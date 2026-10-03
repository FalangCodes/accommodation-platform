# Gap 4: resource permissions and ownership

No migration, frontend change or environment-variable change is required.

## Behaviour

- A landlord may delete an image only from their own listing. The image must
  also belong to the listing named in the URL. Denied requests do not delete
  blobs or database rows. Successful deletion invalidates listing, search and
  featured-listing caches.
- Listing analytics check current ownership before reading cached results.
- Only approved listings have public details and published review previews.
  Pending, rejected, suspended and removed listings can be viewed by the owning
  landlord, moderators and admins; other callers receive `404`. Their detailed
  insights use the same visibility check in addition to authentication.
- View recording uses the same listing visibility rule. Unauthorized requests
  cannot increment hidden-listing counters.
- Visibility checks use current database status and ownership before cached
  content is returned. A previously approved cached listing cannot bypass a
  subsequent suspension. Cached detail responses reflect current status.
- Students can appeal only their own reviews. Landlords can appeal only their
  own listings or landlord profile. Explicit moderation-action IDs must match
  both the resource type and resource ID. Listing actions use the moderation
  log's `accommodation` type. Automatic action lookup and pending-appeal
  duplicate checks remain supported.
- Private verification document storage and appeal resolution workflows are
  separate gaps and are unchanged here.

## Azure validation

After the pushed commit is pulled manually, run:

```sh
cd ~/accommodation-platform
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py tests/integration/test_guest_access.py tests/integration/test_resource_permissions.py -q --tb=short
```

Tests use isolated users/profiles/appeals and scripted listing, review and image
resources. They evaluate resource-query equality predicates, simulate cached
responses and mock blob/cache side effects. They do not touch live users,
listings, Azure blobs or Redis, and do not test PostGIS execution.

If successful, rebuild/restart:

```sh
docker compose up -d --build --no-deps --force-recreate backend
```

## Acceptance checks

Use dedicated test listings and accounts for actions that modify data.

1. Open an approved listing signed out: details and the two-review preview still
   load. Existing gap 3 search, review and insight limits still apply.
2. Open a pending/suspended listing URL signed out or as a student: listing not
   found. Sign in as its owner, a moderator or admin: details remain available.
3. Warm an approved listing's cache, suspend it using a moderator test account,
   then revisit signed out: the listing and review API routes must return `404`.
4. With two landlord test accounts, attempt to delete the other account's image
   through a direct API request: `403`, image preserved. An image from a different
   listing under an owned-listing URL returns `404`. Delete a disposable owned
   image and confirm it disappears after reloading listing/search previews.
5. Load owned analytics to warm the cache, then request them as the other
   landlord: `403`.
6. Submit an appeal for a moderated owned resource: success. Attempt another
   account's resource: `404`; submit an action ID from another resource or type:
   `422`. A duplicate pending appeal remains `409`.

The automated tests cover these cross-account cases without destructive actions
against production data.
