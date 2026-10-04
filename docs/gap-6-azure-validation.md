# Gap 6: one current review with preserved deletion history

## Rule

A student may have exactly one non-deleted review per listing. Analysed,
released, pending-analysis and quarantined rows all block another submission.
Deleting their review starts the existing 14-day cooldown. After it expires,
the student may submit a new row with a new review ID. Old text, replies,
analysis and moderation/appeal references remain attached to the old row.
Deleted rows never appear in public review results. Moderator removal retains
its existing cooldown behaviour; this gap does not redesign moderation rules.

The `reviews` table and its columns are preserved. Migration `c3f6a9b2d5e8`
replaces the lifetime uniqueness constraint with a partial unique index on
`(student_id, accommodation_id) WHERE deleted_at IS NULL`, retaining its name
`uix_student_accommodation_review`. The database itself rejects a second active
row, regardless of frontend checks.

Submission/deletion and appeal restoration serialize on the student profile.
Restoring an old review when a newer active review exists returns `409` and
leaves the appeal pending. Unique-index conflicts during submission return a
clear `409`. Eligibility checks use the latest cooldown across historical rows.

The frontend disables “Write a review” until the server confirms eligibility,
including when an existing review is not publicly visible yet. It displays
cooldown deadlines in the browser's local time. Stale/open forms are still
subject to backend enforcement.

## Azure regression tests

After manually pulling the pushed commit:

```sh
cd ~/accommodation-platform
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py tests/integration/test_guest_access.py tests/integration/test_resource_permissions.py tests/integration/test_private_documents.py tests/integration/test_review_resubmission.py -q --tb=short
```

The new review tests use actual PostgreSQL/PostGIS in disposable schemas named
`test_gap6_<random hex>`. Every connection searches that isolated schema before
`public`, and the fixture verifies the current schema before creating tables.
Schemas are dropped on completion. No production rows are changed; NLP, mail,
blobs and Redis side effects are mocked. Tests exercise the actual migration,
the database constraint, cooldown boundaries, historical reply/analysis
preservation, public visibility and concurrent HTTP requests.

## Deployment

1. Confirm the regression suite and frontend production build pass.
2. Build the backend image, briefly stop backend writes and take/verify a private
   PostgreSQL backup.
3. Run `docker compose run --rm --no-deps backend alembic upgrade head`.
4. Verify the index is unique with predicate `deleted_at IS NULL`, and that
   review row counts are unchanged. Restart the backend and confirm health.

The migration changes no review data. Downgrade refuses to restore the lifetime
constraint when multiple historical rows exist for a pair, rather than deleting
history. Keep backups and do not attempt a destructive downgrade.

## Browser acceptance

Use a verified student and a disposable approved listing.

1. Submit a review: the write button becomes disabled. A pending or quarantined
   review must also prevent another submission.
2. When published, only that student's one current review appears for the listing.
   A direct repeated submission returns `409`.
3. Delete it from the profile, then return to the listing: it disappears from
   public reviews and the write button shows the cooldown deadline.
4. Verify expired-cooldown resubmission through isolated tests or an existing
   eligible test account; do not shorten real students' cooldowns for testing.
5. Moderator/admin appeal restoration works when no replacement review exists.
   If a newer active review exists, restoration is blocked without resolving the
   appeal or altering either review.

Approve this gap after these checks before starting gap 7.
