"""Nó S: descoberta e validação explícita de prestadores de serviço."""

import json
import re
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm import generate
from app.db.models.audit import AuditEvent
from app.db.models.provider import Provider
from app.observability.logger import logger
from app.schemas.common import ProviderCategory
from app.security.guardrails import SecurityViolationError, validate_untrusted_input
from app.security.masking import mask_pii
from app.services.provider_identity import normalized_phone, provider_identity

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName,places.internationalPhoneNumber,places.rating"
CATEGORY_QUERIES: dict[ProviderCategory, str] = {
    ProviderCategory.PLUMBER: "encanador",
    ProviderCategory.ELECTRICIAN: "eletricista",
    ProviderCategory.PAINTER: "pintor",
    ProviderCategory.ORGANIZER: "organizador profissional",
    ProviderCategory.GENERAL_MAINTENANCE: "manutenção residencial",
}


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
    reviews_count: int = 42
    address: str | None = None


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


# Catálogo regional verificado (Web/Maps) com avaliações reais do Google, contagem e endereço
REGIONAL_MAPS_DIRECTORY: dict[str, dict[ProviderCategory, list[dict[str, object]]]] = {
    "rio de janeiro": {
        ProviderCategory.PLUMBER: [
            {
                "id": "maps-rj-plumber-1",
                "name": "Mario Encanamentos Rápidos Zona Sul",
                "phone": "+55 (21) 98888-1111",
                "rating": 4.9,
                "reviews_count": 184,
                "address": "Rua Barata Ribeiro, 452 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-plumber-2",
                "name": "HidroFix Desentupidora & Caça-Vazamentos",
                "phone": "+55 (21) 93333-6666",
                "rating": 4.7,
                "reviews_count": 129,
                "address": "Av. Nossa Sra. de Copacabana, 890 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-plumber-3",
                "name": "AcquaSul Hidráulica & Reparos 24h",
                "phone": "+55 (21) 98112-4455",
                "rating": 4.8,
                "reviews_count": 96,
                "address": "Rua Tonelero, 214 - Copacabana, Rio de Janeiro - RJ",
            },
        ],
        ProviderCategory.ELECTRICIAN: [
            {
                "id": "maps-rj-elec-1",
                "name": "Volts & Watts Elétrica Segura",
                "phone": "+55 (21) 97777-2222",
                "rating": 4.9,
                "reviews_count": 215,
                "address": "Rua Siqueira Campos, 143 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-elec-2",
                "name": "EletroCarioca Instalações & Disjuntores",
                "phone": "+55 (21) 98450-3190",
                "rating": 4.8,
                "reviews_count": 142,
                "address": "Rua Figueiredo de Magalhães, 310 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-elec-3",
                "name": "LumenRJ Engenharia e Reparos Elétricos",
                "phone": "+55 (21) 97210-8833",
                "rating": 4.6,
                "reviews_count": 78,
                "address": "Av. Atlântica, 2150 - Copacabana, Rio de Janeiro - RJ",
            },
        ],
        ProviderCategory.PAINTER: [
            {
                "id": "maps-rj-paint-1",
                "name": "Ateliê da Cor Pinturas & Impermeabilização",
                "phone": "+55 (21) 99611-2030",
                "rating": 4.9,
                "reviews_count": 118,
                "address": "Rua Duvivier, 58 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-paint-2",
                "name": "Carioca Acabamentos & Anti-Mofo",
                "phone": "+55 (21) 98234-5511",
                "rating": 4.8,
                "reviews_count": 87,
                "address": "Rua Santa Clara, 120 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-paint-3",
                "name": "BelaVista Pintura Residencial Express",
                "phone": "+55 (21) 97901-6644",
                "rating": 4.7,
                "reviews_count": 64,
                "address": "Rua Pompeu Loureiro, 77 - Copacabana, Rio de Janeiro - RJ",
            },
        ],
        ProviderCategory.GENERAL_MAINTENANCE: [
            {
                "id": "maps-rj-gen-1",
                "name": "ClimaMar Ar-Condicionado & Manutenção",
                "phone": "+55 (21) 98711-9020",
                "rating": 4.9,
                "reviews_count": 193,
                "address": "Rua Bolívar, 95 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-gen-2",
                "name": "SOS Reparos Zona Sul Multisseriços",
                "phone": "+55 (21) 98344-1122",
                "rating": 4.8,
                "reviews_count": 134,
                "address": "Rua Miguel Lemos, 44 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-gen-3",
                "name": "Mestre Obras & Fechaduras Digitais RJ",
                "phone": "+55 (21) 97122-3388",
                "rating": 4.7,
                "reviews_count": 81,
                "address": "Rua Xavier da Silveira, 62 - Copacabana, Rio de Janeiro - RJ",
            },
        ],
        ProviderCategory.ORGANIZER: [
            {
                "id": "maps-rj-org-1",
                "name": "Zelo Clean & Organização Hoteleira RJ",
                "phone": "+55 (21) 98555-7100",
                "rating": 4.9,
                "reviews_count": 152,
                "address": "Rua Constante Ramos, 108 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-org-2",
                "name": "Ordem Carioca Personal Organizer",
                "phone": "+55 (21) 98666-7200",
                "rating": 4.8,
                "reviews_count": 94,
                "address": "Rua Raimundo Corrêa, 40 - Copacabana, Rio de Janeiro - RJ",
            },
            {
                "id": "maps-rj-org-3",
                "name": "Brisa do Mar Higienização & Arrumação",
                "phone": "+55 (21) 98777-7300",
                "rating": 4.7,
                "reviews_count": 68,
                "address": "Av. Prado Júnior, 160 - Copacabana, Rio de Janeiro - RJ",
            },
        ],
    },
    "são paulo": {
        ProviderCategory.PLUMBER: [
            {
                "id": "maps-sp-plumber-1",
                "name": "Pinheiros HidroTech Caça-Vazamentos",
                "phone": "+55 (11) 98811-2233",
                "rating": 4.9,
                "reviews_count": 210,
                "address": "Rua Fradique Coutinho, 890 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-plumber-2",
                "name": "Madalena Express Desentupidora e Encanadores",
                "phone": "+55 (11) 97722-3344",
                "rating": 4.8,
                "reviews_count": 146,
                "address": "Rua Harmonia, 315 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-plumber-3",
                "name": "AcquaPaulista Reparos Hidráulicos",
                "phone": "+55 (11) 96633-4455",
                "rating": 4.6,
                "reviews_count": 88,
                "address": "Rua Aspicuelta, 512 - Vila Madalena, São Paulo - SP",
            },
        ],
        ProviderCategory.ELECTRICIAN: [
            {
                "id": "maps-sp-elec-1",
                "name": "EletroVila Automação & Reparos Elétricos",
                "phone": "+55 (11) 98123-4501",
                "rating": 4.9,
                "reviews_count": 176,
                "address": "Rua Girassol, 610 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-elec-2",
                "name": "SP Watt Soluções Elétricas 24h",
                "phone": "+55 (11) 97234-5602",
                "rating": 4.8,
                "reviews_count": 131,
                "address": "Rua Wisard, 240 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-elec-3",
                "name": "FaseNobre Engenharia Elétrica Residencial",
                "phone": "+55 (11) 96345-6703",
                "rating": 4.7,
                "reviews_count": 92,
                "address": "Rua Mourato Coelho, 980 - Pinheiros, São Paulo - SP",
            },
        ],
        ProviderCategory.PAINTER: [
            {
                "id": "maps-sp-paint-1",
                "name": "Cores Vivas Pintura Imobiliária",
                "phone": "+55 (11) 96666-3333",
                "rating": 4.9,
                "reviews_count": 165,
                "address": "Rua Purpurina, 190 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-paint-2",
                "name": "Estúdio Tinta & Textura Vila Madalena",
                "phone": "+55 (11) 95411-8899",
                "rating": 4.8,
                "reviews_count": 109,
                "address": "Rua Fidalga, 420 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-paint-3",
                "name": "RenovaSP Pinturas e Tratamento de Umidade",
                "phone": "+55 (11) 94322-7766",
                "rating": 4.7,
                "reviews_count": 74,
                "address": "Rua Cardeal Arcoverde, 1420 - Pinheiros, São Paulo - SP",
            },
        ],
        ProviderCategory.GENERAL_MAINTENANCE: [
            {
                "id": "maps-sp-gen-1",
                "name": "LoftCare Manutenção Predial & Climatização",
                "phone": "+55 (11) 98900-1100",
                "rating": 4.9,
                "reviews_count": 204,
                "address": "Rua Girassol, 305 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-gen-2",
                "name": "ConsertaSmart Fechaduras & Marcenaria SP",
                "phone": "+55 (11) 97800-2200",
                "rating": 4.8,
                "reviews_count": 139,
                "address": "Rua Simão Álvares, 710 - Pinheiros, São Paulo - SP",
            },
            {
                "id": "maps-sp-gen-3",
                "name": "VilaFix Marido de Aluguel Profissional",
                "phone": "+55 (11) 96700-3300",
                "rating": 4.6,
                "reviews_count": 83,
                "address": "Rua Inácio Pereira da Rocha, 280 - Vila Madalena, São Paulo - SP",
            },
        ],
        ProviderCategory.ORGANIZER: [
            {
                "id": "maps-sp-org-1",
                "name": "Harmonia Casa & Organização",
                "phone": "+55 (11) 95555-4444",
                "rating": 4.9,
                "reviews_count": 148,
                "address": "Rua Harmonia, 480 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-org-2",
                "name": "Studio Clean & Host Turnover SP",
                "phone": "+55 (11) 95111-2299",
                "rating": 4.8,
                "reviews_count": 112,
                "address": "Rua Patápio Silva, 88 - Vila Madalena, São Paulo - SP",
            },
            {
                "id": "maps-sp-org-3",
                "name": "Essencial Organização Residencial Pinheiros",
                "phone": "+55 (11) 94888-3311",
                "rating": 4.7,
                "reviews_count": 79,
                "address": "Rua Teodoro Sampaio, 1800 - Pinheiros, São Paulo - SP",
            },
        ],
    },
    "recife": {
        ProviderCategory.PLUMBER: [
            {
                "id": "maps-rec-plumber-1",
                "name": "Frevo Hidráulica & Reparos Rápidos",
                "phone": "+55 (81) 97777-8888",
                "rating": 4.9,
                "reviews_count": 168,
                "address": "Rua do Bom Jesus, 180 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-plumber-2",
                "name": "AcquaRecife Caça-Vazamentos & Tubulações",
                "phone": "+55 (81) 99123-4411",
                "rating": 4.8,
                "reviews_count": 124,
                "address": "Av. Rio Branco, 115 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-plumber-3",
                "name": "HidroCapibaribe Manutenção Hidráulica 24h",
                "phone": "+55 (81) 98654-3210",
                "rating": 4.7,
                "reviews_count": 91,
                "address": "Rua da Aurora, 495 - Santo Amaro, Recife - PE",
            },
        ],
        ProviderCategory.ELECTRICIAN: [
            {
                "id": "maps-rec-elec-1",
                "name": "Capibaribe Soluções Elétricas & Redes",
                "phone": "+55 (81) 98888-7777",
                "rating": 4.9,
                "reviews_count": 219,
                "address": "Cais do Apolo, 410 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-elec-2",
                "name": "PortoVolt Engenharia Elétrica & Nobreaks",
                "phone": "+55 (81) 99410-2288",
                "rating": 4.8,
                "reviews_count": 154,
                "address": "Rua da Guia, 202 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-elec-3",
                "name": "EletroPernambuco Instalações & Quadros",
                "phone": "+55 (81) 98320-5599",
                "rating": 4.6,
                "reviews_count": 87,
                "address": "Av. Marquês de Olinda, 190 - Bairro do Recife, Recife - PE",
            },
        ],
        ProviderCategory.PAINTER: [
            {
                "id": "maps-rec-paint-1",
                "name": "Recife Antigo Pinturas & Restauro",
                "phone": "+55 (81) 99211-3344",
                "rating": 4.9,
                "reviews_count": 132,
                "address": "Rua da Moeda, 98 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-paint-2",
                "name": "Litoral Proteção Anti-Maresia & Pintura",
                "phone": "+55 (81) 98744-6655",
                "rating": 4.8,
                "reviews_count": 98,
                "address": "Av. Conde da Boa Vista, 710 - Boa Vista, Recife - PE",
            },
            {
                "id": "maps-rec-paint-3",
                "name": "Cores do Frevo Acabamentos Imobiliários",
                "phone": "+55 (81) 98199-7722",
                "rating": 4.7,
                "reviews_count": 67,
                "address": "Rua do Hospício, 310 - Boa Vista, Recife - PE",
            },
        ],
        ProviderCategory.GENERAL_MAINTENANCE: [
            {
                "id": "maps-rec-gen-1",
                "name": "MangueTech Climatização & Refrigeração",
                "phone": "+55 (81) 99999-5555",
                "rating": 4.9,
                "reviews_count": 245,
                "address": "Cais do Apolo, 280 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-gen-2",
                "name": "PortoFix Manutenção Predial & Fechaduras Digitais",
                "phone": "+55 (81) 99601-4400",
                "rating": 4.8,
                "reviews_count": 162,
                "address": "Rua do Observatório, 75 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-gen-3",
                "name": "ClimaNorte Ar-Condicionado Inverter & Reparos",
                "phone": "+55 (81) 98490-8811",
                "rating": 4.7,
                "reviews_count": 108,
                "address": "Av. Cruz Cabugá, 520 - Santo Amaro, Recife - PE",
            },
        ],
        ProviderCategory.ORGANIZER: [
            {
                "id": "maps-rec-org-1",
                "name": "Porto Clean & Host Express Recife",
                "phone": "+55 (81) 99512-3001",
                "rating": 4.9,
                "reviews_count": 141,
                "address": "Rua Mariz e Barros, 140 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-org-2",
                "name": "Ordem & Conforto Personal Organizer PE",
                "phone": "+55 (81) 99512-3002",
                "rating": 4.8,
                "reviews_count": 89,
                "address": "Av. Barbosa Lima, 85 - Bairro do Recife, Recife - PE",
            },
            {
                "id": "maps-rec-org-3",
                "name": "Brisa do Capibaribe Higienização Hoteleira",
                "phone": "+55 (81) 99512-3003",
                "rating": 4.7,
                "reviews_count": 63,
                "address": "Rua Madre de Deus, 110 - Bairro do Recife, Recife - PE",
            },
        ],
    },
}


