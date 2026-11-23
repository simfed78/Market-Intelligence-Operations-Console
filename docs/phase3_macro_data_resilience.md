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
   The producer computes a **derived-only** macro regime and publishes source
   identifiers, observed dates, acquisition times, input hashes and official
   links. It does **not** redistribute raw histories or proprietary
   ICE BofA numerical observations. The versioned public artifact is
   `research-data:exports/research/macro_latest.json`.
4. The archive publisher merges newly verified **metadata** into the
   previous derived report. A timeout or partially successful refresh cannot
   delete the previous qualified source date. A later-retrieved observation
   is used only when the observation period is at least as recent.
5. Streamlit Cloud loads the last published **derived-only** archive into
   ephemeral local research storage and refreshes only market quotations.
   **It never requests FRED live**. When the archive is unreachable, previously
   verified local derived context remains intact; otherwise macro is
   DATA UNAVAILABLE. The macro view links to the official FRED time-series
   page for complete history instead of republishing the numeric series.
   Public hosting remains strictly `RESEARCH_ONLY`.
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

## Public redistribution boundary

FRED serves datasets from different copyright holders. In particular, the
ICE BofA IG/HY spread series are identified as copyrighted and require an
independent rights check before republication. This repository publishes
**no raw FRED CSV/JSON or ICE BofA values**, only derived regime commentary
from government macro inputs and provenance/freshness metadata. The
`input_sha256` hashes are provenance references, not data authentication
or a guarantee of historical publication vintages. For the full series
history use FRED's official series pages and applicable license permissions.

## 23 November 2026 — Issuing-agency source fallback

The earlier FRED-MD `current.csv` response sometimes contained a
`CPIAUCSL` series ending in September 2025, so a successful HTTP response
was not enough for a current macro regime. The new ingestion path uses
dated monthly **issuing-agency** observations first:

- **CPIAUCSL**: U.S. Bureau of Labor Statistics, CPI-U all items, seasonally
  adjusted series `CUSR0000SA0`. Endpoint:
  https://api.bls.gov/publicAPI/v1/timeseries/data/CUSR0000SA0
- **INDPRO**: Federal Reserve Board, G.17 seasonally adjusted total
  industrial-production index `B50001`. Official history:
  https://www.federalreserve.gov/releases/g17/Current/ipdisk/ip_sa.txt

These map to the same *concepts* represented by FRED IDs. Their true
acquisition origins are labelled `BLS` and `FRB-G17`, not re-labelled as
direct FRED downloads. Input series must contain at least 16 distinct
continuous monthly observations, no future values, and a latest observation
no more than 75 days old. No interpolation or synthetic continuation.

FRED-MD is now a lower-priority fallback and its individual monthly series
must also meet the 75-day age gate. Remaining rates, breakevens, NFCI and
proprietary credit spreads may still be unavailable until independently
qualified sources are available; a good CPI/IP observation cannot stand in
for those other six series. Macroeconomic regime is context-only and does
**not** override risk gates or authorize a trade.

The public macro archive version `macro-research-summary.v2` may quote only
the latest dated government CPI and industrial production values; it does
not publish original monthly histories or third-party ICE BofA numerical
spread histories. Every published value has a source link, date and hash,
and full history remains available at the issuing provider.
