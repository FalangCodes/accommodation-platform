from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from azure.core.exceptions import ResourceNotFoundError
from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.accommodation import Accommodation
from app.models.landlord import Landlord
from app.models.user import User
from app.services.storage_service import download_document, upload_document, validate_document, DOCUMENT_TYPES, MAX_DOCUMENT_SIZE

router = APIRouter(tags=["Private documents"])


async def store_document_upload(file):
    data = await file.read(MAX_DOCUMENT_SIZE + 1)
    try:
        validate_document(data, file.content_type)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    try:
        return await upload_document(data, file.content_type)
    except Exception:
        raise HTTPException(status_code=503, detail="Document storage is unavailable")


async def document_response(reference, label):
    if not reference:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        data, content_type = await download_document(reference)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception:
        raise HTTPException(status_code=503, detail="Document storage is unavailable")
    return Response(data, media_type=content_type, headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'attachment; filename="{label}.{DOCUMENT_TYPES[content_type]}"',
        "X-Content-Type-Options": "nosniff",
    })


def authorize_landlord_document(landlord, user):
    if user.role in ("moderator", "admin"):
        return
    if user.role != "landlord" or landlord.user_id != user.id:
        raise HTTPException(status_code=403, detail="Document access denied")


@router.get("/landlords/{landlord_id}/documents/{kind}")
async def get_landlord_document(landlord_id: int, kind: str,
                                user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fields = {"id-copy": "id_copy_url", "proof-of-address": "proof_of_address_url"}
    if kind not in fields:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(select(Landlord).where(Landlord.id == landlord_id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Document not found")
    authorize_landlord_document(landlord, user)
    return await document_response(getattr(landlord, fields[kind]), kind)


@router.get("/accommodations/{accommodation_id}/documents/ownership")
async def get_ownership_document(accommodation_id: int, user: User = Depends(get_current_user),
                                 db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Accommodation).where(Accommodation.id == accommodation_id))
    accommodation = result.scalar_one_or_none()
    if not accommodation:
        raise HTTPException(status_code=404, detail="Document not found")
    result = await db.execute(select(Landlord).where(Landlord.id == accommodation.landlord_id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Document not found")
    authorize_landlord_document(landlord, user)
    return await document_response(accommodation.ownership_doc_url, "ownership")
