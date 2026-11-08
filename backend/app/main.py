import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.resolver_graph import close_resolver_checkpointer, init_resolver_checkpointer
from app.agents.resolver_timeouts import set_timeout_scheduler
from app.api import (
    audit_router,
    bookings_router,
    chat_router,
    costs_router,
    demo_router,
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
    try:
        Base.metadata.create_all(bind=engine)
        run_seed()
    except Exception as e:
        print(f"Aviso durante inicialização do banco/seed: {e}")
    await init_resolver_checkpointer()
    scheduler = None
    if settings.environment != "testing":
        scheduler = create_provider_scheduler()
        scheduler.start()
        set_timeout_scheduler(scheduler)
    try:
        yield
    finally:
        set_timeout_scheduler(None)
        await close_resolver_checkpointer()
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
app.include_router(bookings_router)
app.include_router(tickets_router)
app.include_router(property_tickets_router)
app.include_router(costs_router)
app.include_router(audit_router)
app.include_router(demo_router)


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


# Suporte a arquivos estáticos do frontend para deploy em container unificado
_candidates = [
    os.environ.get("FRONTEND_DIST_DIR", ""),
    "/app/frontend_dist",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/dist")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend_dist")),
]
static_dir = next((d for d in _candidates if d and os.path.isdir(d)), None)

if static_dir and os.path.exists(os.path.join(static_dir, "index.html")):
    resolved_static_dir: str = static_dir
    assets_dir = os.path.join(resolved_static_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_spa(full_path: str) -> FileResponse:
        candidate = os.path.join(resolved_static_dir, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(resolved_static_dir, "index.html"))
