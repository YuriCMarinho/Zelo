"""Consulta de prestadores e gatilho controlado de fallback do Nó 3."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.provider import Provider
from app.db.session import get_db
from app.schemas.common import ProviderCategory, mask_phone
from app.services.provider_collector import collect_on_demand

router = APIRouter(prefix="/api/providers", tags=["Prestadores"])
DatabaseDep = Annotated[Session, Depends(get_db)]


class ProviderSummary(BaseModel):
    id: str
    name: str
    category: ProviderCategory
    region: str
    masked_phone: str
    rating: float | None


class FallbackRequest(BaseModel):
    category: ProviderCategory
    region: str = Field(min_length=2, max_length=100)


class FallbackResponse(BaseModel):
    run_id: str | None
    confirmed: int
    already_available: bool


@router.get("", response_model=list[ProviderSummary])
def list_validated_providers(
    db: DatabaseDep,
    category: ProviderCategory | None = None,
    region: Annotated[str | None, Query(max_length=100)] = None,
) -> list[ProviderSummary]:
    query = select(Provider).where(Provider.is_validated.is_(True))
    if category is not None:
        query = query.where(Provider.category == category.value)
    if region is not None:
        query = query.where(Provider.region == region)
    return [
        ProviderSummary(
            id=provider.id,
            name=provider.name,
            category=ProviderCategory(provider.category),
            region=provider.region,
            masked_phone=mask_phone(provider.phone),
            rating=provider.rating,
        )
        for provider in db.scalars(query).all()
    ]


@router.post("/collect", response_model=FallbackResponse)
async def trigger_fallback(request: FallbackRequest, db: DatabaseDep) -> FallbackResponse:
    """Gatilho de demonstração; em produção o Nó 3 chama collect_on_demand diretamente."""
    if settings.environment not in {"development", "testing"}:
        raise HTTPException(status_code=403, detail="Gatilho manual indisponível")
    result = await collect_on_demand(db, request.category, request.region)
    if result is None:
        return FallbackResponse(run_id=None, confirmed=0, already_available=True)
    return FallbackResponse(
        run_id=result.run_id, confirmed=result.confirmed, already_available=False
    )
