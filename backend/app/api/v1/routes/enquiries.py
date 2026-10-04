"""Send enquiries without exposing landlord contact details to the browser."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_student
from app.db.base import get_db
from app.models.user import User
from app.models.student import Student
from app.models.landlord import Landlord
from app.services.resource_access import visible_accommodation
from app.services.email_service import send_email
from app.services.enquiry_service import claim_enquiry, complete_enquiry, message_digest

router = APIRouter(prefix="/accommodations", tags=["Enquiries"])


class EnquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=20, max_length=3000)
    consent: Literal[True]

    @field_validator("message", mode="before")
    @classmethod
    def trim_message(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.post("/{accommodation_id}/enquiries")
async def send_enquiry(
    accommodation_id: int,
    body: EnquiryCreate,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    current_user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    listing = await visible_accommodation(db, accommodation_id, current_user)
    student = (await db.execute(select(Student).where(Student.user_id == current_user.id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    owner = (await db.execute(select(User).join(Landlord, Landlord.user_id == User.id).where(
        Landlord.id == listing.landlord_id, User.role == "landlord", User.is_active.is_(True),
    ))).scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=409, detail="This listing cannot receive enquiries at the moment.")
    digest = message_digest(listing.id, body.message)
    request_key, already_sent = await claim_enquiry(current_user.id, listing.id, idempotency_key, digest)
    if already_sent:
        return {"detail": "Your enquiry has already been sent to the landlord."}
    name = " ".join(part for part in (student.first_name, student.last_name) if part) or "Student"
    email_body = (
        f"New student enquiry through AccomFind\n\nListing: {listing.title}\n"
        f"Listing link: {settings.FRONTEND_URL.rstrip('/')}/listings/{listing.id}\n\n"
        f"Student: {name}\nStudent email: {current_user.email}\n\n"
        f"Enquiry:\n{body.message}\n\n"
        "Reply to this email to respond directly to the student.\n"
        "The student consented to sharing their name and email for this enquiry.\n"
    )
    try:
        await send_email(owner.email, f"AccomFind enquiry for listing #{listing.id}", email_body,
                         reply_to=current_user.email)
    except Exception:
        try:
            await complete_enquiry(request_key, digest, "failed")
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="Delivery could not be confirmed. Wait at least a minute before starting a new enquiry.") from None
    try:
        await complete_enquiry(request_key, digest, "sent")
    except Exception:
        # SMTP accepted the message: never encourage an immediate duplicate send.
        return {"detail": "Your enquiry was accepted by the email service. Please avoid submitting it again."}
    return {"detail": "Your enquiry has been sent to the landlord. They can reply to your email."}
