"""Nó S: descoberta e validação explícita de prestadores de serviço."""

import json
import re
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm import generate
from app.db.models.audit import AuditEvent
from app.db.models.provider import Provider
from app.observability.logger import logger
from app.schemas.common import ProviderCategory
from app.security.guardrails import SecurityViolationError, validate_untrusted_input
from app.security.masking import mask_pii

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName,places.internationalPhoneNumber,places.rating"
CATEGORY_QUERIES: dict[ProviderCategory, str] = {
    ProviderCategory.PLUMBER: "encanador",
    ProviderCategory.ELECTRICIAN: "eletricista",
    ProviderCategory.PAINTER: "pintor",
    ProviderCategory.ORGANIZER: "organizador profissional",
    ProviderCategory.GENERAL_MAINTENANCE: "manutenção residencial",
}
FIXTURE_PHONES = frozenset({"+55 11 90000-0001", "+55 11 90000-0002"})


@dataclass(frozen=True)
class ProviderCandidate:
    place_id: str
    name: str
    category: ProviderCategory
    region: str
    phone: str
    source: str
    rating: float | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class CollectionResult:
    run_id: str
    source: str
    discovered: int
    confirmed: int
    refused: int
    skipped: int
    provider_ids: tuple[str, ...]


@dataclass(frozen=True)
class ValidationMessage:
    place_id: str
    recipient_phone: str
    run_id: str
    body: str


class CandidateSource(Protocol):
    async def search(
        self, category: ProviderCategory, region: str, limit: int = 5
    ) -> list[ProviderCandidate]: ...


class ContactGateway(Protocol):
    async def request_confirmation(
        self, candidate: ProviderCandidate, run_id: str
    ) -> str | None: ...


class FixturePlacesAdapter:
    """Dados artificiais para desenvolvimento e testes, sem chamadas externas."""

    async def search(
        self, category: ProviderCategory, region: str, limit: int = 5
    ) -> list[ProviderCandidate]:
        if not region.strip() or limit < 1:
            return []
        return [
            ProviderCandidate(
                place_id=f"fixture-{category.value}-{index}",
                name=f"Prestador simulado {index} · {CATEGORY_QUERIES[category]}",
                category=category,
                region=region.strip(),
                phone=phone,
                source="fixture",
                rating=4.8,
            )
            for index, phone in enumerate(sorted(FIXTURE_PHONES), start=1)
        ][:limit]


class GooglePlacesAdapter:
    """Text Search (New) com máscara mínima de campos e limite de chamadas."""

    def __init__(
        self, api_key: str, *, max_calls: int = 50, client: httpx.AsyncClient | None = None
    ) -> None:
        if not api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY é obrigatória para Google Places")
        self.api_key = api_key
        self.max_calls = max_calls
        self.calls_made = 0
        self.client = client

    async def search(
        self, category: ProviderCategory, region: str, limit: int = 5
    ) -> list[ProviderCandidate]:
        if self.calls_made >= self.max_calls:
            raise RuntimeError("Limite de chamadas Google Places atingido")
        if not region.strip() or not 1 <= limit <= 20:
            raise ValueError("Região e limite (1 a 20) são obrigatórios")
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
            "Content-Type": "application/json",
        }
        payload = {
            "textQuery": f"{CATEGORY_QUERIES[category]} em {region.strip()}",
            "languageCode": "pt-BR",
            "regionCode": "BR",
            "pageSize": limit,
        }
        self.calls_made += 1
        if self.client is not None:
            response = await self.client.post(PLACES_URL, headers=headers, json=payload)
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(PLACES_URL, headers=headers, json=payload)
        response.raise_for_status()
        places = response.json().get("places", [])
        candidates: list[ProviderCandidate] = []
        for place in places:
            place_id = place.get("id")
            name = place.get("displayName", {}).get("text")
            phone = place.get("internationalPhoneNumber")
            if not all(
                isinstance(value, str) and value.strip() for value in (place_id, name, phone)
            ):
                continue
            raw_rating = place.get("rating")
            rating = float(raw_rating) if isinstance(raw_rating, int | float) else None
            candidates.append(
                ProviderCandidate(
                    place_id=place_id,
                    name=name[:150],
                    category=category,
                    region=region.strip(),
                    phone=phone[:30],
                    source="google_places",
                    rating=rating if rating is None or 1 <= rating <= 5 else None,
                )
            )
        return candidates


