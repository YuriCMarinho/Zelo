# ==============================================================================
# Multi-stage Dockerfile: Unified Container (FastAPI + React Frontend)
# Ideal para deploy no Render, Railway, Fly.io ou VPS com 1 único link público.
# ==============================================================================

# Estágio 1: Build do Frontend React + Vite
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Estágio 2: Runtime Backend com Python 3.12 e uv
FROM python:3.12-slim AS runtime
WORKDIR /app

# Instala uv binário para gerenciamento veloz e determinístico de pacotes
COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    FRONTEND_DIST_DIR=/app/frontend_dist \
    PORT=8000

# Dependências mínimas de sistema (curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalação das dependências Python
COPY backend/pyproject.toml backend/uv.lock* ./backend/
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-editable

# Copia código-fonte do backend
COPY backend/app ./app

# Copia os artefatos estáticos do frontend construídos no estágio 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend_dist

# Criação de usuário não-root para segurança
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck em tempo de execução
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Comando de inicialização com porta dinâmica compatível com Render ($PORT)
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
