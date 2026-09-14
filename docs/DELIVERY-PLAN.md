# Delivery plan and hiring evidence

Scope approved 14 September 2026: start the local Fitness data-engineering slice after the two fintech releases. Saved JDs were read from the Career workspace; these are September 11 captures, not newly verified vacancies or a market-frequency analysis.

| Saved requirement | Implemented milestone-1 evidence | Still required |
|---|---|---|
| Delivery Hero: point-in-time datasets, historization, late arrivals | Revision history and availability/receipt cutoff tests | Production event ingestion, orchestration and operational monitoring |
| Delivery Hero: validation, observability, lineage | Input contracts, payload/source identity, overlap counts, recovery test | Freshness thresholds and actual alert delivery |
| Prodigal: SQL models and rerunnable transformations | SQL window selection and transactional weekly mart, verified replay | Actual dbt build/tests/docs and incremental partition replacement |
| Prodigal: dimensional modelling and historical data | Declared source/session/week grains and preserved revisions | Goal dimension history, additional health observations and dbt lineage |

## Gate 1 — completed locally

Synthetic JSONL → validated revisions → point-in-time current sessions → weekly summaries. Nineteen tests and deterministic demo pass. The sample running total changes from one session / 5,000 metres to two sessions / 8,000 metres after a 6,000-metre correction and a late 2,000-metre session. The earlier historical result remains 5,000 metres. Phone/watch duplicates sharing an explicit session ID count once.

## Gate 2 — next, dependency blocked

Install and lock a tested dbt/DuckDB stack. Port the normalized SQL into staging/intermediate/mart models with source declarations, grain/relationship tests and generated lineage. Re-run the same fixture scenarios against the actual adapter. Use the current full refresh as an oracle for incremental affected-week replacement, including old and new week removal when timestamps change.

The attempted dbt-duckdb 1.9.6 installation failed at PyPI DNS resolution in the restricted session. No installed-version or successful dbt execution claim is made. Resolve environment package access before this gate, rather than substituting mock dbt results.

## Gate 3 — operations

Airflow must execute a real interval, retry and backfill. Demonstrate stale-source alert and recovery. Container build and hosted CI must actually pass. Fitness cloud provider/project and budget remain unselected; no billable deployment is authorized by this local milestone.

## Deferred

HealthKit/native app integration, authenticated summary API, strength-set grain, goal history, dashboards and evaluated plan explanations follow the reliable data slice. No clinical outcomes, recommendation quality or model-comparison claims.
