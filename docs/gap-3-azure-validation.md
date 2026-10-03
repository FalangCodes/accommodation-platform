# Gap 3: enforce guest discovery previews

No database migration or environment-variable change is required.

## Behaviour

- Guests can search page 1 with a fixed page size of 10. The API sends at most
  seven listing records plus `locked_count` for up to three placeholders; no
  identifiers, images, coordinates or other details are sent for locked cards.
- Page 2 and beyond require an eligible authenticated account. Changing
  `page_size` does not expand a guest's preview.
- The listing reviews endpoint returns `{items, total, locked_count}`. Guests
  receive at most two published reviews; signed-in users receive all published
  reviews. Pending, quarantined and deleted reviews remain excluded.
- Detailed insights require an active session. Students must also have verified
  their institutional email. Invalid, revoked and ineligible sessions do not
  unlock guest previews.
- Redis stores full internal records. Both cache-hit and fresh-query paths
  project those records into the caller's permitted response before returning
  them. Search keys include page size and correctly named filter arguments.
- Frontend search/review/insight query keys include the account identity. Guests
  see generic placeholders and do not request detailed insights. The map uses
  only the listing records permitted by the search response.
- Basic listing details, aggregate ratings/sentiment and existing homepage
  previews remain public. This is a per-search preview, not a restriction on
  opening a known listing URL or running a different search.

## Deploy and validate on Azure

After the commit is pushed, pull it manually while preserving the VM's Compose
configuration:

```sh
cd ~/accommodation-platform
git stash push -m "Preserve VM Compose configuration" -- docker-compose.yml
git pull --ff-only
git stash pop
```

Run the regression suite using isolated test users, scripted discovery records
and in-memory cache. These tests do not alter production users/listings or send
email, and do not execute PostGIS search queries:

```sh
docker compose run --rm --no-deps backend python -m pytest tests/unit tests/integration/test_auth_email_flows.py tests/integration/test_guest_access.py -q --tb=short
```

If successful, rebuild/restart the backend:

```sh
docker compose up -d --build --no-deps --force-recreate backend
```

## Browser acceptance

Wait for Vercel's deployment of the same commit, then reload the browser.

1. In a signed-out/incognito window, search with enough matching listings:
   seven visible cards, up to three generic locked cards, and a sign-in prompt.
   The map must not show the locked listings.
2. Try page 2: the UI directs you to sign in; a direct guest API request is
   rejected. A direct `page_size=50` request still contains at most seven items.
3. Open a listing with at least three published reviews: only two review bodies
   are visible, plus a count and sign-in prompt. Check the network response:
   hidden review bodies and replies must be absent.
4. Detailed insights remain locked for guests; the page must not request the
   insights endpoint. A direct guest request must be rejected.
5. Sign in with a verified active student account: full search pages, all
   published reviews and detailed insights should load. Check landlord,
   moderator and admin discovery access where accounts are available.
6. Sign out and repeat: full content must not remain in guest query responses.
   Warm the backend caches while signed in, then repeat guest API checks.

The frontend temporarily accepts the old review-array response during the
deployment handover. Backend enforcement starts when Azure is rebuilt/restarted.
