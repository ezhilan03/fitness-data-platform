terraform {
  backend "s3" {}
  required_version = ">= 1.6"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
provider "aws" { region = "us-east-1" }
variable "image_uri" {
  type    = string
  default = ""
}
data "aws_caller_identity" "current" {}
locals { name = "fitness-data-platform" }
resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy     = jsonencode({ rules = [{ rulePriority = 1, description = "Retain latest three release images", selection = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 3 }, action = { type = "expire" } }] })
}
resource "aws_s3_bucket" "state" { bucket = "${local.name}-${data.aws_caller_identity.current.account_id}" }
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 7 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
  rule {
    id     = "expire-run-snapshots"
    status = "Enabled"
    filter { prefix = "published/runs/" }
    expiration { days = 14 }
  }
}
resource "aws_sqs_queue" "alerts" {
  name                      = "${local.name}-alerts"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 7
}
resource "aws_iam_role" "runtime" {
  name               = "${local.name}-runtime"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "runtime" {
  role = aws_iam_role.runtime.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.state.arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.state.arn}/*" },
    { Effect = "Allow", Action = ["s3:DeleteObject"], Resource = "${aws_s3_bucket.state.arn}/state/run.lock" },
    { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.alerts.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }
  ] })
}
resource "aws_lambda_function" "app" {
  count         = var.image_uri == "" ? 0 : 1
  function_name = local.name
  package_type  = "Image"
  image_uri     = var.image_uri
  role          = aws_iam_role.api.arn
  lifecycle { ignore_changes = [image_uri] }
  architectures = ["x86_64"]
  timeout       = 30
  memory_size   = 256
  ephemeral_storage { size = 512 }
  environment { variables = { FITNESS_BUCKET = aws_s3_bucket.state.id, FITNESS_ALERT_QUEUE = aws_sqs_queue.alerts.url, DBT_SEND_ANONYMOUS_USAGE_STATS = "false", HOME = "/tmp" } }
  depends_on = [aws_iam_role_policy.runtime, aws_cloudwatch_log_group.app]
}
resource "aws_lambda_function_url" "app" {
  count              = var.image_uri == "" ? 0 : 1
  function_name      = aws_lambda_function.app[0].function_name
  authorization_type = "AWS_IAM"
}
resource "aws_iam_role" "github" {
  name               = "${local.name}-github"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com" }, Action = "sts:AssumeRoleWithWebIdentity", Condition = { StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com", "token.actions.githubusercontent.com:sub" = "repo:ezhilan03/fitness-data-platform:ref:refs/heads/main" } } }] })
}
resource "aws_iam_role_policy" "github" {
  role = aws_iam_role.github.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"], Resource = aws_ecr_repository.app.arn },
    { Effect = "Allow", Action = ["lambda:UpdateFunctionCode", "lambda:GetFunctionConfiguration", "lambda:InvokeFunction", "lambda:InvokeFunctionUrl"], Resource = "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:${local.name}" }
  ] })
}
output "repository_url" { value = aws_ecr_repository.app.repository_url }
output "bucket" { value = aws_s3_bucket.state.id }
output "alert_queue" { value = aws_sqs_queue.alerts.url }
output "github_role" { value = aws_iam_role.github.arn }
output "function_url" { value = try(aws_lambda_function_url.app[0].function_url, null) }

# Batches use a full OS runtime: dbt requires POSIX semaphores unavailable in Lambda.
data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}
resource "aws_security_group" "batch" {
  name        = "${local.name}-batch"
  description = "No ingress; outbound HTTPS for S3 ECR logs and queue"
  vpc_id      = data.aws_vpc.default.id
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_ecs_cluster" "batch" { name = local.name }
resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "execution" {
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = aws_ecr_repository.app.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }
  ] })
}
resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "api" {
  role = aws_iam_role.api.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.state.arn}/published/latest.json" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }
  ] })
}
resource "aws_ecs_task_definition" "batch" {
  count                    = var.image_uri == "" ? 0 : 1
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.runtime.arn
  container_definitions = jsonencode([{
    name             = "batch", image = var.image_uri, essential = true,
    entryPoint       = ["python", "-m", "fitness.cloud_batch"],
    environment      = [{ name = "FITNESS_BUCKET", value = aws_s3_bucket.state.id }, { name = "FITNESS_ALERT_QUEUE", value = aws_sqs_queue.alerts.url }, { name = "FITNESS_EXECUTION_MODE", value = "batch" }, { name = "HOME", value = "/tmp" }, { name = "PYTHONPATH", value = "/var/task" }],
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.app.name, "awslogs-region" = "us-east-1", "awslogs-stream-prefix" = "batch" } }
  }])
  lifecycle { ignore_changes = [container_definitions] }
}
resource "aws_iam_role_policy" "github_batch" {
  role = aws_iam_role.github.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecs:DescribeTaskDefinition", "ecs:RegisterTaskDefinition", "ecs:DescribeTasks"], Resource = "*" },
    { Effect = "Allow", Action = ["ecs:StopTask"], Resource = "arn:aws:ecs:us-east-1:${data.aws_caller_identity.current.account_id}:task/${local.name}/*" },
    { Effect = "Allow", Action = ["ecs:RunTask"], Resource = "arn:aws:ecs:us-east-1:${data.aws_caller_identity.current.account_id}:task-definition/${local.name}:*", Condition = { ArnEquals = { "ecs:cluster" = aws_ecs_cluster.batch.arn } } },
    { Effect = "Allow", Action = ["iam:PassRole"], Resource = [aws_iam_role.runtime.arn, aws_iam_role.execution.arn], Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } } },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.state.arn}/published/latest.json" }
  ] })
}
output "batch_task_definition" { value = try(aws_ecs_task_definition.batch[0].arn, null) }
output "batch_subnet" { value = data.aws_subnets.default.ids[0] }
output "batch_security_group" { value = aws_security_group.batch.id }
