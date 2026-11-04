FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS uv
FROM python:3.14-slim

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY *.py ./
COPY facturacion ./facturacion

RUN useradd --uid 1000 --create-home agent \
    && mkdir -p /data /backups \
    && chown -R 1000:1000 /app /opt/venv /data /backups

ENV PATH="/opt/venv/bin:$PATH" \
    AGENT_DATABASE_PATH=/data/agent.sqlite3 \
    AGENT_BACKUP_DIR=/backups

USER 1000:1000
EXPOSE 8000
CMD ["uvicorn", "servidor:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
