# AccomFind management reports

## Purpose and reporting basis

Accommodation reports combine period performance and comparable prior-period
figures, lifetime recorded-view charts, published rating/sentiment distributions,
topic evidence, public landlord reply coverage, strengths to preserve and actions
with a responsible role and follow-up measure. Landlords access them through
My listings -> Analytics -> Generate / view management reports.

Platform reports add current publication/verification/NLP/appeal queues,
registrations and moderation activity, publication/ownership readiness mismatches,
campus discovery coverage, and a list of
properties for follow-up. University reports use the same management format,
scoped to linked listings. Admin access remains through Admin -> Reports.

New reports persist a versioned document in the existing `ReportMetric.breakdown`
JSONB column. They are immutable snapshots, including the view series. Repeatable
read gives each generation a consistent PostgreSQL snapshot. No database schema
change or migration is required. Failed generation rolls back rather than leaving
partially saved metrics or a permanently generating report.

Monthly intervals are half-open UTC date ranges. Current-month reports are
explicitly month-to-date; comparisons use the same elapsed duration of the prior
month, capped at its end. Empty rating samples stay null. A zero comparison
baseline produces no fabricated percentage. Small traffic/review samples are
labelled directional. Ratings change in rating points rather than percentages.

Only currently published, non-deleted reviews enter public experience measures.
Creation dates scope review submission periods; publish timestamps are unavailable.
Operational queues/statuses are labelled current at generation, not reconstructed
historical status. Topic counts describe the overall sentiment of reviews tagged
with a topic; independently scored topic sentiment is not persistently available
in the committed schema. Recommendations are rule-based investigation steps, not
verified safety assertions, guaranteed outcomes or generic generated prose.

Views are recorded page visits, including revisits. Redis-buffered views are
excluded and month assignment follows their database flush timestamp. No booking,
conversion, revenue, unique-visitor, occupied-bed or housing-shortage claims are
made. Current verified student/listing coverage is not a demand/capacity measure.
Individual student names/emails, full review bodies and private documents are
excluded. PDFs and report JSON require admin or current property ownership.

## PDF export

ReportLab renders A4 PDFs server-side: AccomFind letterhead, report reference,
generation date, page numbers, vector view/rating charts, repeated table headings
and wrapped action text. Downloads use authenticated API requests and private,
no-store responses. Browser page printing is removed from report export.

Older report records remain intact. Their PDF export preserves their original
figures and explicitly labels them legacy statistics; generate a fresh report
to get the management analysis. Legacy export does not invent historical insights.
The old accommodation trend endpoint now reads actual view rows, so it no longer
depends on prior report generation or duplicates months when reports regenerate.

Illustrative layout previews were rendered and visually checked locally using
synthetic figures; they are not production reports. Backend execution tests run
only on Azure.

## Azure validation and deployment

### Topic priority calibration (21 October 2026)

Newly generated reports use negative-review frequency, its share of recognised
sentiment results within each topic, and minimum sample sizes. High investigation
priority requires at least 10 recognised results, 5 negative results and 40%
negative; Medium requires at least 5 recognised results, 2 negative results and
20% negative. Other negative signals remain visible as Validate. These thresholds
are an operational triage policy, not statistical significance or confirmed risk.
Unclassified sentiment is explicitly excluded from the percentage denominator.

An isolated safety signal prompts manual review and confirmation before
topic-specific expenditure. A topic name alone does not make it High priority.
Strong positive feedback (at least 5 positive results and 70% of recognised
topic-tagged sentiment) can remain a strength alongside concerns. All counts
remain whole-review sentiment, not an independent score for a tagged topic.
Existing saved reports retain their original classifications and PDF content;
generate a fresh report to use the new policy. No schema migration is needed.

Azure regression coverage includes `tests/unit/test_report_priorities.py` for
the observed 45-positive/10-neutral/1-negative safety scenario, sample and share
boundaries, unclassified results, cross-scope behaviour, mixed strengths, safety
follow-up and ordering against repeated non-safety concerns. The report API/PDF
integration test also verifies the persisted validation step survives export.

### Deployment procedure

1. Pull the pushed commit, preserving the VM Compose configuration as usual.
2. Build the backend image (new pinned PDF dependencies); do not restart yet:
   `docker compose build backend`
3. Run the existing regression suite plus:
   `docker compose run --rm --no-deps backend python -m pytest tests/integration/test_management_reports.py -q --tb=short`
4. Tests use disposable PostgreSQL schemas. They cover period boundaries,
   unpublished/deleted review exclusion, null/zero handling, role/ownership
   isolation for generate/list/read/PDF/trend, immutable snapshots, atomic failure,
   legacy PDF export and letterhead/page content. They never generate production
   reports or contact SMTP, Redis counters, blob storage or external AI.
5. Once tests pass, recreate only backend:
   `docker compose up -d --no-deps backend`
6. Verify HTTPS health, CORS and the Vercel frontend deployment.

## Browser checks

- Landlord: open a property's analytics, generate a selected month's report,
  inspect the assessment and action plan, switch monthly/cumulative views and
  download/open the PDF. Confirm other properties/platform reports are inaccessible.
- Admin: generate platform and accommodation reports; inspect operational queues,
  campus coverage, property follow-up and data limitations. Download the PDFs.
- Verify no-review properties show missing evidence, not a 0/5 rating or 100%
  satisfaction. Compare current reports only after considering unflushed views.
- Confirm a saved report retains its figures after subsequent review changes;
  generate a new report when an updated snapshot is needed.

## Local frontend checks

TypeScript checks, the new report component lint and the final production
frontend build passed on 13 October 2026. Existing admin, dashboard and API lint
issues remain outside this change. Confirm the matching Vercel deployment before
browser acceptance.