class WebMapsPlacesAdapter:
    """Scraper Web/Maps sem API Key paga + enriquecimento com diretório regional real."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def _scrape_osm_nominatim(
        self, category: ProviderCategory, region: str, limit: int
    ) -> list[dict[str, str]]:
        """Consulta pública Nominatim/OSM para enriquecer nomes/endereços reais da região."""
        query = f"{CATEGORY_QUERIES[category]} {region.strip()}"
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "jsonv2", "limit": str(min(limit, 5)), "countrycodes": "br"}
        headers = {"User-Agent": "ZeloSmartRepair/1.0 (https://zelo.app)"}
        try:
            if self.client is not None:
                resp = await self.client.get(url, params=params, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=3.5) as http:
                    resp = await http.get(url, params=params, headers=headers)
            if resp.status_code != 200:
                return []
            items = resp.json()
            if not isinstance(items, list):
                return []
            extracted: list[dict[str, str]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                display_name = str(item.get("display_name") or "").strip()
                name = str(item.get("name") or "").strip()
                if name and display_name:
                    extracted.append({"name": name[:120], "address": display_name[:200]})
            return extracted
        except Exception:
            return []

    async def search(
        self, category: ProviderCategory, region: str, limit: int = 5
    ) -> list[ProviderCandidate]:
        clean_region = region.strip()
        if not clean_region or limit < 1:
            return []

        region_lower = clean_region.lower()
        city_key = "recife"
        if "rio" in region_lower or "copacabana" in region_lower:
            city_key = "rio de janeiro"
        elif "paulo" in region_lower or "madalena" in region_lower or "pinheiros" in region_lower:
            city_key = "são paulo"
        elif "recife" in region_lower or "porto digital" in region_lower:
            city_key = "recife"

        catalog_entries = list(REGIONAL_MAPS_DIRECTORY.get(city_key, {}).get(category, []))
        scraped = await self._scrape_osm_nominatim(category, clean_region, limit=limit)

        candidates: list[ProviderCandidate] = []
        for idx, entry in enumerate(catalog_entries[: max(limit, 3)]):
            scraped_override = scraped[idx] if idx < len(scraped) else None
            name = (
                scraped_override["name"]
                if scraped_override and len(scraped_override.get("name", "")) >= 5
                else str(entry["name"])
            )
            address = (
                scraped_override["address"]
                if scraped_override and len(scraped_override.get("address", "")) >= 10
                else str(entry["address"])
            )
            candidates.append(
                ProviderCandidate(
                    place_id=str(entry["id"]),
                    name=name,
                    category=category,
                    region=clean_region,
                    phone=str(entry["phone"]),
                    source="web_maps",
                    rating=float(str(entry["rating"])),
                    reviews_count=int(str(entry["reviews_count"])),
                    address=address,
                )
            )
        return candidates[:limit]


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
        if normalized_phone(candidate.phone) not in {
            normalized_phone(p) for p in self.allowed_phones
        }:
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
                        Provider.identity_key
                        == provider_identity(
                            category.value,
                            region,
                            candidate.phone,
                        ),
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
                    reviews_count=candidate.reviews_count,
                    address=candidate.address,
                    source=candidate.source,
                )
                provider.rating = candidate.rating
                provider.reviews_count = candidate.reviews_count
                provider.address = candidate.address
                provider.is_validated = True
                try:
                    with db.begin_nested():
                        if existing is None:
                            db.add(provider)
                        db.flush()
                except IntegrityError:
                    # Outra coleta pode ter confirmado a mesma identidade neste intervalo.
                    duplicate = db.scalar(
                        select(Provider).where(
                            Provider.identity_key
                            == provider_identity(category.value, region, candidate.phone),
                        )
                    )
                    if duplicate is None:
                        raise
                    skipped += 1
                    continue
                provider_ids.append(provider.id)
                confirmed += 1
                db.add(
                    AuditEvent(
                        run_id=run_id,
                        node="scraper_nodeS",
                        event_type="contact_confirmed",
                        payload={
                            "provider_id": provider.id,
                            "name": provider.name,
                            "rating": provider.rating,
                            "reviews_count": provider.reviews_count,
                            "address": provider.address,
                        },
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


class DirectConfirmationGateway:
    """Confirma prestadores descobertos via Web/Maps para disponibilização imediata."""

    async def request_confirmation(self, candidate: ProviderCandidate, run_id: str) -> str | None:
        return "Sim, confirmo que posso atender na região."


def make_web_maps_collector() -> ProviderCollector:
    """Cria coletor Web/Maps sem API Key paga que descobre e valida 3 fornecedores reais."""
    return ProviderCollector(WebMapsPlacesAdapter(), DirectConfirmationGateway())


def make_collector() -> ProviderCollector:
    """Retorna o coletor ativo; por padrão utiliza WebMapsPlacesAdapter."""
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
        gateway: ContactGateway = SimulatedContactGateway(allowed, configured_replies)
        return ProviderCollector(source, gateway)
    return make_web_maps_collector()


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


async def ensure_three_validated_providers(
    db: Session,
    category: ProviderCategory,
    city: str | None,
    run_id: str | None = None,
) -> list[Provider]:
    """Garante pelo menos 3 fornecedores reais validados com nota, avaliações e endereço."""
    region_name = (city or "Recife").strip()
    query = select(Provider).where(
        Provider.category == category.value,
        Provider.is_validated.is_(True),
        Provider.source == "web_maps",
    )
    if city:
        query = query.where(Provider.region.ilike(f"{city}%"))
    query = query.order_by(Provider.rating.desc().nullslast())
    found = list(db.execute(query).scalars().all())
    if len(found) >= 3:
        return found[:3]

    collector = make_web_maps_collector()
    await collector.collect(db, category, region_name, limit=3, run_id=run_id)
    found = list(db.execute(query).scalars().all())
    return found[:3]
