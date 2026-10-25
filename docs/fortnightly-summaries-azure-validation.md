# Fortnightly written accommodation summaries

No database migration. Scheduling, writing dates, retry state and source-review
IDs live inside each topic's existing `accommodation_insights.insights` JSON.
Private source/retry metadata is omitted from the insights API response.

The scheduler checks two minutes after backend startup, then hourly. A property's
first eligible summary can be written on that check. Subsequent successful
summaries become eligible fourteen days later. Only approved properties with
published reviews and enough topic evidence are considered. All available topics
are generated in one structured Gemini call per property, including proportionate
landlord recommendations. Unchanged evidence reuses its existing wording without
another API request; the displayed writing date remains truthful.

Counts, topic figures and evidence update immediately. Safe saved wording is
retained between runs, with its date and source-review count shown in the frontend.
If a source review is removed or becomes unpublished, local regeneration drops
that saved wording/advice immediately and uses current template wording. No source
review is deleted, reclassified or sent for reanalysis by this job.

## Retry and concurrency policy

- Review analysis has priority: pending review work defers summaries.
- The existing shared Gemini gate spaces requests and enforces the 24-hour quota
  pause. No summary call bypasses it, and SDK automatic retries remain disabled.
- A property with a failed/invalid batch retains safe saved wording, with retries
  after 1, 2, 4, 8, 16 and then at most 24 hours. A quota response waits at least
  the shared quota pause. Hourly checks may run slightly after the eligibility time.
- Deferred admission (busy gate/Redis outage) is not counted as an API attempt.
- One Redis job lease prevents duplicate scheduler runs, renews between properties,
  and expires after a crash. Each check makes at most ten property attempts.
- No insight lock is held during Gemini calls. Source IDs and aggregate signatures
  are checked again before saving; changed evidence discards the generated batch.
- Cancellation retains the Gemini request lease because cancelling a worker thread
  does not stop its HTTP request. The lease expires rather than admitting overlap.
- Backend restarts retain schedules/retries in PostgreSQL JSON. Shared quota state
  retains the Redis durability limits documented in the quota validation guide.

## Validate on Azure before restarting

Preserve VM Compose changes and pull main, then:

```bash
docker compose build backend
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_scheduled_summaries.py tests/integration/test_gemini_quota.py tests/integration/test_published_metrics.py tests/integration/test_review_moderation_pipeline.py tests/integration/test_appeal_workflow.py tests/integration/test_review_resubmission.py tests/integration/test_guest_access.py tests/integration/test_resource_permissions.py -q --tb=short
```

Tests use disposable PostgreSQL schemas, private Redis namespaces and mocked
Gemini responses. They consume no real quota and modify no production reviews.
Coverage includes fortnight boundaries, unchanged evidence, live additions,
source removals, stale in-flight snapshots, invalid output, retained wording on
failure, retry recovery, quota pauses, review priority and concurrent job runs.

After tests pass:

```bash
docker compose up -d --no-deps backend
docker compose logs --since 10m --no-color backend 2>&1 | grep -E '\[Summaries\]|\[Gemini\]|Scheduler started'
```

The scheduler will use real Gemini quota for eligible work after startup. There
is no need to invoke a second manual generation command. Review backlog, cooldown
or lack of sufficient topic evidence can defer the first written summaries.

Browser acceptance: student insights and landlord analytics show a writing date
and source-review count once a summary exists. Current review figures may be newer
than that text. Template fallbacks do not pretend to have an AI writing date.
The existing server-generated management report snapshots are unaffected.
