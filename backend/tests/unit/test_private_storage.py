"""Storage/migration checks using in-memory blobs; no Azure calls."""
from types import SimpleNamespace
import json
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import ContentSettings

from app.services import storage_service as storage
import migrate_document_storage as migration

ACCOUNT = "https://test.blob.core.windows.net"
PDF = b"%PDF-1.4 synthetic test"
JPEG = bytes([255, 216, 255]) + b"synthetic image"


@pytest.fixture
def blobs(monkeypatch):
    files = {("legacy", "photo.jpg"): (JPEG, ContentSettings(content_type="image/jpeg")),
             ("legacy", "document.jpg"): (PDF, ContentSettings(content_type="application/pdf")),
             ("legacy", "orphan.jpg"): (JPEG, ContentSettings(content_type="image/jpeg"))}
    access = {"legacy": "blob", "documents": None, "photos": "blob"}

    class Blob:
        def __init__(self, container, name):
            self.key = (container, name)
            self.url = f"{ACCOUNT}/{container}/{name}"

        def get_blob_properties(self):
            data, settings = files[self.key]
            return SimpleNamespace(size=len(data), content_settings=settings)

        def download_blob(self):
            return SimpleNamespace(readall=lambda: files[self.key][0])

        def upload_blob(self, data, overwrite=False, content_settings=None):
            if self.key in files and not overwrite:
                raise ResourceExistsError("exists")
            files[self.key] = (data, content_settings)

        def delete_blob(self):
            del files[self.key]

    class Container:
        def __init__(self, name):
            self.name = name

        def get_container_properties(self):
            return {"public_access": access[self.name]}

        def create_container(self, public_access=None):
            if self.name in access:
                raise ResourceExistsError("exists")
            access[self.name] = public_access

        def get_blob_client(self, name):
            return Blob(self.name, name)

        def set_container_access_policy(self, signed_identifiers, public_access):
            access[self.name] = public_access

    class Client:
        url = ACCOUNT

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_container_client(self, name):
            return Container(name)

        def get_blob_client(self, container, name):
            return Blob(container, name)

    client = Client()
    monkeypatch.setattr(storage, "get_blob_client", lambda: client)
    monkeypatch.setattr(migration, "get_blob_client", lambda: client)
    monkeypatch.setattr(storage.settings, "AZURE_DOCUMENT_CONTAINER_NAME", "documents")
    monkeypatch.setattr(storage.settings, "AZURE_STORAGE_CONTAINER_NAME", "photos")
    return client, files, access


@pytest.mark.asyncio
async def test_private_upload_download_and_actual_account_url(blobs):
    _, files, _ = blobs
    reference = await storage.upload_document(PDF, "application/pdf")
    assert reference.startswith(ACCOUNT + "/documents/")
    assert reference.endswith(".pdf")
    assert await storage.download_document(reference) == (PDF, "application/pdf")
    photo = await storage.upload_image(JPEG, "anything.jpg", "image/jpeg")
    assert photo.startswith(ACCOUNT + "/photos/")


@pytest.mark.asyncio
async def test_public_document_container_fails_closed(blobs):
    _, files, access = blobs
    access["documents"] = "blob"
    with pytest.raises(ValueError):
        await storage.upload_document(PDF, "application/pdf")
    files[("documents", "existing.pdf")] = (PDF, ContentSettings(content_type="application/pdf"))
    with pytest.raises(ValueError):
        await storage.download_document(ACCOUNT + "/documents/existing.pdf")


@pytest.mark.parametrize("reference", ["https://evil.example/documents/test.pdf", ACCOUNT + "/legacy/document.jpg",
                                      ACCOUNT + "/documents/../photo.jpg", ACCOUNT + "/documents/test.pdf?sig=secret",
                                      "http://test.blob.core.windows.net/documents/test.pdf"])
def test_storage_references_cannot_target_other_accounts_or_containers(blobs, reference):
    with pytest.raises(ValueError):
        storage.blob_location(blobs[0], reference, {"documents"})


