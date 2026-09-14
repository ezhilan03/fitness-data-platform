# Real dbt milestone — 14 September 2026

Verified locally with dbt Core 1.12.4, dbt-duckdb 1.9.6 and DuckDB 1.5.5 on Python 3.11.15. The complete installed dependency set is in requirements-dbt.lock. Run `python -m fitness.dbt_demo` in that environment to reproduce all eight scenarios and regenerate artifacts/dbt-report.json.

The source exporter reads one SQLite transaction and atomically replaces raw.revisions in DuckDB. The staging view applies source-availability and receipt cutoffs before the current_sessions model resolves versions and explicit device identities. weekly_summaries uses the adapter's delete+insert incremental strategy with user/week/activity keys. Changed aggregates replace old groups; temporary zero-session tombstones remove groups that disappear after corrections or erasure. A post-hook removes those tombstones.

Each actual dbt build runs three models and 13 tests, including source/model non-null checks, grain uniqueness, summary quality and bidirectional EXCEPT parity against full aggregation. A separate Python harness compares every result with SQLite full refresh. Scenarios cover initial load, unchanged replay, correction and late arrival, historical cutoff, return to current, moved week, obsolete week removal and erasure. dbt docs generate produces a manifest, catalog and HTML documentation; dependency edges are retained in the report.

This implementation copies all source rows and scans all current sessions. Only changed target groups are selected for incremental replacement; no throughput or read-pruning claim is made. The whole dbt DAG is not published as one atomic snapshot, and dbt failure/retry recovery has not yet been injected. SQLite atomic rollback tests do not establish dbt atomicity. Erasure propagation is verified in the live source and derived tables; disk sanitization and exported backup retention remain out of scope.

Hosted CI repeats this regression. Separate Docker targets cover the standard-library baseline and cloud dbt runtime. Airflow scheduling/retry/backfill and AWS Fargate execution are verified separately; see the current README and release artifacts.

Adapter reference: https://github.com/duckdb/dbt-duckdb
