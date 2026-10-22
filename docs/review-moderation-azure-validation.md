# Review moderation: first stage

## Behaviour

New reviews start as `pending_analysis`. Gemini must return separate strict
`is_spam` and `is_toxic` booleans, recognised sentiments and bounded confidence
values. Either flag sends the review to quarantine and records an automatic
moderation action; only a valid clear result publishes it. The existing
`spam_flag` column stores the combined moderation flag: no schema migration.
Provider failures, quota exhaustion and invalid/incomplete structured output
leave the review pending. The complete review is analysed rather than dropping
text beyond 2,000 characters. The provider call runs outside the event loop.

Profane/abusive wording, including misspellings, should be flagged for human
review. Ordinary negative criticism is allowed. Prompt/schema tests verify the
contract, not the accuracy of the external model; a real provider smoke check
and moderator oversight remain necessary.

Public reviews and derived metrics now require either explicit `released`
status, or `analysed` status without an NLP moderation flag, and no deletion.
An inconsistent historical `analysed` + `spam_flag=true` row stays in the
database but is excluded from new public review lists, ratings, discovery,
activity, analytics and reports. Human releases are retained. Saved management
reports are immutable and keep their original snapshots.

Public-data Redis entries use an internal versioned namespace so cached data
from the old publication rule is never served after deployment. Existing
logical invalidation keys are retained. View buffers, authentication keys and
private documents are unaffected. Stored legacy insight wording is rebuilt
without external AI on its next authorised read; newly built topic insights
carry the publication-policy version. Visibility changes still refresh
derived figures immediately.

Immediate insight refresh uses local templates, not extra Gemini requests.
The fortnightly AI-written summary job is deliberately the next stage after
this review/moderation stage is validated. It is not scheduled in this commit.

## Historical review audit

Do not silently reclassify or delete existing reviews. Review 174 previously
received a false moderation flag, so a new prompt cannot retroactively hide it.
The inconsistent flagged rows 169, 158 and 156 also need their historical actions
checked before correcting their statuses or moderator queue placement.

Read-only audit in the VM:

```sql
SELECT resource_id AS review_id, action, reason, created_at
FROM moderation_log
WHERE resource_type = 'review' AND resource_id IN (174, 169, 158, 156)
ORDER BY resource_id, created_at;
```

## Cloud Shell validation

Pull main as usual, preserving the VM Compose configuration. Build without
restarting the live backend, then execute:

```bash
docker compose build backend
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py tests/integration/test_guest_access.py tests/integration/test_resource_permissions.py tests/integration/test_private_documents.py tests/integration/test_review_resubmission.py tests/integration/test_appeal_workflow.py tests/integration/test_enquiries_and_ui_actions.py tests/integration/test_published_metrics.py tests/integration/test_auth_rate_limits.py tests/integration/test_management_reports.py tests/integration/test_review_moderation_pipeline.py -q --tb=short
```

Tests use mocked providers and disposable PostgreSQL schemas. They do not send
real review text to Gemini, change production rows or send email. New coverage
checks toxicity independent of spam, quota/invalid responses, publication,
quarantine, moderator release, public metrics, retired caches, safe stored
insight refresh and zero Gemini summary calls during immediate refresh.

After passing tests, a single real-provider smoke call can check the revised
prompt without saving or publishing a review. It consumes one Gemini request:

```bash
docker compose run --rm --no-deps backend python -c 'import asyncio; from app.services.nlp_service import analyse_review; r=asyncio.run(analyse_review(0, "The wifi is complete shit, this pigsty wasted my fucken funds.")); print({k: r.get(k) for k in ("is_toxic", "moderation_reason")} if r else "No analysis returned; do not treat as clear")'
```

Expect `is_toxic: True`. A missing result or false result requires investigation,
not a claim that the model has passed. Do not submit this text as a real public
review. A separate ordinary negative complaint should remain clear.

Only after validation:

```bash
docker compose up -d --no-deps backend
```

Browser acceptance: flagged submissions enter the moderation queue; clear
negative complaints can publish; pending/quarantined reviews stay hidden;
moderator release makes a review visible; new topic/rating figures refresh
without Gemini opinion calls. No production history cleanup or database
migration is included.
