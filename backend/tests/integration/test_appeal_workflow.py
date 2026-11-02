"""Azure-only PostgreSQL workflow tests in disposable schemas; no production writes."""
import asyncio
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, func, text

from test_review_resubmission import isolated_reviews, historical_review
from app.api.v1.routes import appeals, landlords, admin
from app.core.security import create_access_token
from app.models.user import User
from app.models.landlord import Landlord
from app.models.accommodation import Accommodation
from app.models.moderation import Appeal, ModerationLog
from app.models.review import Review, ReviewNLPResult
from app.services import review_service
from app.services.appeal_policy import SYSTEM_EMAIL


def headers(user_id):
    return {"Authorization": "Bearer " + create_access_token(str(user_id))}


@pytest_asyncio.fixture
async def workflow(isolated_reviews):
    client, sessions, student_headers, admin_headers, effects = isolated_reviews
    for module in (appeals, landlords, admin):
        client._transport.app.include_router(module.router, prefix="/api/v1")
    async with sessions() as db:
        db.add(User(id=4, email="moderator@example.test", role="moderator", is_active=True, password_hash="unused"))
        await db.commit()
        # Explicit seed IDs do not advance PostgreSQL sequences.
        await db.execute(text("SELECT setval(pg_get_serial_sequence('users','id'), (SELECT max(id) FROM users))"))
        await db.commit()
    return client, sessions, student_headers, admin_headers, effects


async def penalty(sessions, kind, resource_id, action):
    async with sessions() as db:
        row = ModerationLog(moderator_id=4, resource_type="accommodation" if kind == "listing" else kind,
                            resource_id=resource_id, action=action, reason="Test moderation reason")
        db.add(row)
        await db.commit()
        return row.id


async def submit(client, kind, resource_id, user_id, action_id=None):
    body = {"resource_type": kind, "resource_id": resource_id,
            "reason": "Please reconsider this moderation decision with the supplied evidence."}
    if action_id is not None:
        body["original_action_id"] = action_id
    return await client.post("/api/v1/appeals", headers=headers(user_id), json=body)


@pytest.mark.asyncio
@pytest.mark.parametrize("original_status", ["analysed", "quarantined"])
async def test_student_history_distinguishes_removal_and_supports_appeal(workflow, original_status):
    client, sessions, student_headers, admin_headers, _ = workflow
    review_id = await historical_review(sessions, deleted=False, status=original_status)
    before = (await client.get("/api/v1/reviews/my", headers=student_headers)).json()[0]
    assert before["status"] == original_status
    assert before["removal_reason"] is None and before["removed_at"] is None
    # A previous removal must not supply the reason for the current decision.
    await penalty(sessions, "review", review_id, "remove_review")
    reason = "The review contains targeted abusive language."
    removed = await client.request("DELETE", f"/api/v1/moderation/reviews/{review_id}",
                                  headers=headers(4), json={"reason": reason})
    assert removed.status_code == 200
    history = (await client.get("/api/v1/reviews/my", headers=student_headers)).json()
    assert len(history) == 1
    assert history[0]["status"] == "removed" and history[0]["removal_reason"] == reason
    assert history[0]["removed_at"] is not None
    async with sessions() as db:
        assert (await db.get(Review, review_id)).status == original_status
    public = (await client.get("/api/v1/reviews/accommodation/1", headers=student_headers)).json()
    assert public["total"] == 0
    assert (await client.get("/api/v1/reviews/my", headers=admin_headers)).status_code == 403
    appeal = await submit(client, "review", review_id, 1)
    assert appeal.status_code == 201
    resolved = await client.patch(f"/api/v1/moderation/appeals/{appeal.json()['id']}/resolve",
                                 headers=admin_headers, json={"decision": "upheld"})
    assert resolved.status_code == 200
    restored = (await client.get("/api/v1/reviews/my", headers=student_headers)).json()[0]
    assert restored["status"] == "released"
    assert restored["removal_reason"] is None and restored["removed_at"] is None
    assert (await client.delete(f"/api/v1/reviews/{review_id}", headers=student_headers)).status_code == 204
    assert (await client.get("/api/v1/reviews/my", headers=student_headers)).json() == []


