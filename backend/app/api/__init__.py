"""Pacote de rotas da API FastAPI."""

from app.api.audit import router as audit_router
from app.api.bookings import bookings_router
from app.api.chat import chat_router
from app.api.costs import router as costs_router
from app.api.demo import demo_router
from app.api.providers import router as providers_router
from app.api.tickets import property_tickets_router
from app.api.tickets import router as tickets_router

__all__ = [
    "audit_router",
    "bookings_router",
    "chat_router",
    "costs_router",
    "demo_router",
    "property_tickets_router",
    "providers_router",
    "tickets_router",
]
