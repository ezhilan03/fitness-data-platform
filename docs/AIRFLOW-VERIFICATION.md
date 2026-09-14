# Airflow scheduler verification

The local verification uses Apache Airflow 3.1.8 with its official Python 3.11 constraints in a dedicated environment. The installed package set is pinned in requirements-airflow.lock. dbt remains in .venv, separate from Airflow's .venv-airflow.

Reproduce with `.venv/bin/python scripts/verify_airflow.py` after installing those two environments. The harness creates a fresh ignored directory, initializes synthetic source data and export heartbeats, starts Airflow standalone on loopback port 9876, and unpauses fitness_daily. It watches actual metadata task states, restores the deliberately stale source only after observing up_for_retry, and then asks Airflow to create a two-interval backfill. The harness shuts down its server, scheduler, processor and worker process group on completion or error. Local logs and authentication files stay in ignored artifacts/local and must not be published.

Verified on 14 September 2026: seven scheduled intervals succeeded, the deliberately stale task recovered on attempt two, and two historical backfills succeeded without replacing the latest publication. All nine successful dbt builds passed three models and 13 checks. One local stale-source alert was created; the local server was confirmed stopped afterward.

The daily catchup window is bounded to seven historical intervals for the verification using FITNESS_SCHEDULE_END. Normal DAG operation has no end date unless that setting is supplied. A successful run records seven scheduled intervals, recovery on a subsequent task attempt, two scheduler-executed backfill intervals and preservation of the latest publication pointer. See artifacts/airflow-report.json for the measured result; absent that report, do not infer success from this procedure.

This is a local standalone deployment using SQLite metadata, synthetic input and a single active DAG run. It does not establish distributed-executor behavior, high availability, cloud operation or ingestion scheduling. Export heartbeats are explicit upstream completion fixtures, not fabricated workout activity. Failure alerts remain local files; external notification delivery is not implemented. Historical published snapshots require an erasure/retention policy before real health data.

Official installation reference: https://github.com/apache/airflow/blob/main/INSTALLING.md
