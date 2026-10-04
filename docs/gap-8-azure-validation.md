# Gap 8: enquiries, replies and working frontend actions

## Private landlord enquiries

`POST /api/v1/accommodations/{id}/enquiries` accepts only verified, active
students and approved listings with an active landlord account. The backend
resolves the owner's registered email. Neither recipient nor Reply-To can be
specified by the client; unknown fields are rejected. The message must contain
20–3000 characters after trimming, and consent must be true. The popup explains
that the student's name and verified email will be shared with the landlord.

SMTP uses the existing configured AccomFind sender, the landlord as To, and the
verified student email as Reply-To. The plain-text body includes the listing
title/link, student name/email and enquiry. Responses never expose landlord
email, phone, SMTP diagnostics or configuration. No schema change or additional
environment variable is needed.

An `Idempotency-Key` UUID is required. Atomic Redis Lua scripts allow one enquiry
per student/listing per minute and five attempts per student per hour across
all listings. SMTP failures consume an attempt. Successful request IDs can be
replayed without sending again for 24 hours. Reusing an ID with different content
returns 409. Redis failure prevents sending; 429 includes Retry-After, exposed
through CORS. Redis stores only IDs, counters, message hashes and attempt states,
never message text or recipient addresses. These keys expire automatically.

SMTP acceptance does not guarantee inbox delivery. SMTP and Redis cannot commit
atomically: pending requests are retained for 24 hours after a crash or unknown
result, and no automatic delivery retry is performed. The frontend preserves
the request ID on an unknown network outcome so retrying can detect a completed
send. Delivery failures show a clear message and a one-minute wait before a new
attempt. There is no durable enquiry queue or in-app conversation history.

## Replies, activity and navigation

Only the owning landlord sees the reply form. The backend accepts replies only
on published, non-deleted reviews, trims/validates 10–3000 characters, locks the
review to serialize concurrent submissions, preserves the existing one-reply
database constraint and invalidates the review cache after commit. Responses
are public; the form explains that before submission.

`GET /api/v1/moderation/log?mine=true` counts and paginates the authenticated
moderator/admin's own actions. The default global log remains unchanged. Output
includes moderator_id, ordering is stable, and profiles use total/items rather
than treating the response as an array. Admins also receive the activity panel.

Homepage footer links lead to existing search, account, dashboard/recovery routes
or real homepage anchors. Placeholder company/legal links and social icons with
no destinations are removed. No legal policy text or social accounts are invented.

## Azure regression suite

After the user pulls, run:

```sh
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py tests/integration/test_guest_access.py tests/integration/test_resource_permissions.py tests/integration/test_private_documents.py tests/integration/test_review_resubmission.py tests/integration/test_appeal_workflow.py tests/integration/test_enquiries_and_ui_actions.py -q --tb=short
```

The new tests reuse disposable PostgreSQL/PostGIS schemas, prefix every Redis
Lua key with a unique `test_gap8_<uuid>:` namespace, and remove only those keys
afterward. SMTP is mocked, including the actual From/To/Reply-To construction.
No test writes production rows/Redis keys, sends email, or contacts blob/NLP
providers. After passing tests, rebuild/restart the backend; no migration is needed.

## Browser acceptance

1. As a verified student on your disposable test listing, open Contact landlord.
   Sending requires a meaningful message and the consent checkbox.
2. Confirm your test landlord receives the enquiry with the correct listing,
   student email/name and message. Reply must target the student's email.
   The student's browser must never receive the landlord email/phone.
3. An immediate second enquiry must be limited. Duplicate requests are covered
   by the isolated concurrency tests. Guests must sign in; other roles cannot
   send student enquiries.
4. As the listing's owner, post one response under a published review. It appears
   immediately and the form disappears. Other landlords have no reply control.
5. As moderator/admin, check Profile shows your personal action total and recent
   actions, including totals larger than a single page.
6. Click the homepage footer links and verify route/anchor destinations.

Approve this gap after browser checks before moving to the next gap.
