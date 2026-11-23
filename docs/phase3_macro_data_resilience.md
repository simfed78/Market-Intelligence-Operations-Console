# Phase 3 macro data resilience — published, not live

## Why the change is needed

CPI, industrial production, credit spreads and Treasury yields have published
observations with different release frequencies. A runtime timeout accessing
FRED is not evidence that the previous published observation ceased to exist.
The dashboard must preserve last-good observations and their observed/acquired
dates, instead of treating every remote request as a mandatory live feed.

## Production flow

1. Scheduled research workflow refreshes publicly qualified market data and
   attempts FRED retrieval independently. FRED requests are sequential, with
   short timeouts and a circuit breaker after repeated source connectivity failures.
   Yahoo/market retrieval is prioritized.
2. FRED source is the original official CSV download; if a repository secret
   `FRED_API_KEY` exists, an official FRED observations API request is used.
   The API key is **never** included in the saved source URL, exported archive,
   metrics or diagnostic text.
3. Provider data is strictly validated: official origin, series ID, CSV schema,
   retrieval timestamp, content hash, numeric observations and publication age.
   Only actual FRED responses are archived. The versioned public artifact is
   `research-data:exports/research/macro_latest.json`.
4. The archive publisher merges newly qualified observations into the previous
   archive. A timeout or partially successful refresh cannot delete a
   previously verified series. A later-retrieved observation is used only when
   the observation period is at least as recent.
5. Streamlit Cloud loads the last published archive into its local read-only
   research snapshot database and refreshes only market quotations. **It never
   requests FRED live**. When the archive is unreachable, local previously
   stored snapshots remain intact; otherwise macro is DATA UNAVAILABLE.
   Public hosting remains strictly `RESEARCH_ONLY` and imported records
   are **never** portfolio/broker data.
6. Each macro observation displays source, observed period, acquisition
   timestamp, release/vintage limitation and per-series staleness. A revived
   network connection cannot retroactively certify publication vintages.

## Freshness policy

- Market bars retain their existing strict provider and 6h acquisition cache.
- Verified FRED observations may be served from cache for up to 26h between
  refresh attempts. A network failure **does not delete** older snapshots.
- Macro context continues to evaluate its own per-series observation age
  limits: CPI/INDPRO 75d; Treasury/credit 7d; NFCI 21d.
- Status `DEGRADED` means real revised observations without certified
  historical release vintages. A stale observation remains explicitly
  marked stale; missing observations are not imputed or scored neutral.
- Latest known and latest published are **not automatically equivalent**.
  Never claim release-day coverage if the acquired timestamp predates it.
- Current FRED macro assessments abstain from entry authorization until
  reliable point-in-time vintages and strategy validation are implemented.

## First-time archive availability

`macro_latest.json` will appear only after at least one successful qualified
FRED acquisition by the scheduled research workflow. Without any prior
verified download and while FRED remains inaccessible, no offline series is
invented: the macro engine stays `DATA UNAVAILABLE`.

If FRED public CSV retrieval is persistently unavailable in CI, create an
optional `FRED_API_KEY` **repository Actions secret** (not a source file),
then rerun `Research brief - validate and publish`. For a fully offline import,
verified official FRED CSV records can also enter through the existing
`src.intelligence.refresh --import-inbox` contract. All data are dated.

## Verification

- `python -m pytest -q`
- `python -m src.intelligence.macro_archive --root . --output /tmp/macro.json`
- Inspect the resulting `research-data/exports/research/macro_latest.json`
  after successful scheduled publication.
- Load Streamlit and verify the Macro panel distinguishes historical data,
  provider timeouts, observed period and acquired timestamp.
- No trading orders, real-account integration, or unqualified macro scores.