class SimulatedContactGateway:
    """Canal interno: só registra mensagens para números em allowlist, sem transporte externo."""

    def __init__(self, allowed_phones: set[str], replies: dict[str, str] | None = None) -> None:
        self.allowed_phones = allowed_phones
        self.replies = replies or {}
        self.sent: list[ValidationMessage] = []

    async def request_confirmation(self, candidate: ProviderCandidate, run_id: str) -> str | None:
        if candidate.phone not in self.allowed_phones:
            logger.warning("Contato fora da allowlist ignorado", extra={"run_id": run_id})
            return None
        self.sent.append(
            ValidationMessage(
                place_id=candidate.place_id,
                recipient_phone=candidate.phone,
                run_id=run_id,
                body=(
                    "Olá! Somos da SmartRepair. Você confirma que aceita receber solicitações "
                    "de orçamento para serviços de manutenção nesta região?"
                ),
            )
        )
        return self.replies.get(candidate.place_id)


class ContactDecision(BaseModel):
    confirmed: bool


async def contact_is_confirmed(reply: str | None, run_id: str, db: Session) -> bool:
    """Recusas têm prioridade; resposta ambígua só passa com classificação positiva."""
    if reply is None:
        return False
    try:
        clean = validate_untrusted_input(reply, role="provider", run_id=run_id)
    except SecurityViolationError:
        return False
    normalized = clean.casefold()
    if re.search(r"\b(não|nao|recuso|indisponível|indisponivel|não posso|nao posso)\b", normalized):
        return False
    if re.search(r"\b(sim|confirmo|aceito|atendo|posso atender|estou disponível)\b", normalized):
        return True
    if settings.llm_mode == "mock":
        return False
    response = await generate(
        messages=[
            {
                "role": "system",
                "content": (
                    "Classifique se o prestador confirmou explicitamente o contato. "
                    "Retorne JSON com confirmed; dúvida ou recusa = false."
                ),
            },
            {"role": "user", "content": mask_pii(clean)},
        ],
        model="Qwen/Qwen3.5-4B",
        max_tokens=64,
        run_id=run_id,
        node="scraper_nodeS",
        response_format=ContactDecision,
        db=db,
    )
    return isinstance(response.parsed, ContactDecision) and response.parsed.confirmed


