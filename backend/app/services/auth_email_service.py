import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from fastapi import HTTPException
from sqlalchemy import select, update
from app.core.config import settings
from app.models.auth_email_token import AuthEmailToken
from app.models.user import User
from app.services.email_service import send_auth_email


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_email_token(db, user: User, purpose: str) -> bool:
    # Serialise requests for the same account, including token replacement.
    await db.execute(select(User).where(User.id == user.id).with_for_update())
    timestamp = now()
    result = await db.execute(select(AuthEmailToken).where(
        AuthEmailToken.user_id == user.id,
        AuthEmailToken.purpose == purpose,
        AuthEmailToken.created_at > timestamp - timedelta(hours=1),
    ).order_by(AuthEmailToken.created_at.desc()))
    recent = result.scalars().all()
    if len(recent) >= 3 or (recent and aware(recent[0].created_at) > timestamp - timedelta(seconds=60)):
        return False
    await db.execute(update(AuthEmailToken).where(
        AuthEmailToken.user_id == user.id,
        AuthEmailToken.purpose == purpose,
        AuthEmailToken.used_at.is_(None),
    ).values(used_at=timestamp))
    token = secrets.token_urlsafe(32)
    verifying = purpose == "verify_email"
    db.add(AuthEmailToken(
        token_hash=digest(token), user_id=user.id, purpose=purpose,
        created_at=timestamp,
        expires_at=timestamp + (timedelta(hours=24) if verifying else timedelta(minutes=30)),
    ))
    await db.flush()
    path = "verify-email" if verifying else "reset-password"
    # A fragment keeps the secret out of request URLs and access logs.
    link = f"{settings.FRONTEND_URL.rstrip('/')}/{path}#{urlencode({'token': token})}"
    subject = "Verify your AccomFind email" if verifying else "Reset your AccomFind password"
    expiry = "24 hours" if verifying else "30 minutes"
    await send_auth_email(user.email, subject,
        f"{subject}\n\nOpen this link and confirm the action:\n{link}\n\n"
        f"This link expires in {expiry} and can be used once. "
        "If you did not request this, you can ignore this email.")
    return True


async def consume_email_token(db, token: str, purpose: str):
    result = await db.execute(select(AuthEmailToken).where(AuthEmailToken.token_hash == digest(token)))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=400, detail="This link is invalid or expired. Request a new link.")
    user_result = await db.execute(select(User).where(User.id == candidate.user_id).with_for_update())
    user = user_result.scalar_one_or_none()
    result = await db.execute(select(AuthEmailToken).where(
        AuthEmailToken.token_hash == digest(token)
    ).with_for_update().execution_options(populate_existing=True))
    record = result.scalar_one_or_none()
    if not user or not record or record.purpose != purpose or record.used_at or aware(record.expires_at) <= now():
        raise HTTPException(status_code=400, detail="This link is invalid or expired. Request a new link.")
    record.used_at = now()
    return user
