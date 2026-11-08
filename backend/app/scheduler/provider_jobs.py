"""Agendamento periódico do Nó S via APScheduler."""

from uuid import uuid4

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore  # type: ignore[import-untyped]
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from sqlalchemy import select

from app.core.config import settings
from app.db import session as database
from app.db.models.property import Property
from app.db.session import SessionLocal
from app.observability.logger import logger
from app.schemas.common import ProviderCategory
from app.services.provider_collector import ProviderCollector, make_collector


async def run_periodic_collection(collector: ProviderCollector | None = None) -> str:
    """Uma execução possui run_id próprio, compartilhado por todas as buscas do lote."""
    run_id = str(uuid4())
    active_collector = collector or make_collector()
    with SessionLocal() as db:
        regions = {
            f"{city}, {state}"
            for city, state in db.execute(select(Property.city, Property.state)).all()
        }
        for region in sorted(regions):
            for category in ProviderCategory:
                try:
                    await active_collector.collect(db, category, region, run_id=run_id)
                except Exception:
                    logger.exception(
                        "Falha na busca periódica de prestadores",
                        extra={"run_id": run_id, "category": category.value},
                    )
    return run_id


def create_provider_scheduler() -> AsyncIOScheduler:
    if settings.provider_collection_hours < 1:
        raise ValueError("PROVIDER_COLLECTION_HOURS deve ser >= 1")
    scheduler = AsyncIOScheduler(
        timezone="UTC",
        jobstores={"default": SQLAlchemyJobStore(engine=database.engine)},
        job_defaults={"misfire_grace_time": None},
    )
    scheduler.add_job(
        run_periodic_collection,
        trigger="interval",
        hours=settings.provider_collection_hours,
        id="provider_collector_node_s",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler
