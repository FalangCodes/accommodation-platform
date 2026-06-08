import uuid
from azure.storage.blob import BlobServiceClient
from app.core.config import settings

def get_blob_client():
    return BlobServiceClient.from_connection_string(
        settings.AZURE_STORAGE_CONNECTION_STRING
    )

async def upload_image(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload image to Azure Blob Storage and return public URL."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    blob_name = f"{uuid.uuid4()}.{ext}"

    client = get_blob_client()
    container_client = client.get_container_client(
        settings.AZURE_STORAGE_CONTAINER_NAME
    )

    container_client.upload_blob(
        name=blob_name,
        data=file_bytes,
        content_settings=__import__(
            "azure.storage.blob",
            fromlist=["ContentSettings"]
        ).ContentSettings(content_type=content_type),
        overwrite=True
    )

    return f"https://accomfindstorage.blob.core.windows.net/{settings.AZURE_STORAGE_CONTAINER_NAME}/{blob_name}"


async def delete_image(blob_url: str) -> None:
    """Delete image from Azure Blob Storage by URL."""
    blob_name = blob_url.rsplit("/", 1)[-1]
    client = get_blob_client()
    container_client = client.get_container_client(
        settings.AZURE_STORAGE_CONTAINER_NAME
    )
    try:
        container_client.delete_blob(blob_name)
    except Exception:
        pass