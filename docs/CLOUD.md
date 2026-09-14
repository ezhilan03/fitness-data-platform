# Cloud operations and cost boundary

AWS us-east-1. The deployed batch family/cluster and API function are `fitness-data-platform`. Terraform definitions are in `infra/aws`; local credentials are never checked into the repository. GitHub deployment uses OIDC and repository variables, not access-key secrets.

The API requires AWS IAM signing for `/`, `/summary` and `/health`. Anonymous requests must return 403. The public Pages demo contains only a recorded synthetic snapshot; it is not an unauthenticated proxy to the cloud API. Lambda has a read-only S3 role. Batch tasks have the separately scoped ingestion/storage/alert role.

No ECS service, NAT gateway, load balancer, managed database or scheduled cloud batch is provisioned. Tasks receive a temporary public IP for outbound HTTPS, accept no inbound traffic and stop after execution. ECR retains three images; S3 run snapshots expire after 14 days and old versions after seven days; CloudWatch logs expire after seven days. Alert messages expire after 14 days. Terraform state is stored in the same private versioned bucket under `infra/terraform.tfstate`, with native S3 locking.

For light demos, the target is comfortably below $5/month, not a guaranteed spending cap. Idle costs are primarily image/object/log storage. Fargate is charged while tasks run (including its minimum billing duration); Lambda, S3, SQS, logging and temporary IPv4 usage are metered. Free-tier eligibility is not assumed. This budget is shared with the user's other portfolio infrastructure. There are no automatic recurring demos.

Pricing references: [Fargate](https://aws.amazon.com/fargate/pricing/), [Lambda](https://aws.amazon.com/lambda/pricing/), [ECR](https://aws.amazon.com/ecr/pricing/), [VPC IPv4](https://aws.amazon.com/vpc/pricing/).

## Reproduction and recovery

Install `requirements-cloud-tools.txt` alongside the local dbt environment and authenticate the personal AWS `portfolio` profile. `scripts/verify_cloud.py` runs real on-demand batches, verifies idempotent replay, injects a stale-source failure, checks SQS delivery, restores a versioned source database, and checks signed versus unsigned HTTP access. It writes `artifacts/cloud-report.json` and a synthetic dashboard snapshot. This is an explicit test workflow; it is not a recurring scheduler.

The deployment workflow publishes an immutable image, registers a new Fargate task definition, updates the read-only Lambda image and runs a smoke batch. Rollback uses an earlier retained image/task-definition revision. Terraform does not silently undo an image deployment. The first infrastructure bootstrap creates the storage/image repository before the image-dependent resources; subsequent init uses the existing S3 backend.

A failed batch leaves the latest published summary intact. Inspect CloudWatch structured events (`fitness_run_failed`, `dbt_build_failed`) and the SQS alert. Restore the source's prior S3 version if needed, then rerun. Expired leases can be replaced with an ETag-conditional write; an active lease returns busy. Do not delete someone else's active lock or bypass the concurrency guard.

Only synthetic fixtures are authorized for this release. Logical deletion in the ingestion database does not sanitize every retained S3 version, local export or public snapshot. Real health data requires a separate retention/subject-erasure design before ingestion.
