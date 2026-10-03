# Gap 5: private verification documents

No database schema migration is required. Existing URL columns remain internal
storage references. Public listing responses omit ownership-document references,
including legacy cached values. Authorized APIs return protected endpoint paths.

## Access and uploads

- `GET /api/v1/landlords/{id}/documents/id-copy`
- `GET /api/v1/landlords/{id}/documents/proof-of-address`
- `GET /api/v1/accommodations/{id}/documents/ownership`

Each download checks the active session and permits only the owning landlord,
moderators or admins. Students and other landlords cannot download documents,
even for approved listings. Responses use attachment filenames, correct MIME
types, `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.
Download failures do not expose storage details.

Document uploads use a separate private container, bounded reads (10MB maximum),
allowed MIME types and matching file signatures. Both upload and download fail
closed if the document container is public. The backend resolves only references
from the configured account/private container, never arbitrary URLs or SAS links.
Listing photos use the configured public photo container and actual account URL.

Moderator/admin buttons fetch bytes with the session authorization header and
download a temporary browser Blob URL. Tokens are never embedded in links.

## Test before migration

After manually pulling the pushed commit on Azure:

```sh
cd ~/accommodation-platform
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py tests/integration/test_guest_access.py tests/integration/test_resource_permissions.py tests/integration/test_private_documents.py -q --tb=short
docker compose run --rm --no-deps backend python migrate_document_storage.py --source-container listing-images
```

Tests isolate database data and mock Azure/Redis. Migration unit tests verify
dry runs, copy failure, repeatability, checksum comparison, retained originals,
private legacy access and document/photo reference separation.

## Migration and deployment

The initial read-only inventory found one `listing-images` container with public
blob access and 30 blobs. The database referenced 15 photos, four ownership
documents, three ID copies and three proof-of-address files. Counts may change
before deployment; use the migration's fresh dry-run inventory.

1. Build the backend image. Wait for the new Vercel frontend deployment so its
   document buttons support authenticated downloads.
2. Stop the backend briefly to prevent uploads during migration; keep DB/Redis
   running. Take a private PostgreSQL dump and verify its archive can be listed.
3. Run the migration with `--apply`. It creates `listing-photos` with public blob
   access and `verification-documents` with private access. It copies referenced
   files and compares SHA-256 checksums of source and destination bytes before
   updating references in one database transaction.
4. The migration then makes `listing-images` private. All source files remain
   there, including unreferenced uploads. No source blobs are deleted. A document
   also referenced as a public photo causes the migration to abort for review.
5. Set the VM root `.env` values below, preserving its other secrets/settings:

```dotenv
AZURE_STORAGE_CONTAINER_NAME=listing-photos
AZURE_DOCUMENT_CONTAINER_NAME=verification-documents
```

6. Clear affected listing/search/featured/activity caches and recreate the
   backend. Confirm health, photo access, protected download responses and
   anonymous denial for both private containers.

```sh
docker compose run --rm --no-deps backend python migrate_document_storage.py --source-container listing-images --apply
docker compose up -d --no-deps --force-recreate backend
```

The migration is repeatable after interruption. Keep the backend stopped if it
fails. Source files and the database backup support recovery. Never restore
anonymous access to the old mixed container as a recovery shortcut; rerun the
migration after addressing the failure or restoring database references.

## Browser acceptance

- Public photos still load on search and listing pages. Public listing network
  responses contain no ownership-document storage URL or download endpoint.
- An owning landlord can upload PDF/JPEG/PNG/WebP documents and submit the existing
  verification workflow. Invalid or oversized files are rejected.
- Moderators/admins can download ID, address and ownership documents from their
  existing review screens. Downloaded PDFs keep the `.pdf` extension.
- A signed-out browser, student or different landlord cannot download documents.
  Direct old/new document Blob URLs also reject anonymous requests.
- Previous gaps' authentication, guest previews and resource permissions continue
  to work. Approve this gap after browser checks before starting gap 6.
