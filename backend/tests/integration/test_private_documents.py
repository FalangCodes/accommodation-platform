"""Authenticated document routes with isolated users and mocked storage."""
import httpx
import pytest
from sqlalchemy import select
from test_resource_permissions import resources
from app.api.v1.routes import documents
from app.models.landlord import Landlord
from app.models.user import User

REFERENCE = "https://storage.blob.core.windows.net/verification-documents/private.pdf"


@pytest.fixture
def private_documents(resources, monkeypatch):
    app, headers, listing, cache, effects, session = resources
    app.include_router(documents.router, prefix="/api/v1")
    landlord = session.execute(select(Landlord).where(Landlord.id == 1)).scalar_one()
    landlord.id_copy_url = landlord.proof_of_address_url = REFERENCE
    listing.ownership_doc_url = REFERENCE
    cache["listing:1"]["ownership_doc_url"] = REFERENCE
    session.commit()
    calls = []

    async def download(reference):
        calls.append(("download", reference))
        return b"%PDF-1.4 test", "application/pdf"

    async def upload(data, content_type):
        calls.append(("upload", content_type))
        return REFERENCE

    monkeypatch.setattr(documents, "download_document", download)
    monkeypatch.setattr(documents, "upload_document", upload)
    return resources, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["guest", "student", "other_landlord", "owner", "moderator", "admin"])
@pytest.mark.parametrize("path", ["landlords/1/documents/id-copy", "landlords/1/documents/proof-of-address",
                                  "accommodations/1/documents/ownership"])
async def test_document_download_permissions_and_headers(private_documents, actor, path):
    (app, headers, _, _, _, _), calls = private_documents
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/{path}", headers=headers(actor))
    if actor in ("owner", "moderator", "admin"):
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF-")
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"].endswith('.pdf"')
        assert len(calls) == 1
    else:
        assert response.status_code in (401, 403)
        assert not calls


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["guest", "student", "other_landlord", "owner", "moderator", "admin"])
async def test_listing_responses_never_expose_blob_references(private_documents, actor):
    (app, headers, listing, _, _, _), _ = private_documents
    listing.status = "approved"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/accommodations/1", headers=headers(actor))
    assert response.status_code == 200
    assert "blob.core.windows.net" not in response.text
    if actor in ("owner", "moderator", "admin"):
        assert response.json()["ownership_doc_url"] == "/api/v1/accommodations/1/documents/ownership"
    else:
        assert "ownership_doc_url" not in response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["landlords/me/documents/id-copy", "landlords/me/documents/proof-of-address",
                                  "accommodations/1/documents/ownership"])
async def test_uploads_validate_content_and_return_only_protected_paths(private_documents, path):
    (app, headers, _, _, _, _), calls = private_documents
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        auth = headers("owner")
        invalid = await client.post(f"/api/v1/{path}", headers=auth, files={"file": ("fake.pdf", b"<html>bad</html>", "application/pdf")})
        assert invalid.status_code == 400
        assert not calls
        other = await client.post(f"/api/v1/{path}", headers=headers("student"), files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")})
        assert other.status_code == 403
        response = await client.post(f"/api/v1/{path}", headers=auth, files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")})
        assert response.status_code == 200
        assert response.json()["url"].startswith("/api/v1/")
        assert "blob.core.windows.net" not in response.text
        assert calls == [("upload", "application/pdf")]


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["inactive", "unverified", "revoked"])
async def test_ineligible_sessions_cannot_download(private_documents, condition):
    (app, headers, _, _, _, session), calls = private_documents
    actor = "student" if condition == "unverified" else "owner"
    user = session.get(User, 3 if actor == "student" else 1)
    if condition == "inactive":
        user.is_active = False
    elif condition == "unverified":
        user.email_verified_at = None
    else:
        user.token_version = 1
    session.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/landlords/1/documents/id-copy", headers=headers(actor))
        assert response.status_code in (401, 403)
    assert not calls


@pytest.mark.asyncio
async def test_missing_documents_and_storage_failure(private_documents, monkeypatch):
    (app, headers, listing, _, _, _), calls = private_documents
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        listing.ownership_doc_url = None
        assert (await client.get("/api/v1/accommodations/1/documents/ownership", headers=headers("owner"))).status_code == 404
        assert not calls
        listing.ownership_doc_url = REFERENCE
        async def unavailable(reference):
            raise RuntimeError("Sensitive storage details must not leak")
        monkeypatch.setattr(documents, "download_document", unavailable)
        response = await client.get("/api/v1/accommodations/1/documents/ownership", headers=headers("owner"))
        assert response.status_code == 503
        assert "Sensitive" not in response.text
