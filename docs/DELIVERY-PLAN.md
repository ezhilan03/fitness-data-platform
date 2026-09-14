# V1 delivery and hiring evidence

The release implements the approved reliable-data slice and its operational delivery. Saved job descriptions informed the design; this is not a current-vacancy or market-frequency analysis.

| Requirement | Delivered evidence |
|---|---|
| Point-in-time history and late arrivals | Versioned ingestion, knowledge cutoffs, corrections and replay tests |
| SQL modelling and dbt | Explicit source/session/week grains, real adapter execution, parity and quality checks, lineage |
| Orchestration and recovery | Airflow ingestion and transformation, daily intervals, automatic retries and backfills |
| Container and cloud delivery | Verified Docker targets, hosted CI, OIDC deployment, Terraform, on-demand Fargate and authenticated Lambda reads |
| Observability and retained state | CloudWatch structured logs, SQS failure delivery, S3 versions and restoration tests |
| Usable output | Authenticated daily/weekly JSON and dashboard; public recorded synthetic demo |

The current README and artifacts are the source of verification results. Initial package-network restrictions were resolved. dbt batch execution uses Fargate because the Lambda runtime lacks the POSIX semaphores required by the adapter.

Beyond v1: native HealthKit synchronization, real health-data retention and coordinated erasure, strength-set/goal histories and model-generated training plans. They are not requirements left unfinished inside this synthetic data-engineering release.
