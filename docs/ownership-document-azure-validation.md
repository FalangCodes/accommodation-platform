# Ownership document publishing guard

Approval, reinstatement and an upheld listing appeal now require a nonblank ownership document reference. A missing reference returns HTTP 409 with a readable message. Existing approved listings are not changed by deployment; historical records require a separate decision and data cleanup.

This change adds no migration or database constraint. It checks the recorded reference, not the contents or availability of a stored file. Moderators must still open and inspect the uploaded evidence. The isolated, explicitly opted-in demo seed remains synthetic fixture data, not a real ownership verification workflow.

## Azure validation

After pulling main while preserving the VM's Compose edits, run from `~/accommodation-platform`:

```bash
docker compose build backend
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration -q --tb=short
```

The additional cases are in `tests/integration/test_appeal_workflow.py`. They use disposable PostgreSQL schemas, fake document references and mocked cache effects; no live listing, uploaded file or external provider is changed.

Coverage includes all three publishing paths with null, empty and whitespace-only references; unchanged status, audit log and pending appeal after refusal; publishing documented listings as admin/moderator; documented listing appeals; and dismissal without publishing.

Only after tests pass, recreate the backend:

```bash
docker compose up -d --no-deps backend
```

No Alembic command is required for this change. Vercel must deploy the frontend commit to show the specific errors in approval/reinstatement screens. The appeal screens already display server error messages.

## Manual checks

- Attempt to approve an undocumented listing: expect the ownership-document message and no status change.
- Attempt to reinstate an undocumented suspended listing: expect the same refusal.
- Uphold an undocumented listing appeal: expect refusal, with the appeal still pending. Dismissing the appeal remains allowed.
- A listing with an uploaded document can proceed through the normal moderation decision.

Uploading a document sends a listing into `pending` for moderation under the existing upload flow. It does not automatically publish the listing or grant an appeal. Previous penalties/appeals must still pass their existing current-state checks.

Do not suspend, remove or seed historical live listings as part of running these checks. Deciding what to do with existing live records missing documents is a separate operation.
