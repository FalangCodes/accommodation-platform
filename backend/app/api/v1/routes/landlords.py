from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone

from app.db.base import get_db
from app.core.dependencies import get_current_landlord, get_current_moderator
from app.models.user import User
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation
from app.models.moderation import ModerationLog
from app.api.v1.routes.documents import store_document_upload
from app.services.document_links import landlord_document_link
from app.core.encryption import decrypt_value

router = APIRouter(prefix="/landlords", tags=["Landlords"])

async def get_landlord_profile(current_user: User, db: AsyncSession) -> Landlord:
    result = await db.execute(select(Landlord).where(Landlord.user_id == current_user.id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord profile not found")
    return landlord


# ── Document uploads ──────────────────────────────────────────────────────────

@router.post("/me/documents/id-copy", status_code=status.HTTP_200_OK)
async def upload_id_copy(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    landlord = await get_landlord_profile(current_user, db)

    landlord.id_copy_url = await store_document_upload(file)
    await db.commit()
    return {"detail": "ID copy uploaded successfully", "url": landlord_document_link(landlord.id, "id-copy", landlord.id_copy_url)}


@router.post("/me/documents/proof-of-address", status_code=status.HTTP_200_OK)
async def upload_proof_of_address(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    landlord = await get_landlord_profile(current_user, db)

    landlord.proof_of_address_url = await store_document_upload(file)
    await db.commit()
    return {"detail": "Proof of address uploaded successfully", "url": landlord_document_link(landlord.id, "proof-of-address", landlord.proof_of_address_url)}


@router.post("/me/verification/submit", status_code=status.HTTP_200_OK)
async def submit_verification(
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    landlord = await get_landlord_profile(current_user, db)

    if landlord.verification_status == "verified":
        raise HTTPException(status_code=400, detail="Your account is already verified")

    if landlord.verification_status == "pending":
        raise HTTPException(status_code=400, detail="Your verification is already under review")

    if not landlord.id_copy_url:
        raise HTTPException(status_code=400, detail="Please upload your ID copy before submitting")

    if not landlord.proof_of_address_url:
        raise HTTPException(status_code=400, detail="Please upload proof of address before submitting")

    if not landlord.id_number_encrypted:
        raise HTTPException(status_code=400, detail="ID number is required for verification")

    landlord.verification_status = "pending"
    await db.commit()

    return {"detail": "Verification submitted. An admin will review your documents shortly."}


# ── Landlord profile ──────────────────────────────────────────────────────────

@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_landlord),
    db: AsyncSession = Depends(get_db)
):
    landlord = await get_landlord_profile(current_user, db)

    return {
        "id": landlord.id,
        "display_name": landlord.display_name,
        "contact_phone": landlord.contact_phone,
        "bio": landlord.bio,
        "website": landlord.website,
        "verification_status": landlord.verification_status,
        "rejection_reason": landlord.rejection_reason,
        "id_copy_uploaded": landlord.id_copy_url is not None,
        "proof_of_address_uploaded": landlord.proof_of_address_url is not None,
        "id_number_verified": landlord.id_number_verified,
        "verified_at": landlord.verified_at,
    }


# ── Admin verification endpoints ──────────────────────────────────────────────

@router.get("/pending-verification")
async def get_pending_landlords(
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Get all landlords with pending verification — admin/moderator only."""
    result = await db.execute(
        select(Landlord).where(Landlord.verification_status == "pending")
        .order_by(Landlord.id.asc())
    )
    landlords = result.scalars().all()

    output = []
    for l in landlords:
        # Fetch email from users table
        from app.models.user import User as UserModel
        user_result = await db.execute(
            select(UserModel).where(UserModel.id == l.user_id)
        )
        user = user_result.scalar_one_or_none()

        # Decrypt ID number for admin review
        id_number = None
        if l.id_number_encrypted:
            try:
                id_number = decrypt_value(l.id_number_encrypted)
            except Exception:
                id_number = "Decryption failed"

        output.append({
            "id": l.id,
            "display_name": l.display_name,
            "email": user.email if user else None,
            "contact_phone": l.contact_phone,
            "id_number": id_number,
            "id_number_verified": l.id_number_verified,
            "id_copy_url": landlord_document_link(l.id, "id-copy", l.id_copy_url),
            "proof_of_address_url": landlord_document_link(l.id, "proof-of-address", l.proof_of_address_url),
            "verification_status": l.verification_status,
            "address": f"{l.address_line1}, {l.city}, {l.province}, {l.postal_code}" if l.address_line1 else None,
        })

    return output


@router.patch("/{landlord_id}/verify")
async def verify_landlord(
    landlord_id: int,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Approve a landlord's verification."""
    result = await db.execute(select(Landlord).where(Landlord.id == landlord_id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")
    if landlord.verification_status != "pending":
        raise HTTPException(status_code=400, detail="Landlord is not pending verification")

    landlord.verification_status = "verified"
    landlord.id_number_verified = True
    landlord.verified_at = datetime.now(timezone.utc)
    landlord.rejection_reason = None

    log = ModerationLog(
        moderator_id=current_user.id,
        action="landlord_verified",
        resource_type="landlord",
        resource_id=landlord_id,
    )
    db.add(log)
    await db.commit()

    return {"detail": "Landlord verified successfully", "landlord_id": landlord_id}


@router.patch("/{landlord_id}/reject-verification")
async def reject_landlord_verification(
    landlord_id: int,
    body: dict,
    current_user: User = Depends(get_current_moderator),
    db: AsyncSession = Depends(get_db)
):
    """Reject a landlord's verification with a reason."""
    reason = body.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    result = await db.execute(select(Landlord).where(Landlord.id == landlord_id))
    landlord = result.scalar_one_or_none()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")

    landlord.verification_status = "rejected"
    landlord.rejection_reason = reason
    landlord.id_number_verified = False

    log = ModerationLog(
        moderator_id=current_user.id,
        action="landlord_verification_rejected",
        resource_type="landlord",
        resource_id=landlord_id,
        reason=reason,
    )
    db.add(log)
    await db.commit()

    return {"detail": "Landlord verification rejected", "landlord_id": landlord_id, "reason": reason}