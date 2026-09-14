# Interval operations — local implementation

The interval job gates a real dbt build on successful export heartbeats, writes into a new run directory, and replaces latest.json only after success. A historical run does not replace a newer published interval. Failed builds leave the previous pointer untouched and write a local structured alert. Consumers must resolve latest.json; direct reads of intermediate model files are not a supported publication interface. This is a single-writer local design; the DAG limits active runs to one. Retained snapshots need explicit erasure and retention management before real health data is used.

Freshness measures completed exports, including empty exports, rather than last workout activity. Required sources and the age threshold are explicit. The upstream ingestion process is responsible for supplying truthful heartbeat timestamps after export ingestion completes. The prepared DAG expects a separate heartbeat file for each interval end, supporting historical checks without overwriting evidence. Automated export ingestion is not yet orchestrated.

Run `.venv/bin/python -m fitness.operations_demo` to exercise two actual dbt builds around a stale-source failure. The report records freshness failure, local alert creation, preserved publication and successful recovery. Unit tests additionally inject a transform failure and check historical-publication behavior; these are not Airflow scheduler tests. Run outputs in the demo are temporary synthetic artifacts.

`dags/fitness_daily.py` prepares an Airflow 3 daily schedule, two retries, catchup and one active run. It runs dbt in its separate environment to avoid dependency conflicts. Configure FITNESS_PROJECT_ROOT and FITNESS_STATE_ROOT; source.db and per-interval heartbeats must exist under the latter. FITNESS_REQUIRED_SOURCES defaults to watch,phone,manual.

Airflow 3.1.8 installation with the official Python 3.11 constraints was attempted but blocked by DNS/network restrictions. The DAG has not been imported or executed by Airflow. Scheduled intervals, actual scheduler retries/backfills and external alert delivery remain unverified. No cloud resources were created.

Official constrained-install reference: https://github.com/apache/airflow/blob/main/INSTALLING.md
