# Fitness Data Platform

A local, synthetic data-engineering project for reliable workout history and weekly summaries. **Local ingestion, incremental SQL and real dbt/DuckDB milestones are implemented and tested.** This is not a completed cloud product, HealthKit integration, or medical recommendation system.

## Run now

Requires Python 3.11+ with IANA timezone data. The verified local baseline uses only the standard library and SQLite; there are no package downloads or paid API calls required.

```bash
python3 -m unittest discover -s tests -v
python3 -m fitness.demo
python3 -m fitness.incremental_demo
python3 -m fitness --database fitness.db ingest fixtures/baseline.jsonl
python3 -m fitness --database fitness.db summarize --as-of 2026-12-31T23:59:59Z
```

The ordinary ingestion command records the actual receipt time; choose a summary cutoff after that time to see the records. The deterministic demo replays an explicitly synthetic historical timeline in a temporary database and removes it afterward. It does not read real health exports.

## Implemented evidence

- 26 passing tests, including conflict rollback and injected summary-write failure/recovery.
- Source revisions are appended atomically; identical exports replay without duplicate totals.
- A correction changes the current result without overwriting the historical revision.
- Event time, source availability and local receipt time are separate. Historical selection filters knowledge timestamps before selecting the latest revision.
- Distances normalize to metres; durations use UTC elapsed time across daylight-saving changes. Week assignment uses the session's IANA local timezone.
- Only explicitly shared session identities deduplicate devices. Unlinked overlapping workouts remain visible and are counted in an overlap-quality signal.
- Missing distances stay null and missing days stay unknown. Weekly summaries include observation counts.
- Local logical deletion removes revisions and summaries, then blocks reintroduction from old exports.

[Incremental verification](artifacts/incremental-report.json) · [Demo report](artifacts/demo-report.json) · [Test results](artifacts/test-results.txt) · [Data contract](docs/DATA-CONTRACT.md) · [Delivery plan](docs/DELIVERY-PLAN.md)

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

The full-refresh mart is the correctness baseline. The incremental path compares current canonical sessions with a persisted snapshot, replaces affected user/week/activity groups, and commits its snapshot and cutoff in the same transaction. Corrections moving weeks rebuild both old and new groups. Unchanged replay recomputes zero groups. Source history is still scanned and snapshots copied; this is not a scale or performance claim. Cutoff metadata updates every mart row. Incremental cutoffs cannot move backward; use full refresh for an older historical view. This single-process demo does not serve concurrent snapshots.

Manual records win over watch records, which win over phone records, only when the user and canonical session ID agree. Different IDs never merge merely because timestamps overlap. Whole workout duration is assigned to its start day and week; cross-midnight splitting is not implemented.

Erasure is logical within the live database, not forensic disk sanitization. Hash tombstones retain replay-suppression metadata. External files, exported reports and backups require a separate retention/erasure design before real health data is introduced.

## Real dbt verification

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dbt.lock
.venv/bin/python -m fitness.dbt_demo
```

Three actual dbt models and 13 data tests pass in each of eight synthetic scenarios, with exact result parity against SQLite full refresh. Corrections, late arrivals, historical cutoffs, replay, moved weeks, obsolete group removal and erasure are covered. Documentation and lineage generation also pass. Dependencies are pinned; the previous package-network blocker is resolved.

[dbt verification report](artifacts/dbt-report.json) · [Design and limits](docs/DBT-VERIFICATION.md)

## Interval operations

The local interval runner adds export-heartbeat freshness checks, isolated dbt runs and a latest-successful-publication pointer. See [operations design and verification limits](docs/OPERATIONS.md). Run `.venv/bin/python -m fitness.operations_demo` for actual dbt failure-gate/recovery evidence. Airflow 3.1.8 now runs the actual DAG: seven scheduled intervals and two backfills passed, including recovery on a second task attempt after a stale-source failure. [Scheduler evidence](artifacts/airflow-report.json) and [reproduction details](docs/AIRFLOW-VERIFICATION.md).

## Next gates

1. Verify external freshness-alert delivery and automate upstream export ingestion.
2. Verify Docker and hosted CI, then authenticated summary delivery and budgeted cloud operations.

Airflow is verified locally with a single active run and SQLite metadata. No cloud resources were created. CI includes the dbt regression but has not run on GitHub. The Docker definition currently covers the standard-library baseline and remains unverified locally.

For the incremental command, use `python3 -m fitness --database fitness.db summarize --as-of 2030-01-01T00:00:00Z --incremental`. Local deletion also removes the subject from the incremental snapshot. Snapshot, aggregates and watermark roll back together on failure.
