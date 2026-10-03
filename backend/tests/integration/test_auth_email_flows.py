"""Exercise the authentication API against isolated SQLite data and captured mail.

The small adapter below provides AsyncSession's awaited interface over SQLite's
synchronous driver, so no extra test dependency or running service is required.
These tests cover application behaviour, not PostgreSQL row-lock semantics.
"""
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.db.models  # Register relationship targets.
from app.api.v1.routes.auth import router
from app.api.v1.routes.admin import router as admin_router
from app.core.dependencies import get_optional_user
from app.core.security import create_access_token, create_refresh_token, get_password_hash
from app.db.base import get_db
from app.models.auth_email_token import AuthEmailToken
from app.models.student import Student
from app.models.user import User
from app.services import auth_email_service


class AwaitedSession:
    def __init__(self, session):
        self.session = session

    def add(self, value):
        self.session.add(value)

    async def execute(self, statement):
        return self.session.execute(statement)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def refresh(self, value):
        self.session.refresh(value)


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE universities (id INTEGER PRIMARY KEY, domain VARCHAR NOT NULL)"))
        connection.execute(text("INSERT INTO universities VALUES (1, 'spu.ac.za')"))
    User.__table__.create(engine)
    Student.__table__.create(engine)
    AuthEmailToken.__table__.create(engine)
    session = Session(engine, expire_on_commit=False)
    db = AwaitedSession(session)
    emails = []

    async def capture(recipient, subject, body):
        emails.append({"recipient": recipient, "subject": subject, "body": body})

    monkeypatch.setattr(auth_email_service, "send_auth_email", capture)
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.include_router(admin_router, prefix="/api/v1")

    async def isolated_db():
        try:
            yield db
        finally:
            session.rollback()

    application.dependency_overrides[get_db] = isolated_db

    from fastapi import Depends

    @application.get("/optional-user")
    async def optional_user(user=Depends(get_optional_user)):
        return {"user_id": user.id if user else None}

    yield application, session, emails
    session.close()
    engine.dispose()


@pytest_asyncio.fixture
async def client(setup):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=setup[0]), base_url="http://test") as connection:
        yield connection


STUDENT = {"email": "student@spu.ac.za", "password": "StudentPass123!", "first_name": "Test", "last_name": "Student", "student_number": "12345678"}


def token_from(emails, index=-1):
    link = re.search(r"https?://\S+", emails[index]["body"]).group()
    return parse_qs(urlsplit(link).fragment)["token"][0]


def create_user(session, *, role="student", verified=True, active=True):
    user = User(email="student@spu.ac.za", password_hash=get_password_hash(STUDENT["password"]), role=role,
                is_active=active, email_verified_at=auth_email_service.now() if verified else None)
    session.add(user)
    session.commit()
    if role == "student":
        session.add(Student(user_id=user.id, university_id=1, verification_tier=1 if verified else 0))
        session.commit()
    return user


@pytest.mark.asyncio
async def test_registration_verification_login_and_reuse(client, setup):
    _, session, emails = setup
    response = await client.post("/api/v1/auth/register/student", json=STUDENT)
    assert response.status_code == 201
    assert "token" not in response.text
    user = session.scalar(select(User))
    assert user.is_active and user.email_verified_at is None
    assert session.scalar(select(Student)).verification_tier == 0
    assert len(emails) == 1 and emails[0]["recipient"] == STUDENT["email"]
    token = token_from(emails)
    record = session.scalar(select(AuthEmailToken))
    assert record.token_hash != token and record.token_hash == auth_email_service.digest(token)
    assert (record.expires_at - record.created_at) == timedelta(hours=24)
    assert (await client.post("/api/v1/auth/login", json=STUDENT)).status_code == 403
    old_access = create_access_token(user.id)
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})).status_code == 403
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": create_refresh_token(user.id)})).status_code == 403
    assert (await client.get("/optional-user", headers={"Authorization": f"Bearer {old_access}"})).json()["user_id"] is None
    assert (await client.post("/api/v1/auth/verify-email", json={"token": token})).status_code == 200
    assert user.email_verified_at is not None
    assert session.scalar(select(Student)).verification_tier == 1
    assert (await client.post("/api/v1/auth/verify-email", json={"token": token})).status_code == 400
    login = await client.post("/api/v1/auth/login", json=STUDENT)
    assert login.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("email,status", [("student@example.com", 422), ("student@other.ac.za", 400), ("student@SPU.AC.ZA", 201)])
async def test_registration_domains(client, email, status):
    assert (await client.post("/api/v1/auth/register/student", json={**STUDENT, "email": email})).status_code == status


@pytest.mark.asyncio
async def test_duplicate_registration(client):
    assert (await client.post("/api/v1/auth/register/student", json=STUDENT)).status_code == 201
    assert (await client.post("/api/v1/auth/register/student", json=STUDENT)).status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("purpose,endpoint", [("verify_email", "resend-verification"), ("reset_password", "request-password-reset")])
