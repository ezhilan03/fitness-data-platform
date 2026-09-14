FROM python:3.11-slim
WORKDIR /app
COPY fitness/ fitness/
COPY sql/ sql/
COPY fixtures/ fixtures/
COPY tests/ tests/
RUN useradd --uid 1000 --create-home appuser
ENV PYTHONDONTWRITEBYTECODE=1
USER 1000:1000
CMD ["python", "-m", "fitness.demo"]
