# Gap 2: Account deactivation and session revocation

This change builds on the activation and email-verification guards introduced in
gap 1. Account status changes now revoke previous access and refresh tokens by
incrementing `users.token_version`. Activation also revokes legacy tokens from
accounts that were inactive before session revocation was implemented.
Repeated requests for the same status do not change the token version.

No database migration is required; the token-version column was added in gap 1.
The existing protection against deactivating an administrator through the admin
API is retained. Inactive administrator accounts are still blocked by all shared
authentication guards.

The backend labels inactive, unverified, and revoked-session failures using an
`X-Auth-Error` response header exposed through CORS. Ordinary role/ownership
permission errors do not end a valid session. The frontend clears credentials,
identity state, and cached query data when a session ends. It checks account
status when the window regains focus and once per minute while visible.
Every protected backend request checks status immediately; the periodic frontend
check only controls how quickly an idle page reflects the change.

## Azure update

The user pulls new commits on the VM before Codex runs backend tests or restarts
the application. Preserve the VM-specific Compose change when pulling:

```sh
cd ~/accommodation-platform
git stash push -m "Preserve VM Compose configuration" -- docker-compose.yml
git pull --ff-only
git stash pop
```

If a conflict occurs, resolve it before proceeding. Do not overwrite SMTP,
Gemini, or other VM environment settings.

After confirming the pull, run isolated tests in Azure and restart the backend:

```sh
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py -q
docker compose up -d --no-deps --force-recreate backend
```

The tests use isolated SQLite data and captured email inside Azure's backend
image; they do not deactivate real users or send messages. PostgreSQL row-lock
behaviour is not covered by this isolated suite.

Vercel must deploy the corresponding frontend commit. Keep
`NEXT_PUBLIC_API_URL=https://api.kgotsofalangkakudi.co.za` configured.

## Browser acceptance

Use dedicated student, landlord, and moderator test accounts and a separate
administrator session, preferably in another browser profile.

1. Sign in with a test account, then deactivate it from the administrator panel.
2. Make a protected request or refocus the test account's window. It should clear
   its session and show the inactive-account message on the login page. An idle,
   visible page should detect the change within one minute.
3. Confirm login and refresh are blocked while inactive. Public browsing remains
   available as a guest.
4. Reactivate the account. Its previous access and refresh tokens must remain
   rejected; a fresh login must succeed.
5. Repeat for the other test roles. Confirm student activation does not bypass
   email verification.
6. Confirm that attempting an administrator-only action as a student, landlord,
   or moderator returns a permission error without logging out the active user.
7. Confirm verification and password-reset pages keep their email links when an
   unrelated stored session is rejected.

Gap 2 remains pending until the Azure tests and browser acceptance checks pass.