@pytest.mark.asyncio
async def test_legacy_removed_review_without_audit_reason_remains_private_history(workflow):
    client, sessions, student_headers, _, _ = workflow
    await historical_review(sessions)
    history = (await client.get("/api/v1/reviews/my", headers=student_headers)).json()
    assert len(history) == 1 and history[0]["status"] == "removed"
    assert history[0]["removal_reason"] is None and history[0]["removed_at"] is not None


@pytest.mark.asyncio
async def test_review_appeal_context_includes_full_quarantined_body(workflow):
    client, sessions, _, _, _ = workflow
    review_id = await historical_review(sessions, deleted=False, status="quarantined")
    body = "Original student feedback.\n" * 100 + "Important final sentence."
    async with sessions() as db:
        (await db.get(Review, review_id)).body = body
        await db.commit()
    await penalty(sessions, "review", review_id, "quarantined")
    assert (await submit(client, "review", review_id, 1)).status_code == 201
    listed = await client.get("/api/v1/moderation/appeals", headers=headers(2))
    assert listed.json()[0]["original_review"]["body"] == body
    assert listed.json()[0]["original_review"]["status"] == "quarantined"


@pytest.mark.asyncio
async def test_missing_review_context_does_not_hide_pending_appeal(workflow):
    client, sessions, _, _, _ = workflow
    review_id = await historical_review(sessions)
    await penalty(sessions, "review", review_id, "remove_review")
    created = await submit(client, "review", review_id, 1)
    assert created.status_code == 201
    # Legacy/corrupt missing resources should not make the entire queue fail.
    async with sessions() as db:
        await db.delete(await db.get(Review, review_id))
        await db.commit()
    listed = await client.get("/api/v1/moderation/appeals", headers=headers(2))
    assert listed.status_code == 200 and listed.json()[0]["id"] == created.json()["id"]
    assert listed.json()[0]["original_review"] is None


@pytest.mark.asyncio
async def test_moderators_cannot_list_or_resolve_appeals(workflow):
    client, sessions, _, _, _ = workflow
    old_id = await historical_review(sessions)
    await penalty(sessions, "review", old_id, "remove_review")
    created = await submit(client, "review", old_id, 1)
    assert created.status_code == 201
    for actor in (1, 3, 4):
        assert (await client.get("/api/v1/moderation/appeals", headers=headers(actor))).status_code == 403
        assert (await client.patch(f"/api/v1/moderation/appeals/{created.json()['id']}/resolve",
                                  headers=headers(actor), json={"decision": "upheld"})).status_code == 403
    listed = await client.get("/api/v1/moderation/appeals", headers=headers(2))
    assert listed.status_code == 200
    assert listed.json()[0]["original_action"]["action"] == "remove_review"
    context = listed.json()[0]["original_review"]
    assert context["id"] == old_id and context["body"] == "Original review retained for history."
    assert context["rating"] == 2 and context["status"] == "removed"
    assert context["accommodation_id"] == 1 and context["accommodation_title"] == "Test listing"
    assert context["created_at"] is not None
    async with sessions() as db:
        assert (await db.get(Appeal, created.json()["id"])).status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,action", [("review", "released"), ("listing", "approve_listing"),
                                       ("landlord", "landlord_verified")])
async def test_positive_actions_cannot_be_appealed(workflow, kind, action):
    client, sessions, _, _, _ = workflow
    resource_id = await historical_review(sessions, deleted=False, status="released") if kind == "review" else 1
    action_id = await penalty(sessions, kind, resource_id, action)
    response = await submit(client, kind, resource_id, 1 if kind == "review" else 3, action_id)
    assert response.status_code == 422
    async with sessions() as db:
        assert (await db.execute(select(func.count(Appeal.id)))).scalar() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,action", [("listing", "reject_listing"), ("listing", "suspend_listing"),
                                       ("listing", "remove_listing"), ("landlord", "landlord_verification_rejected")])
