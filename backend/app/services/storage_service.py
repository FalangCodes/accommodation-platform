import asyncio
import uuid
from urllib.parse import urlsplit, unquote
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
from app.core.config import settings

DOCUMENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


def get_blob_client():
    return BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)


def blob_location(client, reference, allowed_containers):
    """Resolve only this account's permitted containers, never arbitrary URLs."""
    url, account = urlsplit(reference), urlsplit(client.url)
    parts = unquote(url.path).lstrip("/").split("/", 1)
    if (url.scheme != "https" or url.netloc.lower() != account.netloc.lower()
            or url.query or url.fragment or len(parts) != 2
            or parts[0] not in allowed_containers or not parts[1]
            or any(p in (".", "..") for p in parts[1].split("/"))):
        raise ValueError("Invalid storage reference")
    return parts


def validate_document(data, content_type):
    valid = {
        "application/pdf": data.startswith(b"%PDF-"),
        "image/jpeg": data.startswith(bytes([255, 216, 255])),
        "image/png": data.startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10])),
        "image/webp": len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    }
    if not data or len(data) > MAX_DOCUMENT_SIZE or not valid.get(content_type, False):
        raise ValueError("Document must be a matching JPEG, PNG, WebP or PDF file under 10MB")


def ensure_private(container):
    if container.get_container_properties().get("public_access") is not None:
        raise ValueError("Document container must be private")


async def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    def upload():
        with get_blob_client() as client:
            container = client.get_container_client(settings.AZURE_STORAGE_CONTAINER_NAME)
            blob = container.get_blob_client(f"{uuid.uuid4()}.{DOCUMENT_TYPES.get(content_type, 'jpg')}")
            blob.upload_blob(file_bytes, content_settings=ContentSettings(content_type=content_type), overwrite=False)
            return blob.url
    return await asyncio.to_thread(upload)


async def upload_document(file_bytes: bytes, content_type: str) -> str:
    validate_document(file_bytes, content_type)
    def upload():
        if settings.AZURE_DOCUMENT_CONTAINER_NAME == settings.AZURE_STORAGE_CONTAINER_NAME:
            raise ValueError("Separate document storage is required")
        with get_blob_client() as client:
            container = client.get_container_client(settings.AZURE_DOCUMENT_CONTAINER_NAME)
            ensure_private(container)
            blob = container.get_blob_client(f"{uuid.uuid4()}.{DOCUMENT_TYPES[content_type]}")
            blob.upload_blob(file_bytes, content_settings=ContentSettings(content_type=content_type), overwrite=False)
            return blob.url
    return await asyncio.to_thread(upload)


async def download_document(reference: str):
    def download():
        with get_blob_client() as client:
            container_name, name = blob_location(client, reference, {settings.AZURE_DOCUMENT_CONTAINER_NAME})
            container = client.get_container_client(container_name)
            ensure_private(container)
            blob = container.get_blob_client(name)
            properties = blob.get_blob_properties()
            content_type = properties.content_settings.content_type
            if properties.size > MAX_DOCUMENT_SIZE or content_type not in DOCUMENT_TYPES:
                raise ValueError("Invalid stored document")
            return blob.download_blob().readall(), content_type
    return await asyncio.to_thread(download)


async def delete_image(blob_url: str) -> None:
    def delete():
        with get_blob_client() as client:
            container, name = blob_location(client, blob_url, {settings.AZURE_STORAGE_CONTAINER_NAME})
            try:
                client.get_blob_client(container, name).delete_blob()
            except ResourceNotFoundError:
                pass
    await asyncio.to_thread(delete)
