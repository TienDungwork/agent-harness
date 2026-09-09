# Runtime image for vms-sync. Polls Postgres, inserts into ClickHouse.
FROM python:3.12-slim

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY config.py main.py sources.py ./

CMD ["/opt/venv/bin/python", "main.py"]
