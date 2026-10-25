# Shared Gemini quota handling

All Gemini review analysis and optional AI opinion calls use one Redis admission
gate. A 429 / RESOURCE_EXHAUSTED response starts a conservative 24-hour pause
from that failure; this is our policy, not a claim about Google's quota reset.
No new Gemini request is sent during that pause. Reviews remain pending and
hidden, including submissions arriving during the pause.

The gate allows one request in flight, with at least 13 seconds between its
completion and the next request. Busy/paced submissions remain pending for the
scheduled sweep. The SDK has one attempt and a 60-second timeout; application
scheduling owns retries. Temporary provider failures use shared exponential
backoff from 60 seconds up to 15 minutes, reset after a successful provider call.

The existing sweep still wakes every ten minutes. While quota/backoff is active
it skips the database scan and provider entirely. Otherwise it considers at most
100 non-deleted pending reviews, oldest first, and stops the batch if a pause
starts. A failed provider response never clears a review for publication.

Cooldown state survives backend restarts in Redis. Redis must remain available:
if admission storage cannot be read, calls are deferred. A local fallback retains
a quota decision if its Redis write briefly fails and republishes it on recovery.
Losing both Redis state and the backend process loses that fallback; Redis
durability is an infrastructure concern, not a new database migration here.

Immediate topic refreshes continue to use local wording. The fortnightly summary
schedule is still a separate, unimplemented stage. Future AI callers should use
`gemini_gateway.generate_content` so they share quota/pacing with reviews.

## Azure checks

After preserving VM Compose edits and pulling main, build without restarting:

```bash
docker compose build backend
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_gemini_quota.py tests/integration/test_appeal_workflow.py tests/integration/test_review_resubmission.py tests/integration/test_review_moderation_pipeline.py -q --tb=short
```

The new tests use real Redis Lua in unique `test_gemini_<uuid>:` namespaces and
mocked Gemini responses. They never consume real quota, change live reviews, or
delete production Redis keys. They check concurrent calls, shared quota expiry,
backend restart behaviour, temporary backoff, Redis outages, quota write recovery,
summary fallback, and stopping/skipping the sweep. Existing structured-output
unit tests isolate their provider; quota integration tests exercise the real gate.

After passing tests:

```bash
docker compose up -d --no-deps backend
docker compose exec -T backend python -c 'import asyncio; from app.services.gemini_gateway import pause_seconds; print("Gemini shared pause remaining (seconds):", asyncio.run(pause_seconds()))'
```

The diagnostic sends no request to Gemini. A zero pause does not mean an unlimited
budget: admission still serializes and spaces requests. A real quota failure logs
one 24-hour pause decision; subsequent submissions remain pending without calling
the provider. No historical review reanalysis or database structure change occurs.
