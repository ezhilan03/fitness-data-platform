FROM python:3.11-slim AS baseline
WORKDIR /app
COPY fitness/ fitness/
COPY sql/ sql/
COPY fixtures/ fixtures/
COPY tests/ tests/
RUN useradd --uid 1000 --create-home appuser && mkdir -p /app/artifacts && chown -R 1000:1000 /app/artifacts
ENV PYTHONDONTWRITEBYTECODE=1
USER 1000:1000
CMD ["python", "-m", "fitness.demo"]

FROM public.ecr.aws/lambda/python:3.12 AS cloud
COPY requirements-dbt.lock ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-dbt.lock
COPY fitness/ ${LAMBDA_TASK_ROOT}/fitness/
COPY sql/ ${LAMBDA_TASK_ROOT}/sql/
COPY dbt/ ${LAMBDA_TASK_ROOT}/dbt/
COPY fixtures/ ${LAMBDA_TASK_ROOT}/fixtures/
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["fitness.aws_app.handler"]
