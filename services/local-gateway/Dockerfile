# Runtime image for local-gateway. Source is bind-mounted at /app in compose.
FROM python:3.12-slim

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PYTHONPATH=/app

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

EXPOSE 18110
CMD ["/opt/venv/bin/python", "main.py"]
