# Gap 7: moderation and appeals

Only admins can list and resolve pending appeals. Moderators continue to approve,
reject, remove and release content, and verify landlords. The moderation panel
shows the Appeals tab only for admins. The admin dashboard links to that panel.

Appeals must reference the latest action on the owned resource, and that action
must still be an applicable penalty: review quarantine/removal, listing
rejection/suspension/removal, or landlord verification rejection. Positive actions
cannot be appealed. Owner and resource row locks prevent duplicate concurrent
appeals and serialize decisions with moderation. An outdated appeal can be
dismissed, but upholding it returns 409 without changing the appeal or resource.

Upholding restores a review to released, a listing to approved, or landlord
verification to verified (including verified timestamp, ID verification and
cleared rejection reason). Review restoration still cannot create a second active
review for the same student/listing. Decisions and resource changes commit
together, and affected caches are cleared afterward. Listing audit entries use
the existing `accommodation` resource type consistently.

Automatic NLP quarantine records a moderation action under a dedicated inactive
system identity. That identity has a random unknown password, no access role and
cannot be activated or authenticated. Concurrent pipeline retries cannot duplicate
the quarantine or overwrite a moderator's release/removal. Existing quarantines
without an action are recorded when their author requests an appeal. This requires
no database schema migration; all existing tables and columns remain unchanged.

Students and landlords see their own appeal status in the profile. Rejected
landlord verification can be appealed there; listing appeal buttons cover
rejected, suspended and removed listings. Admins see the original action and
reason beside the appeal reason.

## Azure validation

After the user pulls:

```sh
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py tests/integration/test_guest_access.py tests/integration/test_resource_permissions.py tests/integration/test_private_documents.py tests/integration/test_review_resubmission.py tests/integration/test_appeal_workflow.py -q --tb=short
```

Workflow tests reuse the isolated PostgreSQL/PostGIS schemas from gap 6. The
application's database sessions are overridden, and NLP, cache and insight side
effects are mocked. Tests never change production rows or contact email/blob/NLP
providers. Only after tests pass, rebuild and restart the backend. No Alembic
migration is needed.

## Browser acceptance

Use disposable test resources and separate student, landlord, moderator and admin
accounts.

1. As moderator, confirm normal moderation works and no Appeals tab appears.
2. As student, appeal a quarantined or moderator-removed review from the profile.
   Its appeal appears as pending under My appeals. A duplicate is rejected.
3. As landlord, appeal a rejected verification or rejected/suspended/removed
   listing from the profile.
4. As admin, open `/moderation`, review the original action and appeal reasons,
   and uphold an appeal. Refresh the owner's profile to confirm restored state
   and upheld status. Dismiss another and confirm its resource stays unchanged.
5. For a pending appeal, make a newer moderation decision, then try upholding the
   older appeal. It must show a conflict and remain pending until dismissed.
6. The existing one-active-review rule remains enforced during restoration.

Automatic quarantine, pipeline retries, concurrent requests and stale actions are
covered by isolated tests; do not alter production cooldowns or histories to test.
