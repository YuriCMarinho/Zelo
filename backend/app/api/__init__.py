"""Pacote de rotas da API FastAPI."""

from app.api.chat import chat_router
from app.api.providers import router as providers_router

__all__ = ["chat_router", "providers_router"]
