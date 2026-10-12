# Authentication rate limiting

No database schema changes. Existing enquiry limits remain unchanged.

| Budget | Window | Per IP | Per address |
|---|---|---|---|
| Sign-in attempts | 15 minutes | 60 total attempts | 5 failed sign-ins |
| Registration, shared across student/landlord/moderator | 1 hour | 10 | 3 |
| Verification/resets email requests, combined | 1 hour | 30 | 5 |
| Verification/password-reset token submissions, combined | 15 minutes | 30 | — |
| Refresh requests | 1 minute | 180 | — |

Account sign-in limits count failed sign-ins, including unknown accounts. Each
request reserves a slot before credential checking so concurrent attempts cannot
bypass the cap. A successful sign-in clears the account counter, while the IP
counter remains. Other budgets count successful and unsuccessful attempts.
Redis Lua checks and increments all budgets atomically. Normalised addresses and
IPs are represented by keyed hashes; passwords, tokens and raw addresses are not
stored in limiter keys. Limits expire automatically. Blocked requests return 429
with a human-readable message and `Retry-After` seconds. Redis failure returns
503 with a 60-second retry indication, before authentication side effects.
Existing `/auth/me` sessions do not require the rate-limit service.

## Azure proxy deployment

1. Pull normally, preserving the VM's existing Compose changes.
2. Run isolated tests before deploying:
   `docker compose run --rm --no-deps backend python -m pytest tests/integration/test_auth_rate_limits.py -q --tb=short`
   and the existing unit/integration regression suite.
3. Determine the backend Docker network's gateway. Set the root `.env` variable
   `AUTH_TRUSTED_PROXY_IPS` to that exact peer IP (currently `172.18.0.1`). Do not
   use `*` or a broad public/network range. This setting passes through Compose.
4. Confirm the effective backend mapping is `127.0.0.1:8000:8000`, with Uvicorn
   `--no-proxy-headers`. Nginx is the public API entry point. This prevents clients
   connecting directly and impersonating the trusted proxy. Preserve Nginx TLS
   and `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`.
5. Rebuild/recreate backend. Inspect effective mapping, command and proxy setting
   without printing other environment values. Verify HTTPS health and CORS.

The app uses the final address appended by a trusted Nginx peer. It ignores
forwarded headers from other peers. Without configured proxies it safely counts
by the peer address, which could group all proxied visitors together.
Do not make production login/reset requests repeatedly for deployment tests:
the integration tests use private Redis prefixes and isolated SQLite records,
and capture mail without contacting SMTP.

## User checks

Using a test account, repeat an incorrect password until the sign-in budget is
exhausted after five failures. The sixth attempt shows a wait message. A correct password during that
window is also throttled; it works after the window expires. Successful sign-in
before exhausting the budget resets the account failure count. Email pages show a
wait message when their combined request budget is exhausted. Temporary refresh
throttling/outages preserve browser tokens and permit a later retry.

The per-IP budgets allow normal shared-campus use but may need tuning based on
traffic. These limits reduce abuse; they do not replace MFA or perimeter DDoS
protection. Do not clear production limiter keys as part of deployment.
