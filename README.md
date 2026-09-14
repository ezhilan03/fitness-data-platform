# Fitness Data Platform

A synthetic fitness data-engineering project that preserves workout history, reconstructs what was known at a cutoff, and publishes daily and weekly summaries with explicit data-quality evidence.

[Dashboard demo](https://ezhilan03.github.io/fitness-data-platform/) · [Architecture](docs/ARCHITECTURE.md) · [Cloud operations](docs/CLOUD.md) · [Data contract](docs/DATA-CONTRACT.md)

The public dashboard is a recorded synthetic snapshot. The cloud API is authenticated with AWS IAM. Native wearable sync, clinical guidance, goal/strength-set tracking and model-generated training plans are outside v1.

## What this demonstrates

- Validated complete-export ingestion, including successful empty exports and source heartbeats.
- Append-only source revisions, duplicate-safe replay, explicit device identities and point-in-time selection using source availability plus local receipt time.
- UTC elapsed duration, IANA local day/week assignment, unit normalization and preserved missing-distance values.
- Real dbt/DuckDB transformations, grain and quality checks, incremental replacement, obsolete-group removal, documentation and lineage.
- Airflow ingestion → transformation DAG with an explicit daily data-interval timetable, catchup, retries and historical backfills.
- Publication that preserves the previous successful result on failure. Read-only authenticated summaries and a responsive dashboard.
- Docker, hosted CI, Terraform, OIDC deployment, on-demand ECS Fargate batches, private versioned S3, Lambda IAM authentication, CloudWatch logs and SQS failure alerts.

## Evidence

| Verification | Artifact |
|---|---|
| 28 unit/integration tests | [Test results](artifacts/test-results.txt) |
| Three dbt models and 13 tests in eight scenarios; exact weekly parity and daily-total checks | [dbt report](artifacts/dbt-report.json) |
| Seven scheduled intervals, automatic retry recovery and two historical backfills | [Airflow report](artifacts/airflow-report.json) |
| dbt runs as a non-root user with a read-only container filesystem | [Container report](artifacts/cloud-container-report.json) |
| Actual AWS execution, replay, alert transport, restore and authorization | [Cloud report](artifacts/cloud-report.json) |
| Hosted verification and deployment | [GitHub Actions](https://github.com/ezhilan03/fitness-data-platform/actions) |

The fixture starts with one canonical 5,000-metre run despite watch/phone representations. A correction and late session produce two running sessions totalling 8,000 metres, while the earlier historical result remains reconstructable. Distinct overlapping workout IDs are retained. Missing days are unknown; missing distances remain null.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dbt.lock
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m fitness.demo
.venv/bin/python -m fitness.dbt_demo
.venv/bin/python -m fitness.operations_demo
```

The standard-library ingestion baseline needs Python 3.11+. Airflow uses its own Python 3.11 environment and `requirements-airflow.lock`; the cloud image uses Python 3.12. The [scheduler verification procedure](docs/AIRFLOW-VERIFICATION.md) starts a real local scheduler and shuts down its services afterward.

```bash
docker build --target baseline -t fitness-data .
docker run --rm fitness-data
docker build --platform linux/amd64 --provenance=false --target cloud -t fitness-cloud .
```

## Scope and tradeoffs

This is portfolio evidence at a declared synthetic workload. Source snapshots and aggregations still perform full scans; no large-scale throughput claim is made. Airflow is verified locally with SQLite metadata, while cloud batch execution is on demand. There is no continuously running cloud scheduler, database or container service.

The local SQLite incremental path updates affected groups transactionally. dbt writes changed groups but does not publish the whole DAG atomically; readers use a latest-successful pointer. Cloud writers use an expiring conditional S3 lease. Daily summaries are derived from the verified current-session table.

Local logical erasure and replay suppression are tested. Cloud versions and exported snapshots have retention policies, but coordinated subject erasure across every retained copy is not implemented; only synthetic data is supported. Missing data, device-identity assumptions and start-day assignment are documented in the contract. Failure alerts are delivered to SQS; no human email/SMS subscription is implied.