async def test_upholding_restores_correct_resource_and_audit_type(workflow, kind, action):
    client, sessions, _, _, effects = workflow
    async with sessions() as db:
        if kind == "listing":
            (await db.get(Accommodation, 1)).status = {"reject_listing": "rejected", "suspend_listing": "suspended", "remove_listing": "removed"}[action]
            (await db.get(Accommodation, 1)).ownership_doc_url = "mock://ownership.pdf"
        else:
            owner = await db.get(Landlord, 1)
            owner.verification_status = "rejected"
            owner.rejection_reason = "Test reason"
            owner.id_number_verified = False
        await db.commit()
    await penalty(sessions, kind, 1, action)
    created = await submit(client, kind, 1, 3)
    assert created.status_code == 201
    pending = (await client.get("/api/v1/moderation/appeals", headers=headers(2))).json()
    assert pending[0]["original_review"] is None
    appeal_id = created.json()["id"]
    response = await client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=headers(2),
                                  json={"decision": "upheld", "reason": "Evidence accepted"})
    assert response.status_code == 200
    async with sessions() as db:
        result = await db.get(Appeal, appeal_id)
        assert result.status == "upheld" and result.assigned_admin_id == 2 and result.resolved_at
        if kind == "listing":
            assert (await db.get(Accommodation, 1)).status == "approved"
        else:
            owner = await db.get(Landlord, 1)
            assert owner.verification_status == "verified" and owner.id_number_verified
            assert owner.verified_at and owner.rejection_reason is None
        last = (await db.execute(select(ModerationLog).order_by(ModerationLog.id.desc()).limit(1))).scalar_one()
        assert last.resource_type == ("accommodation" if kind == "listing" else "landlord")
        assert last.action == "appeal_upheld"
    assert effects
    assert (await client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=headers(2),
                               json={"decision": "upheld"})).status_code == 409


@pytest.mark.asyncio
async def test_stale_review_appeal_does_not_override_release(workflow):
    client, sessions, _, _, _ = workflow
    review_id = await historical_review(sessions, deleted=False, status="quarantined")
    action_id = await penalty(sessions, "review", review_id, "quarantined")
    created = await submit(client, "review", review_id, 1)
    assert created.status_code == 201
    assert (await client.patch(f"/api/v1/moderation/reviews/{review_id}/release", headers=headers(4))).status_code == 200
    assert (await submit(client, "review", review_id, 1, action_id)).status_code == 409
    appeal_id = created.json()["id"]
    assert (await client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=headers(2),
                               json={"decision": "upheld"})).status_code == 409
    async with sessions() as db:
        assert (await db.get(Appeal, appeal_id)).status == "pending"
        assert (await db.get(Review, review_id)).status == "released"
    # An obsolete appeal may still be closed without changing the current resource.
    assert (await client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=headers(2),
                               json={"decision": "dismissed"})).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["listing", "landlord"])
async def test_newer_penalty_cannot_be_overridden_by_an_old_appeal(workflow, kind):
    client, sessions, _, _, _ = workflow
    async with sessions() as db:
        if kind == "listing":
            (await db.get(Accommodation, 1)).status = "rejected"
        else:
            (await db.get(Landlord, 1)).verification_status = "rejected"
        await db.commit()
    action = "reject_listing" if kind == "listing" else "landlord_verification_rejected"
    old_action = await penalty(sessions, kind, 1, action)
    created = await submit(client, kind, 1, 3)
    assert created.status_code == 201
    await penalty(sessions, kind, 1, action)
    assert (await submit(client, kind, 1, 3, old_action)).status_code == 409
    assert (await client.patch(f"/api/v1/moderation/appeals/{created.json()['id']}/resolve", headers=headers(2),
                               json={"decision": "upheld"})).status_code == 409
    async with sessions() as db:
        assert (await db.get(Appeal, created.json()["id"])).status == "pending"
        resource = await db.get(Accommodation if kind == "listing" else Landlord, 1)
        assert (resource.status if kind == "listing" else resource.verification_status) == "rejected"
    # Dismissing the old appeal must not hide the newer penalty from appeal lookup.
    assert (await client.patch(f"/api/v1/moderation/appeals/{created.json()['id']}/resolve", headers=headers(2),
                               json={"decision": "dismissed"})).status_code == 200
    replacement = await submit(client, kind, 1, 3)
    assert replacement.status_code == 201
    assert replacement.json()["original_action_id"] != old_action