async def test_resend_rate_limit_and_replacement(client, setup, purpose, endpoint):
    _, session, emails = setup
    create_user(session, verified=False)
    path = f"/api/v1/auth/{endpoint}"
    await client.post(path, json={"email": STUDENT["email"]})
    first = token_from(emails)
    await client.post(path, json={"email": STUDENT["email"]})
    assert len(emails) == 1
    for expected in (2, 3):
        for record in session.scalars(select(AuthEmailToken)):
            record.created_at = auth_email_service.now() - timedelta(minutes=2)
        session.commit()
        await client.post(path, json={"email": STUDENT["email"]})
        assert len(emails) == expected
    for record in session.scalars(select(AuthEmailToken)):
        record.created_at = auth_email_service.now() - timedelta(minutes=2)
    session.commit()
    await client.post(path, json={"email": STUDENT["email"]})
    assert len(emails) == 3
    old = session.get(AuthEmailToken, auth_email_service.digest(first))
    assert old.used_at is not None
    assert len([record for record in session.scalars(select(AuthEmailToken)) if record.used_at is None]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["resend-verification", "request-password-reset"])
async def test_generic_request_response(client, setup, endpoint):
    create_user(setup[1], verified=False)
    known = await client.post(f"/api/v1/auth/{endpoint}", json={"email": STUDENT["email"]})
    unknown = await client.post(f"/api/v1/auth/{endpoint}", json={"email": "missing@spu.ac.za"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(setup[2]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,submit,purpose", [
    ("resend-verification", "verify-email", "verify_email"),
    ("request-password-reset", "reset-password", "reset_password"),
])
async def test_expired_and_wrong_purpose_links(client, setup, endpoint, submit, purpose):
    _, session, emails = setup
    create_user(session, verified=False)
    await client.post(f"/api/v1/auth/{endpoint}", json={"email": STUDENT["email"]})
    token = token_from(emails)
    wrong = "reset-password" if submit == "verify-email" else "verify-email"
    assert (await client.post(f"/api/v1/auth/{wrong}", json={"token": token, "password": "NewPassword123!"})).status_code == 400
    record = session.scalar(select(AuthEmailToken))
    assert record.used_at is None
    record.expires_at = auth_email_service.now() - timedelta(seconds=1)
    session.commit()
    assert (await client.post(f"/api/v1/auth/{submit}", json={"token": token, "password": "NewPassword123!"})).status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "landlord", "moderator", "admin"])
async def test_reset_password_revokes_all_sessions(client, setup, role):
    _, session, emails = setup
    user = create_user(session, role=role)
    login = (await client.post("/api/v1/auth/login", json=STUDENT)).json()
    await client.post("/api/v1/auth/request-password-reset", json={"email": STUDENT["email"]})
    token = token_from(emails)
    record = session.scalar(select(AuthEmailToken))
    assert record.expires_at - record.created_at == timedelta(minutes=30)
    assert (await client.post("/api/v1/auth/reset-password", json={"token": token, "password": "NewPassword123!"})).status_code == 200
    assert user.token_version == 1
    old_headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert (await client.get("/api/v1/auth/me", headers=old_headers)).status_code == 401
    assert (await client.get("/optional-user", headers=old_headers)).json()["user_id"] is None
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json=STUDENT)).status_code == 401
    new_login = await client.post("/api/v1/auth/login", json={**STUDENT, "password": "NewPassword123!"})
    assert new_login.status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": new_login.json()["refresh_token"]})).status_code == 200
    assert (await client.post("/api/v1/auth/reset-password", json={"token": token, "password": "AnotherPassword123!"})).status_code == 400


@pytest.mark.asyncio
async def test_verification_never_activates_suspended_account(client, setup):
    user = create_user(setup[1], verified=False, active=False)
    await client.post("/api/v1/auth/resend-verification", json={"email": STUDENT["email"]})
    assert (await client.post("/api/v1/auth/verify-email", json={"token": token_from(setup[2])})).status_code == 200
    assert user.email_verified_at is not None and not user.is_active
    assert (await client.post("/api/v1/auth/login", json=STUDENT)).status_code == 403


@pytest.mark.asyncio
async def test_password_reset_does_not_verify_or_activate(client, setup):
    user = create_user(setup[1], verified=False, active=False)
    await client.post("/api/v1/auth/request-password-reset", json={"email": STUDENT["email"]})
    assert (await client.post("/api/v1/auth/reset-password", json={"token": token_from(setup[2]), "password": "NewPassword123!"})).status_code == 200
    assert not user.is_active and user.email_verified_at is None


@pytest.mark.asyncio
async def test_delivery_failure_rolls_back_registration(client, setup, monkeypatch):
    async def fail(*args):
        raise RuntimeError("Unavailable")
    monkeypatch.setattr(auth_email_service, "send_auth_email", fail)
    assert (await client.post("/api/v1/auth/register/student", json=STUDENT)).status_code == 503
    assert setup[1].scalar(select(func.count()).select_from(User)) == 0
    assert setup[1].scalar(select(func.count()).select_from(AuthEmailToken)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["resend-verification", "request-password-reset"])
