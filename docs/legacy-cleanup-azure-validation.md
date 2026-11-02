# Legacy NLP retirement and safe demo seeding

The active review pipeline uses Gemini through the shared quota gate. The
Hugging Face microservice and unused Celery worker are retired. Docker Compose
now runs PostgreSQL/PostGIS, Redis and the backend only. No database migration
or live-data rewrite is included. Existing `.env` files may retain
`NLP_SERVICE_URL`; it is accepted solely for compatibility and is not used.

## Validate on Azure

Preserve VM Compose edits and pull main as usual. If stash pop reports a conflict,
resolve it before running Compose; preserve the VM's bindings and environment.

```bash
docker compose config --quiet
docker compose build backend
docker compose run --rm --no-deps backend python -m pip check
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration -q --tb=short
```

All demo-seed tests use disposable PostgreSQL schemas. They do not seed the live
database or call Gemini/SMTP. They verify refusal before database access without
confirmation/password, refusal of existing data, transaction rollback, concurrent
seed protection, and pending review status without fabricated NLP results.

After tests pass, retire only the old NLP container if it still exists:

```bash
docker ps -a --filter name=accommodation_nlp --format '{{.Names}} {{.Status}}'
```

If `accommodation_nlp` is listed, stop and remove that container:

```bash
docker stop accommodation_nlp
docker rm accommodation_nlp
```

Then restart only the updated backend:

```bash
docker compose up -d --no-deps backend
```

No volume deletion, database reset, or broad orphan removal is needed.

## Demo data for a separate empty database only

Do **not** run this against the presentation/live database. The schema must
already exist through the normal Alembic migration process. The seed command
refuses any database containing data in any application table.
Its inserts commit in one transaction and never change existing records.

On a separate fresh demo installation, provide a password through the shell:

```bash
read -rsp 'Demo password (8-64 characters): ' DEMO_PASSWORD
echo
export DEMO_PASSWORD
docker compose run --rm --no-deps -e DEMO_PASSWORD backend python -m app.db.seed --demo
unset DEMO_PASSWORD
```

Accounts are `demo.landlord.1@example.com`, `demo.student.1@example.com`, etc.,
using the supplied password. These synthetic accounts are preverified only to
make the isolated demo usable without sending email. They do not represent real
identity or property verification. Listings are marked `[DEMO]`; names, prices
and review templates are demonstration data, not current property claims.

Seeded reviews remain `pending_analysis`. The regular backend sweep analyses
them through Gemini and applies normal moderation and quota handling. The seed
itself sends no AI or email requests, publishes no reviews, and never backfills
pre-existing pending reviews. The removed service remains recoverable in Git
history rather than being shipped as a second conflicting implementation.