@pytest.mark.asyncio
async def test_concurrent_duplicate_appeals_and_decisions_are_serialized(workflow):
    client, sessions, _, _, _ = workflow
    review_id = await historical_review(sessions)
    await penalty(sessions, "review", review_id, "remove_review")
    responses = await asyncio.gather(submit(client, "review", review_id, 1), submit(client, "review", review_id, 1))
    assert sorted(response.status_code for response in responses) == [201, 409]
    appeal_id = next(response.json()["id"] for response in responses if response.status_code == 201)
    decisions = await asyncio.gather(*[
        client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=headers(2), json={"decision": decision})
        for decision in ("upheld", "dismissed")
    ])
    assert sorted(response.status_code for response in decisions) == [200, 409]
    async with sessions() as db:
        assert (await db.execute(select(func.count(ModerationLog.id)).where(ModerationLog.action.like("appeal_%")))).scalar() == 1


@pytest.mark.asyncio
async def test_legacy_quarantine_is_appealable_and_system_identity_cannot_activate(workflow):
    client, sessions, _, _, _ = workflow
    review_id = await historical_review(sessions, deleted=False, status="quarantined")
    response = await submit(client, "review", review_id, 1)
    assert response.status_code == 201
    async with sessions() as db:
        actor = (await db.execute(select(User).where(User.email == SYSTEM_EMAIL))).scalar_one()
        assert actor.role == "system" and not actor.is_active
        actor_id = actor.id
        log = await db.get(ModerationLog, response.json()["original_action_id"])
        assert log.action == "quarantined" and log.moderator_id == actor_id
    assert (await client.patch(f"/api/v1/admin/users/{actor_id}/activate", headers=headers(2))).status_code == 400
    assert (await client.get("/api/v1/appeals/my", headers=headers(actor_id))).status_code == 403