async def test_delivery_failure_preserves_generic_response(client, setup, monkeypatch, endpoint):
    create_user(setup[1], verified=False)
    async def fail(*args):
        raise RuntimeError("Unavailable")
    monkeypatch.setattr(auth_email_service, "send_auth_email", fail)
    response = await client.post(f"/api/v1/auth/{endpoint}", json={"email": STUDENT["email"]})
    assert response.status_code == 200
    assert setup[1].scalar(select(func.count()).select_from(AuthEmailToken)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["verify-email", "reset-password"])
async def test_invalid_token_and_password_validation(client, endpoint):
    assert (await client.post(f"/api/v1/auth/{endpoint}", json={"token": "x" * 43, "password": "NewPassword123!"})).status_code == 400
    assert (await client.post(f"/api/v1/auth/{endpoint}", json={"token": "short", "password": "NewPassword123!"})).status_code == 422
    if endpoint == "reset-password":
        assert (await client.post(f"/api/v1/auth/{endpoint}", json={"token": "x" * 43, "password": "short"})).status_code == 422


def administrator_headers(session, target):
    admin = User(email="admin@example.com", password_hash=target.password_hash, role="admin", is_active=True)
    session.add(admin)
    session.commit()
    return {"Authorization": f"Bearer {create_access_token(admin.id)}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "landlord", "moderator"])
async def test_deactivation_and_reactivation_never_restore_old_sessions(client, setup, role):
    user = create_user(setup[1], role=role)
    admin_headers = administrator_headers(setup[1], user)
    tokens = (await client.post("/api/v1/auth/login", json=STUDENT)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.patch(f"/api/v1/admin/users/{user.id}/deactivate", headers=admin_headers)).status_code == 200
    assert not user.is_active and user.token_version == 1
    for response in [
        await client.post("/api/v1/auth/login", json=STUDENT),
        await client.get("/api/v1/auth/me", headers=headers),
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}),
    ]:
        assert response.status_code == 403
        assert response.headers["x-auth-error"] == "account_inactive"
    assert (await client.get("/optional-user", headers=headers)).json()["user_id"] is None
    assert (await client.patch(f"/api/v1/admin/users/{user.id}/deactivate", headers=admin_headers)).status_code == 200
    assert user.token_version == 1  # Retrying the same status change is harmless.
    assert (await client.patch(f"/api/v1/admin/users/{user.id}/activate", headers=admin_headers)).status_code == 200
    assert user.is_active and user.token_version == 2
    for response in [
        await client.get("/api/v1/auth/me", headers=headers),
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}),
    ]:
        assert response.status_code == 401
        assert response.headers["x-auth-error"] == "session_revoked"
    assert (await client.get("/optional-user", headers=headers)).json()["user_id"] is None
    fresh = await client.post("/api/v1/auth/login", json=STUDENT)
    assert fresh.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh.json()['access_token']}"})).status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": fresh.json()["refresh_token"]})).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "landlord", "moderator", "admin"])
async def test_inactive_accounts_blocked_in_all_auth_paths(client, setup, role):
    user = create_user(setup[1], role=role, active=False)
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    for response in [
        await client.post("/api/v1/auth/login", json=STUDENT),
        await client.get("/api/v1/auth/me", headers=headers),
        await client.post("/api/v1/auth/refresh", json={"refresh_token": create_refresh_token(user.id)}),
    ]:
        assert response.status_code == 403 and response.headers["x-auth-error"] == "account_inactive"
    assert (await client.get("/optional-user", headers=headers)).json()["user_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["student", "landlord", "moderator"])
async def test_status_changes_require_administrator(client, setup, role):
    user = create_user(setup[1], role=role)
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    for action in ["activate", "deactivate"]:
        response = await client.patch(f"/api/v1/admin/users/{user.id}/{action}", headers=headers)
        assert response.status_code == 403
        assert "x-auth-error" not in response.headers  # Permission errors do not end sessions.
    assert user.is_active and user.token_version == 0


@pytest.mark.asyncio
async def test_admin_account_deactivation_protection_remains(client, setup):
    user = create_user(setup[1], role="admin")
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    response = await client.patch(f"/api/v1/admin/users/{user.id}/deactivate", headers=headers)
    assert response.status_code == 400
    assert user.is_active and user.token_version == 0


@pytest.mark.asyncio
async def test_legacy_inactive_account_tokens_revoked_on_activation(client, setup):
    user = create_user(setup[1], active=False)
    headers = administrator_headers(setup[1], user)
    old_access = create_access_token(user.id)
    old_refresh = create_refresh_token(user.id)
    assert (await client.patch(f"/api/v1/admin/users/{user.id}/activate", headers=headers)).status_code == 200
    assert user.token_version == 1
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})).status_code == 401


@pytest.mark.asyncio
async def test_activation_does_not_verify_student_email(client, setup):
    user = create_user(setup[1], verified=False, active=False)
    headers = administrator_headers(setup[1], user)
    assert (await client.patch(f"/api/v1/admin/users/{user.id}/activate", headers=headers)).status_code == 200
    assert user.is_active and user.email_verified_at is None
    response = await client.post("/api/v1/auth/login", json=STUDENT)
    assert response.status_code == 403 and response.headers["x-auth-error"] == "email_unverified"
