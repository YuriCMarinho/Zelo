from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import (
    audit_router,
    chat_router,
    costs_router,
    property_tickets_router,
    providers_router,
    tickets_router,
)
from app.core.config import settings
from app.db.base import Base
from app.db.models import MaintenanceTicket, Property
from app.db.seed import run_seed
from app.db.session import engine, get_db
from app.scheduler.provider_jobs import create_provider_scheduler
from app.schemas.property import PropertyRead

DatabaseDep = Annotated[Session, Depends(get_db)]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    try:
        run_seed()
    except Exception as e:
        print(f"Aviso durante seed de inicialização: {e}")
    scheduler = None
    if settings.environment != "testing":
        scheduler = create_provider_scheduler()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="SmartRepair AI API",
    description="Plataforma de agentes de IA para gestão e manutenção de imóveis de temporada.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(providers_router)
app.include_router(chat_router, prefix="/api")
app.include_router(tickets_router)
app.include_router(property_tickets_router)
app.include_router(costs_router)
app.include_router(audit_router)


@app.get("/health", tags=["Saúde"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "app": "SmartRepair AI",
        "environment": settings.environment,
        "llm_mode": settings.llm_mode,
    }


@app.get("/health/db", tags=["Saúde"])
def db_health_check(db: DatabaseDep) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        props_count = db.query(Property).count()
        tickets_count = db.query(MaintenanceTicket).count()
        return {
            "status": "healthy",
            "database": "connected",
            "properties_count": props_count,
            "tickets_count": tickets_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Falha de conexão com o banco de dados: {e}",
        ) from e


@app.get("/api/properties", response_model=list[PropertyRead], tags=["Imóveis"])
def list_properties(db: DatabaseDep) -> list[Property]:
    return db.query(Property).all()
