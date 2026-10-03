"""Copy verified files, update references, then privatize the legacy container.

Dry-run by default. Before --apply: stop backend writes and take a DB backup.
Source blobs are retained; this never deletes files or restores public access
to the old mixed container. Re-running an interrupted migration is supported.
"""
import argparse
import asyncio
import hashlib
import json
from urllib.parse import urlsplit

from azure.core.exceptions import ResourceExistsError
from sqlalchemy import text
from app.db.base import AsyncSessionLocal, engine
from app.services.storage_service import get_blob_client, blob_location, validate_document, MAX_DOCUMENT_SIZE

engine.echo = False
REFERENCES = [("accommodation_images", "blob_url", False), ("accommodations", "ownership_doc_url", True),
              ("landlords", "id_copy_url", True), ("landlords", "proof_of_address_url", True)]


def verified_copy(client, source, destination_container, document):
    container, name = source
    blob = client.get_blob_client(container, name)
    properties = blob.get_blob_properties()
    if properties.size > MAX_DOCUMENT_SIZE:
        raise ValueError("Stored file exceeds the migration size limit")
    data = blob.download_blob().readall()
    content_type = properties.content_settings.content_type
    if not document and content_type == "application/pdf":
        raise ValueError("A public photo is marked as a PDF document")
    validate_document(data, content_type)
    digest = hashlib.sha256(data).digest()
    target_name = "migrated/" + hashlib.sha256(f"{container}/{name}".encode()).hexdigest()
    target = client.get_blob_client(destination_container, target_name)
    try:
        target.upload_blob(data, overwrite=False, content_settings=properties.content_settings)
    except ResourceExistsError:
        pass
    if hashlib.sha256(target.download_blob().readall()).digest() != digest:
        raise ValueError("Copied file verification failed")
    return target.url


async def migrate(args):
    if len({args.source_container, args.photos_container, args.documents_container}) != 3:
        raise ValueError("Three distinct containers are required")
    with get_blob_client() as client:
        async with AsyncSessionLocal() as db:
            entries = []
            for table, column, document in REFERENCES:
                result = await db.execute(text(f"SELECT id, {column} AS reference FROM {table} WHERE {column} IS NOT NULL"))
                for row in result.mappings():
                    reference = row["reference"]
                    if not document and urlsplit(reference).netloc != urlsplit(client.url).netloc:
                        continue  # Existing externally hosted public photos are unchanged.
                    location = blob_location(client, reference, {args.source_container, args.photos_container, args.documents_container})
                    target = args.documents_container if document else args.photos_container
                    if location[0] != args.source_container and location[0] != target:
                        raise ValueError("File is in an unexpected container")
                    client.get_blob_client(*location).get_blob_properties()
                    entries.append((table, column, row["id"], reference, location, target, document))
            photos = {tuple(e[4]) for e in entries if not e[6]}
            documents = {tuple(e[4]) for e in entries if e[6]}
            if photos & documents:
                raise ValueError("A document is also referenced as a public photo")
            summary = {"apply": args.apply, "photo_references": sum(not e[6] for e in entries),
                       "document_references": sum(e[6] for e in entries), "source_files_retained": True}
            if not args.apply:
                print(json.dumps(summary))
                return
            for name, public in ((args.photos_container, "blob"), (args.documents_container, None)):
                container = client.get_container_client(name)
                try:
                    container.create_container(public_access=public)
                except ResourceExistsError:
                    pass
                if container.get_container_properties().get("public_access") != public:
                    raise ValueError("Destination container access level is incorrect")
            changes = []
            for table, column, row_id, original, location, target, document in entries:
                if location[0] == target:
                    if document:
                        blob = client.get_blob_client(*location)
                        validate_document(blob.download_blob().readall(), blob.get_blob_properties().content_settings.content_type)
                    continue
                destination = verified_copy(client, location, target, document)
                changes.append((table, column, row_id, original, destination))
            for table, column, row_id, original, destination in changes:
                result = await db.execute(text(f"UPDATE {table} SET {column} = :destination WHERE id = :id AND {column} = :original"),
                                          {"destination": destination, "id": row_id, "original": original})
                if result.rowcount != 1:
                    raise ValueError("Reference changed during migration; keep backend stopped")
            await db.commit()
            source = client.get_container_client(args.source_container)
            source.set_container_access_policy(signed_identifiers={}, public_access=None)
            if source.get_container_properties().get("public_access") is not None:
                raise ValueError("Legacy container is still public")
            summary["updated_references"] = len(changes)
            summary["legacy_container_private"] = True
            print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-container", required=True)
    parser.add_argument("--photos-container", default="listing-photos")
    parser.add_argument("--documents-container", default="verification-documents")
    parser.add_argument("--apply", action="store_true")
    try:
        asyncio.run(migrate(parser.parse_args()))
    except Exception as error:
        raise SystemExit(f"Migration failed ({type(error).__name__}); keep backend stopped and inspect configuration/references.")
