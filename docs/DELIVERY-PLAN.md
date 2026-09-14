# Delivery plan and hiring evidence

Scope approved 14 September 2026: start the local Fitness data-engineering slice after the two fintech releases. Saved JDs were read from the Career workspace; these are September 11 captures, not newly verified vacancies or a market-frequency analysis.

| Saved requirement | Implemented milestone-1 evidence | Still required |
|---|---|---|
| Delivery Hero: point-in-time datasets, historization, late arrivals | Revision history and availability/receipt cutoff tests | Production event ingestion, orchestration and operational monitoring |
| Delivery Hero: validation, observability, lineage | Input contracts, payload/source identity, overlap counts, recovery test | Freshness thresholds and actual alert delivery |
| Prodigal: SQL models and rerunnable transformations | SQL window selection and transactional weekly mart, verified replay | Airflow scheduling, dbt failure/retry recovery and hosted CI |
| Prodigal: dimensional modelling and historical data | Declared source/session/week grains and preserved revisions | Goal dimension history and additional health observations |

## Gate 1 — completed locally

Synthetic JSONL → validated revisions → point-in-time current sessions → weekly summaries. Nineteen tests and deterministic demo pass. The sample running total changes from one session / 5,000 metres to two sessions / 8,000 metres after a 6,000-metre correction and a late 2,000-metre session. The earlier historical result remains 5,000 metres. Phone/watch duplicates sharing an explicit session ID count once.

## Gate 2 — completed locally

Real dbt/DuckDB execution now passes three models and 13 tests in each of eight fixture scenarios, matching the SQLite full-refresh oracle. Incremental target replacement includes obsolete group deletion after moved weeks and erasure. Documentation/catalog/lineage generation succeeds. The earlier network blocker is resolved. See [verification and limits](DBT-VERIFICATION.md).

## Gate 3 — operations

Airflow now executes real daily intervals, automatic retry recovery and two historical backfills; all nine successful runs pass three dbt models and 13 checks. Local stale-source alert evidence is verified. External notification delivery and upstream ingestion scheduling remain pending. Container build and hosted CI must actually pass. Fitness cloud provider/project and budget remain unselected; no billable deployment is authorized by this local milestone.

## Deferred

HealthKit/native app integration, authenticated summary API, strength-set grain, goal history, dashboards and evaluated plan explanations follow the reliable data slice. No clinical outcomes, recommendation quality or model-comparison claims.

## Incremental SQL milestone — completed locally

The SQLite mart now replaces affected user/week/activity groups and tracks the last successful cutoff with a session snapshot. Twenty-four tests pass, including full-refresh equivalence, unchanged replay, source-priority changes, correction across week boundaries, erasure, backward-cutoff rejection and atomic failure/recovery. The synthetic demonstration rebuilds two groups initially, one after corrections/late arrival and zero on unchanged replay. The initial dependency blocker was later resolved and Gate 2 is verified above. Airflow scheduler verification is now complete locally; see AIRFLOW-VERIFICATION.md.