class ProviderCollector:
    def __init__(self, source: CandidateSource, gateway: ContactGateway) -> None:
        self.source = source
        self.gateway = gateway

    async def collect(
        self,
        db: Session,
        category: ProviderCategory,
        region: str,
        *,
        limit: int = 5,
        run_id: str | None = None,
    ) -> CollectionResult:
        run_id = run_id or str(uuid4())
        if not region.strip() or len(region) > 100:
            raise ValueError("Região inválida")
        if isinstance(self.source, GooglePlacesAdapter):
            reserve_places_call(db, run_id, settings.max_places_calls)
        else:
            from app.services.provider_browser import AgentBrowserAdapter

            if isinstance(self.source, AgentBrowserAdapter):
                reserve_browser_search(db, run_id, settings.max_browser_searches)
        candidates = await self.source.search(category, region.strip(), limit)
        confirmed = refused = skipped = 0
        provider_ids: list[str] = []
        db.add(
            AuditEvent(
                run_id=run_id,
                node="scraper_nodeS",
                event_type="collection_started",
                payload={
                    "category": category.value,
                    "region": region.strip(),
                    "source": type(self.source).__name__,
                },
            )
        )
        try:
            for candidate in candidates:
                if candidate.category != category or candidate.region != region.strip():
                    skipped += 1
                    continue
                existing = db.scalar(
                    select(Provider).where(
                        Provider.category == category.value,
                        Provider.region == region.strip(),
                        Provider.phone == candidate.phone,
                    )
                )
                if existing is not None and existing.is_validated:
                    skipped += 1
                    continue
                reply = await self.gateway.request_confirmation(candidate, run_id)
                if not await contact_is_confirmed(reply, run_id, db):
                    refused += 1
                    db.add(
                        AuditEvent(
                            run_id=run_id,
                            node="scraper_nodeS",
                            event_type="contact_not_confirmed",
                            payload={"place_id": candidate.place_id},
                        )
                    )
                    continue
                provider = existing or Provider(
                    name=candidate.name,
                    category=category.value,
                    region=region.strip(),
                    phone=candidate.phone,
                    rating=candidate.rating,
                    source=candidate.source,
                )
                provider.is_validated = True
                if existing is None:
                    db.add(provider)
                db.flush()
                provider_ids.append(provider.id)
                confirmed += 1
                db.add(
                    AuditEvent(
                        run_id=run_id,
                        node="scraper_nodeS",
                        event_type="contact_confirmed",
                        payload={"provider_id": provider.id},
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        logger.info(
            "Coleta de prestadores concluída",
            extra={
                "run_id": run_id,
                "confirmed": confirmed,
                "refused": refused,
                "skipped": skipped,
            },
        )
        return CollectionResult(
            run_id,
            type(self.source).__name__,
            len(candidates),
            confirmed,
            refused,
            skipped,
            tuple(provider_ids),
        )


def reserve_places_call(db: Session, run_id: str, max_calls: int) -> None:
    """Reserva uma tentativa no ledger antes da chamada paga, inclusive entre reinícios."""
    _reserve_search(db, run_id, max_calls, "places_search", "Google Places")


def reserve_browser_search(db: Session, run_id: str, max_calls: int) -> None:
    _reserve_search(db, run_id, max_calls, "browser_search", "Agent Browser")


def _reserve_search(
    db: Session,
    run_id: str,
    max_calls: int,
    event_type: str,
    source: str,
) -> None:
    bind = db.get_bind()
    with Session(bind) as quota_db:
        if bind.dialect.name == "postgresql":
            quota_db.execute(text("SELECT pg_advisory_xact_lock(20261107)"))
        used = (
            quota_db.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.node == "scraper_nodeS",
                    AuditEvent.event_type == event_type,
                )
            )
            or 0
        )
        if used >= max_calls:
            raise RuntimeError(f"Limite global de chamadas {source} atingido")
        quota_db.add(
            AuditEvent(
                run_id=run_id,
                node="scraper_nodeS",
                event_type=event_type,
                payload={},
            )
        )
        quota_db.commit()


def make_collector() -> ProviderCollector:
    if (
        settings.provider_source in {"agent_browser", "google_places"}
        and settings.llm_mode.lower() != "recorded_demo"
    ):
        source: CandidateSource
        if settings.provider_source == "agent_browser":
            from app.services.provider_browser import AgentBrowserAdapter

            source = AgentBrowserAdapter(
                settings.agent_browser_command,
                settings.browser_timeout_seconds,
                settings.agent_browser_executable_path,
            )
        else:
            source = GooglePlacesAdapter(
                settings.google_places_api_key, max_calls=settings.max_places_calls
            )
        allowed = {
            phone.strip()
            for phone in settings.provider_contact_allowlist.split(",")
            if phone.strip()
        }
        configured_replies = json.loads(settings.provider_simulated_replies)
        if not isinstance(configured_replies, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in configured_replies.items()
        ):
            raise ValueError("PROVIDER_SIMULATED_REPLIES deve ser um objeto JSON de textos")
        gateway = SimulatedContactGateway(allowed, configured_replies)
    elif settings.provider_source == "fixture" or settings.llm_mode.lower() == "recorded_demo":
        source = FixturePlacesAdapter()
        gateway = SimulatedContactGateway(
            set(FIXTURE_PHONES),
            {
                f"fixture-{category.value}-1": "Sim, confirmo que posso atender."
                for category in ProviderCategory
            }
            | {
                f"fixture-{category.value}-2": "Não posso atender no momento."
                for category in ProviderCategory
            },
        )
    else:
        raise ValueError("PROVIDER_SOURCE deve ser agent_browser, fixture ou google_places")
    return ProviderCollector(source, gateway)


async def collect_on_demand(
    db: Session, category: ProviderCategory, region: str, collector: ProviderCollector | None = None
) -> CollectionResult | None:
    """Fallback do Nó 3: busca apenas quando a categoria/região não têm validados."""
    existing = db.scalar(
        select(Provider.id)
        .where(
            Provider.category == category.value,
            Provider.region == region,
            Provider.is_validated.is_(True),
        )
        .limit(1)
    )
    if existing is not None:
        return None
    return await (collector or make_collector()).collect(db, category, region)
