# Fitness Data Platform

A local, synthetic data-engineering project for reliable workout history and weekly summaries. **Milestone 1 is implemented and tested.** This is not a completed cloud product, HealthKit integration, or medical recommendation system.

## Run now

Requires Python 3.11+ with IANA timezone data. The verified local baseline uses only the standard library and SQLite; there are no package downloads or paid API calls required.

```bash
python3 -m unittest discover -s tests -v
python3 -m fitness.demo
python3 -m fitness --database fitness.db ingest fixtures/baseline.jsonl
python3 -m fitness --database fitness.db summarize --as-of 2026-12-31T23:59:59Z
```

The ordinary ingestion command records the actual receipt time; choose a summary cutoff after that time to see the records. The deterministic demo replays an explicitly synthetic historical timeline in a temporary database and removes it afterward. It does not read real health exports.

## Implemented evidence

- 19 passing tests, including conflict rollback and injected summary-write failure/recovery.
- Source revisions are appended atomically; identical exports replay without duplicate totals.
- A correction changes the current result without overwriting the historical revision.
- Event time, source availability and local receipt time are separate. Historical selection filters knowledge timestamps before selecting the latest revision.
- Distances normalize to metres; durations use UTC elapsed time across daylight-saving changes. Week assignment uses the session's IANA local timezone.
- Only explicitly shared session identities deduplicate devices. Unlinked overlapping workouts remain visible and are counted in an overlap-quality signal.
- Missing distances stay null and missing days stay unknown. Weekly summaries include observation counts.
- Local logical deletion removes revisions and summaries, then blocks reintroduction from old exports.

[Demo report](artifacts/demo-report.json) · [Test results](artifacts/test-results.txt) · [Data contract](docs/DATA-CONTRACT.md) · [Delivery plan](docs/DELIVERY-PLAN.md)

```mermaid
flowchart LR
  E[Synthetic JSONL export] --> V[Validate batch and provenance]
  V --> R[(Append-only source revisions)]
  R --> C[Select versions known at cutoff]
  C --> D[Resolve explicit cross-device identities]
  D --> W[Weekly SQL summaries and quality counts]
  X[Local erasure request] --> R
  X --> T[Replay suppression tombstone]
```

## Important modelling choices

The first mart performs a transactional full refresh. This deliberately establishes a correctness baseline before incremental partition replacement; it is not a claim of scalable incremental transformations. Historical requests rebuild the mart for that cutoff, so this single-process demo does not serve concurrent snapshots.

Manual records win over watch records, which win over phone records, only when the user and canonical session ID agree. Different IDs never merge merely because timestamps overlap. Whole workout duration is assigned to its start day and week; cross-midnight splitting is not implemented.

Erasure is logical within the live database, not forensic disk sanitization. Hash tombstones retain replay-suppression metadata. External files, exported reports and backups require a separate retention/erasure design before real health data is introduced.

## Next gates

1. Run these same fixtures through real dbt models and tests, preserving the SQL baseline results.
2. Implement incremental affected-week replacement and compare against full refresh, including corrections that move records between weeks.
3. Run Airflow interval/retry/backfill and freshness-alert exercises.
4. Verify Docker and hosted CI, then authenticated summary delivery and budgeted cloud operations.

Package installation failed in this session because the restricted environment could not resolve PyPI. **dbt and Airflow are not installed or verified here.** The [official dbt-duckdb adapter](https://github.com/duckdb/dbt-duckdb) is the planned local transformation runtime once dependencies are available. No cloud resources were created. CI and Docker definitions are supplied but have not run.
