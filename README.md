# AccomFind

A student accommodation discovery and review platform, developed around Sol Plaatje University in Kimberley, South Africa.

Students discover listings, publish moderated reviews and contact landlords through private email enquiries. Landlords manage listings, inspect feedback and generate management reports. Moderators review listings and flagged content; administrators manage users, universities, appeals and platform reports.

## Current architecture

- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS, TanStack Query, Leaflet and Recharts.
- **Backend:** Python 3.11, FastAPI, SQLAlchemy and Alembic.
- **Database:** PostgreSQL 15 with PostGIS for campus-distance searches.
- **Redis:** caching, view buffers, request limits and shared Gemini admission control.
- **Gemini:** structured review sentiment, topic and spam/toxicity analysis; scheduled property wording.
- **Azure Blob Storage:** listing photos and private verification documents.
- **SMTP:** verification, password reset and landlord enquiry delivery.
- **Reporting:** saved management report snapshots and generated PDF documents.
- **Scheduling:** APScheduler inside the backend. The old Hugging Face service and Celery worker have been retired.

The deployed frontend uses Vercel. The backend runs on an Azure VM behind an HTTPS reverse proxy. Production proxy/TLS settings are configured separately from the development Compose file.

```text
Browser -> Next.js -> FastAPI -> PostgreSQL / PostGIS
                         |----> Redis
                         |----> Gemini
                         |----> Azure Blob Storage
                         |----> SMTP
```

## Repository

```text
backend/app/          API routes, models, services and scheduled jobs
backend/alembic/      Database migration history
backend/tests/        Unit and isolated integration tests
frontend/src/         Pages, components, authentication and API client
frontend/public/      Application assets
docs/                 Operational notes and validation guides
docker-compose.yml    Development database, Redis and backend services
```

## Requirements

- Docker with Docker Compose v2.
- Node.js 22 and npm for the frontend. The installed Next.js version requires Node.js 20.9 or newer.
- Gemini, SMTP and Azure Storage credentials for the corresponding integrations.

The frontend and API can run locally, but email delivery, real AI analysis and hosted uploads still require their external services. Missing Gemini configuration leaves reviews pending. SMTP is needed for normal email registration/reset flows; isolated demo accounts are available through the guarded seed utility.

## Fresh local setup

These steps are for a new installation. Preserve the existing `.env`, encryption key, database volume and VM configuration when updating an existing deployment.

1. From the repository root, copy the Docker configuration example:

   ```bash
   cp .env.example .env
   docker compose build backend
   ```

2. Generate separate random values for `SECRET_KEY` and `MODERATOR_INVITE_KEY` by running the first command twice. Generate `ENCRYPTION_KEY` with the second command. Put the values in the private root `.env` file:

   ```bash
   docker compose run --rm --no-deps backend python -c "import secrets; print(secrets.token_urlsafe(48))"
   docker compose run --rm --no-deps backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   The encryption key protects stored identity information. Keep the original key with backups of an existing database.

3. Configure the integrations you need:

   | Variable | Purpose |
   |---|---|
   | `FRONTEND_URL` | Frontend origin for CORS and email links; locally `http://localhost:3000` |
   | `GEMINI_API_KEY` | Review analysis and scheduled summaries |
   | `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage access |
   | `AZURE_STORAGE_CONTAINER_NAME` | Listing photo container |
   | `AZURE_DOCUMENT_CONTAINER_NAME` | Private verification document container |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Email delivery |
   | `SMTP_STARTTLS`, `SMTP_SSL` | Select the transport supported by your email provider |
   | `AUTH_TRUSTED_PROXY_IPS` | Exact trusted proxy peers for deployed request limits; blank locally |

   Verification document containers must be private. Credentials belong in environment files, not source control. `backend/.env.example` is for native Python execution; Docker Compose reads the repository-root `.env` instead.

4. Start the infrastructure and check that PostgreSQL accepts TCP connections:

   ```bash
   docker compose up -d db redis
   docker compose exec db pg_isready -h 127.0.0.1 -U postgres -d accommodation_db
   ```

   Wait for a successful readiness result before continuing.

5. Apply the existing migrations and start the API:

   ```bash
   docker compose run --rm --no-deps backend alembic upgrade head
   docker compose up -d --no-deps backend
   ```

   API health: <http://localhost:8000/health>. Interactive API documentation: <http://localhost:8000/docs>.

   The legacy `init_db.py` command is disabled. It opens no database connection and cannot reset tables. Database evolution uses Alembic.

6. In another terminal, start the frontend:

   ```bash
   cd frontend
   cp .env.example .env.local
   npm ci
   npm run dev -- --webpack
   ```

   Open <http://localhost:3000>. Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local`; omit the `/api/v1` suffix. This explicit setting matters because the current API client falls back to the hosted API when the variable is absent.

   The Webpack development command is the locally validated preview path. The normal `npm run build` command is used for production builds.

