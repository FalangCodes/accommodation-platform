# Gap 1: Azure deployment and validation

Email verification for students and password recovery are implemented in this
development copy. Backend acceptance testing must take place in the Azure
environment. No Azure deployment or application database migration has been
performed by Codex.

## Configuration

Configure the following in the Compose environment file on the Azure host
(normally the root `.env`, or the file supplied with `docker compose --env-file`).
Keep credentials out of version control.

```dotenv
FRONTEND_URL=https://your-frontend-domain
SMTP_HOST=your-smtp-host
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=your-verified-sender@example.com
SMTP_STARTTLS=true
SMTP_SSL=false
```

For implicit TLS on port 465, use `SMTP_SSL=true` and `SMTP_STARTTLS=false`.
`FRONTEND_URL` must point to the frontend that contains the new verification and
reset pages. The example URL is a placeholder, not a configured deployment.
Both frontend and backend changes must be deployed for the links to work.

## Deploy the backend

Use the existing project directory on the Azure host. Back up the application
database using your normal backup procedure before migrating. Stop the backend
while applying the migration so the old application does not create tokens or
users against a changing schema. Leave the database and Redis running.

```sh
docker compose stop backend
docker compose build backend
docker compose run --rm --no-deps backend alembic upgrade head
docker compose up -d --no-deps backend
```

The new Alembic head is `b2d5e8f1a4c7`. It adds `users.token_version` and
`auth_email_tokens`. It does not mark existing users verified or activate them.
Deploy the frontend with the normal frontend deployment process; this repository's
root Compose file does not define a frontend service.

## Existing student accounts

All students with no `email_verified_at` must verify their institutional mailbox.
They can request an email from `/verify-email`. Students whose `is_active` flag is
already false must also be activated by an administrator after review. Email
verification and password reset never activate an account. This avoids treating
an administrator suspension as an unfinished verification.

## Automated checks on Azure

Run inside the backend container, which installs the pinned requirements:

```sh
docker compose exec backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py -q
```

The integration tests use isolated SQLite data and captured email, so they do not
modify the application database or send real messages. They cover API behaviour,
including expiry, single use, throttling, invalidation, and delivery failures.
They do not validate PostgreSQL row locking or external SMTP delivery.

The local Windows virtual environment failed password hashing because its bcrypt
installation is incompatible with passlib. The project's requirements pin
`bcrypt==4.0.1` with `passlib==1.7.4`. The local results therefore do not establish
that these backend flows pass on Azure.

## Browser acceptance checklist

Use dedicated test accounts and disposable test passwords.

1. Register a student using a recognised institutional mailbox. Expect a check
   your email page, no automatic login, and a verification email.
2. Attempt login before verification. Expect a verification-required error.
3. Open the email link. Expect automatic verification without entering an email
   or pressing a verification button, followed by confirmation and a **Sign in**
   button. Reusing the same link must fail. Missing/expired links show the resend
   form; temporary failures offer a manual retry.
4. Request another verification email twice within a minute. At most one new
   email should be sent. At most three emails per account and purpose are issued
   per hour; a newly issued link replaces the previous link.
5. Confirm an expired verification link is rejected after 24 hours. Test expiry
   using controlled test data rather than changing production clocks.
6. Request a password reset. Known and unknown email addresses must receive the
   same on-screen response. Only an existing account should receive an email.
7. Open the reset link, enter matching new passwords, and submit. Expect success.
   The old password and existing access/refresh tokens must stop working. The new
   password must work. Reusing the link must fail.
8. Confirm reset links expire after 30 minutes and that a verification token
   cannot be used as a reset token, or vice versa.
9. Verify an inactive test student. Its account must remain inactive. Password
   reset must also leave its activation and verification status unchanged.
10. Check password recovery for landlord, moderator, and administrator test
    accounts. Landlord identity/document verification remains a separate process.

Do not consider gap 1 accepted until these checks pass on Azure. Gap 2 remains
pending approval, although activation enforcement was necessary here to keep
verification and suspension separate.
