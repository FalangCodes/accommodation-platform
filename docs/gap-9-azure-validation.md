# Gap 9: published review metrics, insight refresh, and view flushing

No database migration or schema change is required.

## Changes

- Search filters and ratings, listing details, owner analytics, featured listings,
  and the activity feed use only non-deleted `analysed` / `released` reviews.
- Public platform review counts also require an approved listing.
- Student deletion, moderator removal/release, and upheld review appeals refresh
  insights after the review change commits. Removing the final published review
  clears stored insights and recommendations. Published reviews without NLP
  results still contribute to the insight review count.
- Insight generation can derive aspect details from existing NLP columns; it does
  not require the separately proposed `aspect_details` database column.
- Review changes invalidate listing, reviews, analytics, search, featured,
  activity, and platform count caches after commit.
- Redis view counters are claimed atomically into retained batches. New views
  continue accumulating separately. PostgreSQL commits before acknowledgment;
  a stable marker in the existing view hash column prevents retry duplication.
  PostgreSQL advisory locks serialize concurrent flushers and view-total reads.
- Analytics reads refresh view totals even when review analytics are cached.

View counts represent recorded page views, not unique visitors. Retained batches
protect against failed writes, acknowledgment failures, and concurrent flushes.
They do not protect against losing Redis storage; Redis persistence remains an
infrastructure concern. If Redis is unavailable, buffered counts cannot be read.

## Azure validation

After pulling this commit, run the existing regression suite plus:

```sh
docker compose run --rm --no-deps backend python -m pytest tests/integration/test_published_metrics.py -q --tb=short
```

Tests use disposable PostgreSQL schemas and Redis keys prefixed `test_gap9_<uuid>:`.
They never modify production rows, counters, SMTP, blobs, or external NLP services.
They cover published-only ratings, last-review deletion, moderator release/removal,
legacy NLP columns, failed commits, committed-but-unacknowledged batches, concurrent
flushers, and concurrent increments. Run all previous gap regression tests too.

Restart the backend after tests pass. Clear existing derived cache keys once:
`listing:*`, `reviews:*`, `analytics:*`, `search:*`, `featured:listings`,
`activity:feed`, `platform:stats`. Preserve `views:*` and `view-batch:*`.
Regenerate existing listing insights using the committed insight engine so old
stored summaries also follow the published-review rules.

## Browser checks

1. Compare a listing's published reviews with its rating and review count on the
   detail page, search results, and landlord dashboard.
2. Delete your review. Its rating contribution disappears after refreshing, and
   insights update. If it was the last published review, old recommendations clear.
3. Release a quarantined test review as moderator/admin, then remove it. Verify
   that public counts and insights increase/decrease with its visibility.
4. Visit an approved listing, then refresh its owner's analytics. Recorded views
   should increase and remain consistent after the scheduled database flush.

Keep the one-active-review and cooldown behavior from Gap 6 unchanged. Do not
advance to the next gap until these checks pass.