## Demo data and roles

[Safe demo seeding](docs/legacy-cleanup-azure-validation.md#demo-data-for-a-separate-empty-database-only) requires an explicit `--demo` flag, a supplied password and an empty application database. It creates clearly marked synthetic listings and example.com landlord/student accounts. It makes no AI or email calls and leaves all reviews pending for the real analysis pipeline.

Normal student registration requires an institutional `.ac.za` email and email verification. Landlords submit verification documents, and moderators review them. Seeded demo verification is fixture data, not evidence of real identity verification.

### First administrator: operator-only bootstrap

There is no public admin registration. A database operator can promote one existing, active, email-verified account. On an isolated demo installation, `demo.student.1@example.com` can be used; a real deployment must use the intended verified operator account.

Open the database console using the credentials for that installation:

```bash
docker compose exec db psql -U postgres -d accommodation_db
```

Run the following with the intended account email:

```sql
BEGIN;
UPDATE users
SET role = 'admin', token_version = token_version + 1
WHERE lower(email) = lower('demo.student.1@example.com')
  AND is_active IS TRUE
  AND email_verified_at IS NOT NULL
  AND role IN ('student', 'landlord')
RETURNING id, email, role;
```

Verify that exactly the expected account was returned, then run `COMMIT;`; otherwise run `ROLLBACK;`. Sign in again after promotion. Admins can create moderator accounts through **Admin -> User management**. The database credentials in the supplied development Compose file are local defaults, not a production credential policy.

## Review analysis and scheduled wording

1. A submitted review starts hidden as `pending_analysis`.
2. A valid Gemini result publishes a clear review or quarantines flagged content for human moderation.
3. Provider errors and incomplete results leave the review pending. New submissions and retries share request pacing; a quota response pauses Gemini requests for 24 hours under the application's conservative policy.
4. The ten-minute sweep retries eligible pending reviews. Ratings, counts and topic evidence update when review visibility changes.
5. Written property summaries and advice become eligible every fourteen days. An hourly job checks due properties, prioritises pending review analysis and uses one structured call per property.
6. Saved wording records its writing date and source-review count. Unchanged evidence can reuse that wording without another call. Removed source reviews invalidate dependent wording immediately.

Moderator removal retains a review in the author's private history with the removal reason and appeal option. Admin appeals include the original review for decision context. Published metrics exclude removed/quarantined reviews; a moderator can explicitly release a quarantined review.

## Validation

Backend checks are run on Azure in this project's workflow. From the project root on the VM:

```bash
docker compose build backend
docker compose run --rm --no-deps backend python -m pip check
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration -q --tb=short
```

Integration tests use disposable database schemas or isolated test databases and private Redis namespaces. Provider/email responses are mocked. They do not seed live data or consume real Gemini quota. Bootstrap regression checks execute the migration revisions in a fresh disposable schema and check PostGIS ownership.

Frontend checks, from `frontend/`:

```bash
npx tsc --noEmit
npx eslint --max-warnings 0
node --test tests/session.test.mjs
npm run build
```

Frontend verification covers strict lint, TypeScript, mocked session/error tests, production builds and targeted browser scenarios. The two known backend dependency deprecation warnings do not currently fail tests. Migration-body checks are separate from an end-to-end deployment rehearsal.

## Existing Azure / Vercel deployment

- Back up the database, uploaded files and required private environment values separately; Git contains source code, not the live database or storage account.
- Pull the approved main branch while preserving the VM's local Compose configuration.
- Build and test before recreating the backend. The deployment notes in `docs/` cover individual changes.
- Use HTTPS for a hosted API called by the Vercel frontend. Set Vercel's `NEXT_PUBLIC_API_URL` before building, and set the backend's `FRONTEND_URL` to the public frontend origin.
- Follow [trusted proxy configuration](docs/auth-rate-limit-azure-validation.md) for accurate request limits behind the VM proxy.
- Stopping the backend stops its in-process scheduler. Due summary dates remain stored, and a new summary check is scheduled after startup.

## Handover notes

The current source and validated behaviour take precedence over historical implementation notes. Earlier documents may describe the retired Hugging Face/Celery architecture. Useful guides include:

- [Review moderation](docs/review-moderation-azure-validation.md)
- [Shared Gemini quota handling](docs/gemini-quota-azure-validation.md)
- [Fortnightly summaries](docs/fortnightly-summaries-azure-validation.md)
- [Management reports](docs/management-reports-azure-validation.md)
- [Legacy cleanup and demo data](docs/legacy-cleanup-azure-validation.md)

Share a clean source export rather than the entire working directory. Private `.env` files, credentials, verification documents, live student data, dependencies, caches and temporary preview files do not belong in the lecturer's source package. Environment examples contain placeholders only.
