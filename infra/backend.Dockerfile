# Backend Dockerfile isolado (caso deseje executar sem o frontend)
FROM python:3.12-slim
WORKDIR /app/backend

COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-dev --no-editable

COPY backend/app ./app

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