@pytest.mark.parametrize("data,kind", [(b"", "application/pdf"), (b"<html>bad</html>", "application/pdf"),
                                      (PDF, "image/jpeg"), (JPEG, "image/svg+xml"),
                                      (PDF + b"x" * (10 * 1024 * 1024), "application/pdf")])
def test_invalid_or_oversized_documents_are_rejected(data, kind):
    with pytest.raises(ValueError):
        storage.validate_document(data, kind)


@pytest.fixture
def migration_db(monkeypatch):
    engine = create_engine("sqlite://")
    session = Session(engine)
    session.execute(text("CREATE TABLE accommodation_images (id INTEGER PRIMARY KEY, blob_url TEXT)"))
    session.execute(text("CREATE TABLE accommodations (id INTEGER PRIMARY KEY, ownership_doc_url TEXT)"))
    session.execute(text("CREATE TABLE landlords (id INTEGER PRIMARY KEY, id_copy_url TEXT, proof_of_address_url TEXT)"))
    session.execute(text("INSERT INTO accommodation_images VALUES (1, :url)"), {"url": ACCOUNT + "/legacy/photo.jpg"})
    session.execute(text("INSERT INTO landlords VALUES (1, :url, NULL)"), {"url": ACCOUNT + "/legacy/document.jpg"})
    session.commit()

    class DB:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            session.rollback()

        async def execute(self, statement, params=None):
            return session.execute(statement, params or {})

        async def commit(self):
            session.commit()

    monkeypatch.setattr(migration, "AsyncSessionLocal", DB)
    yield session
    session.close()
    engine.dispose()


def arguments(apply=False):
    return SimpleNamespace(source_container="legacy", photos_container="photos", documents_container="documents", apply=apply)


@pytest.mark.asyncio
async def test_migration_dry_run_does_not_modify_storage_or_database(blobs, migration_db, capsys):
    _, files, access = blobs
    await migration.migrate(arguments())
    assert len(files) == 3
    assert access["legacy"] == "blob"
    assert json.loads(capsys.readouterr().out)["document_references"] == 1
    assert migration_db.execute(text("SELECT id_copy_url FROM landlords")).scalar().endswith("/legacy/document.jpg")


@pytest.mark.asyncio
async def test_migration_verified_copy_keeps_originals_private_and_is_repeatable(blobs, migration_db, capsys):
    _, files, access = blobs
    await migration.migrate(arguments(True))
    assert access["legacy"] is None
    assert files[("legacy", "orphan.jpg")][0] == JPEG
    assert len(files) == 5
    assert migration_db.execute(text("SELECT blob_url FROM accommodation_images")).scalar().startswith(ACCOUNT + "/photos/")
    assert migration_db.execute(text("SELECT id_copy_url FROM landlords")).scalar().startswith(ACCOUNT + "/documents/")
    await migration.migrate(arguments(True))
    assert len(files) == 5
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["updated_references"] == 0


@pytest.mark.asyncio
async def test_migration_copy_failure_preserves_database_references(blobs, migration_db, monkeypatch):
    def failed_copy(*args):
        raise ValueError("verification failed")
    monkeypatch.setattr(migration, "verified_copy", failed_copy)
    with pytest.raises(ValueError):
        await migration.migrate(arguments(True))
    assert migration_db.execute(text("SELECT blob_url FROM accommodation_images")).scalar().endswith("/legacy/photo.jpg")
    assert blobs[2]["legacy"] == "blob"


@pytest.mark.asyncio
async def test_migration_rejects_document_also_registered_as_public_photo(blobs, migration_db):
    migration_db.execute(text("INSERT INTO accommodations VALUES (1, :url)"), {"url": ACCOUNT + "/legacy/photo.jpg"})
    migration_db.commit()
    with pytest.raises(ValueError):
        await migration.migrate(arguments(True))
    assert len(blobs[1]) == 3