@pytest.mark.asyncio
async def test_automatic_analysis_logs_quarantine_once_and_does_not_undo_release(workflow, monkeypatch):
    client, sessions, _, _, effects = workflow
    review_id = await historical_review(sessions, deleted=False, status="pending_analysis")
    async def analyse(*args):
        return {"sentiment": "negative", "sentiment_score": 0.1, "aspects": {}, "is_toxic": True}
    async def noop(*args):
        effects.append(("pipeline", args))
    monkeypatch.setattr(review_service, "analyse_review", analyse)
    monkeypatch.setattr(review_service, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(review_service, "regenerate_accommodation_insights", noop)
    monkeypatch.setattr(review_service, "cache_delete", noop)
    monkeypatch.setattr(review_service, "cache_delete_pattern", noop)
    await asyncio.gather(review_service.process_review_nlp(review_id, "Test review"),
                         review_service.process_review_nlp(review_id, "Test review"))
    async with sessions() as db:
        assert (await db.get(Review, review_id)).status == "quarantined"
        assert (await db.execute(select(func.count(ModerationLog.id)))).scalar() == 1
        assert (await db.execute(select(func.count(ReviewNLPResult.id)))).scalar() == 1
    assert (await client.patch(f"/api/v1/moderation/reviews/{review_id}/release", headers=headers(4))).status_code == 200
    await review_service.process_review_nlp(review_id, "Test review")
    async with sessions() as db:
        assert (await db.get(Review, review_id)).status == "released"


@pytest.mark.asyncio
async def test_removed_review_cannot_be_released_and_invalidates_cached_results(workflow):
    client, sessions, _, _, effects = workflow
    review_id = await historical_review(sessions, deleted=False, status="quarantined")
    assert (await client.request("DELETE", f"/api/v1/moderation/reviews/{review_id}", headers=headers(4),
                                json={"reason": "Removed for moderation"})).status_code == 200
    assert (await client.patch(f"/api/v1/moderation/reviews/{review_id}/release", headers=headers(4))).status_code == 400
    invalidated = [key for _, args in effects for key in args]
    assert "reviews:1" in invalidated and "listing:1" in invalidated and "search:*" in invalidated


@pytest.mark.asyncio
@pytest.mark.parametrize("document", [None, "", " \t\n"])
@pytest.mark.parametrize("flow,original_status", [
    ("approve", "pending"), ("reinstate", "suspended"), ("appeal", "rejected"),
])
async def test_listing_publication_requires_document_without_side_effects(workflow, document, flow, original_status):
    client, sessions, _, _, effects = workflow
    async with sessions() as db:
        listing = await db.get(Accommodation, 1)
        listing.status = original_status
        listing.ownership_doc_url = document
        await db.commit()
    appeal_id = None
    if flow == "appeal":
        await penalty(sessions, "listing", 1, "reject_listing")
        created = await submit(client, "listing", 1, 3)
        assert created.status_code == 201
        appeal_id = created.json()["id"]
    async with sessions() as db:
        log_count = (await db.execute(select(func.count(ModerationLog.id)))).scalar_one()
    effects.clear()
    path = (f"/api/v1/moderation/appeals/{appeal_id}/resolve" if appeal_id else
            f"/api/v1/moderation/listings/1/{flow}")
    response = await client.patch(path, headers=headers(2), json={"decision": "upheld"} if appeal_id else None)
    assert response.status_code == 409
    assert response.json()["detail"] == "An ownership document must be uploaded before this listing can be published."
    async with sessions() as db:
        listing = await db.get(Accommodation, 1)
        assert listing.status == original_status and listing.ownership_doc_url == document
        assert (await db.execute(select(func.count(ModerationLog.id)))).scalar_one() == log_count
        if appeal_id:
            appeal = await db.get(Appeal, appeal_id)
            assert appeal.status == "pending"
            assert appeal.assigned_admin_id is None and appeal.resolved_at is None
    assert not effects


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", [2, 4])
@pytest.mark.parametrize("flow,original_status,action", [
    ("approve", "pending", "approve_listing"),
    ("reinstate", "suspended", "reinstate_listing"),
])
async def test_admin_and_moderator_can_publish_documented_listing(workflow, actor, flow, original_status, action):
    client, sessions, _, _, effects = workflow
    async with sessions() as db:
        listing = await db.get(Accommodation, 1)
        listing.status = original_status
        listing.ownership_doc_url = "mock://ownership.pdf"
        await db.commit()
    effects.clear()
    response = await client.patch(f"/api/v1/moderation/listings/1/{flow}", headers=headers(actor))
    assert response.status_code == 200
    async with sessions() as db:
        assert (await db.get(Accommodation, 1)).status == "approved"
        logs = (await db.execute(select(ModerationLog))).scalars().all()
        assert len(logs) == 1 and logs[0].action == action and logs[0].moderator_id == actor
    assert effects


@pytest.mark.asyncio
async def test_undocumented_listing_appeal_can_still_be_dismissed(workflow):
    client, sessions, _, _, _ = workflow
    async with sessions() as db:
        listing = await db.get(Accommodation, 1)
        listing.status = "rejected"
        listing.ownership_doc_url = None
        await db.commit()
    await penalty(sessions, "listing", 1, "reject_listing")
    created = await submit(client, "listing", 1, 3)
    assert created.status_code == 201
    appeal_id = created.json()["id"]
    response = await client.patch(f"/api/v1/moderation/appeals/{appeal_id}/resolve", headers=headers(2),
                                  json={"decision": "dismissed"})
    assert response.status_code == 200
    async with sessions() as db:
        assert (await db.get(Accommodation, 1)).status == "rejected"
        assert (await db.get(Appeal, appeal_id)).status == "dismissed"
