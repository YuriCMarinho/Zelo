"""Fluxo B: confirmação, recusa, allowlist, fallback e adaptador Places."""

from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.audit import AuditEvent
from app.db.models.property import Property
from app.db.models.provider import Provider
from app.scheduler import provider_jobs
from app.schemas.common import ProviderCategory
from app.services.provider_collector import (
    FIELD_MASK,
    PLACES_URL,
    GooglePlacesAdapter,
    ProviderCandidate,
    ProviderCollector,
    SimulatedContactGateway,
    collect_on_demand,
    make_collector,
    reserve_places_call,
)


@pytest.mark.asyncio
async def test_fixture_only_persists_explicit_confirmation(db_session: Session) -> None:
    collector = make_collector()
    result = await collector.collect(db_session, ProviderCategory.PLUMBER, "Fortaleza, CE")

    UUID(result.run_id)
    assert result.discovered == 2
    assert result.confirmed == 1
    assert result.refused == 1
    providers = db_session.scalars(select(Provider)).all()
    assert len(providers) == 1
    assert providers[0].is_validated is True
    assert providers[0].phone == "+55 11 90000-0001"
    events = db_session.scalars(select(AuditEvent).where(AuditEvent.run_id == result.run_id)).all()
    assert {event.event_type for event in events} == {
        "collection_started",
        "contact_confirmed",
        "contact_not_confirmed",
    }
    assert all("phone" not in event.payload for event in events)


@pytest.mark.asyncio
async def test_refusal_and_allowlist_never_activate_provider(db_session: Session) -> None:
    candidate = ProviderCandidate(
        place_id="external-1",
        name="Prestador de teste",
        category=ProviderCategory.ELECTRICIAN,
        region="Fortaleza, CE",
        phone="+55 85 90000-0999",
        source="google_places",
    )
    source = AsyncMock()
    source.search.return_value = [candidate]
    gateway = SimulatedContactGateway(set(), {candidate.place_id: "Sim, confirmo."})
    result = await ProviderCollector(source, gateway).collect(
        db_session, ProviderCategory.ELECTRICIAN, "Fortaleza, CE"
    )
    assert result.confirmed == 0
    assert gateway.sent == []
    assert db_session.scalar(select(Provider.id)) is None

    gateway = SimulatedContactGateway(
        {candidate.phone}, {candidate.place_id: "Sim, mas não posso atender."}
    )
    result = await ProviderCollector(source, gateway).collect(
        db_session, ProviderCategory.ELECTRICIAN, "Fortaleza, CE"
    )
    assert result.refused == 1
    assert len(gateway.sent) == 1
    assert "confirma" in gateway.sent[0].body
    assert gateway.sent[0].recipient_phone == candidate.phone
    assert db_session.scalar(select(Provider.id)) is None


@pytest.mark.asyncio
async def test_fallback_collects_only_when_no_validated_provider(db_session: Session) -> None:
    collector = make_collector()
    first = await collect_on_demand(
        db_session, ProviderCategory.PAINTER, "Fortaleza, CE", collector
    )
    assert first is not None
    assert first.confirmed == 1
    assert (
        await collect_on_demand(db_session, ProviderCategory.PAINTER, "Fortaleza, CE", collector)
        is None
    )
    assert db_session.scalars(select(Provider).where(Provider.is_validated.is_(True))).one()


@pytest.mark.asyncio
async def test_google_places_adapter_uses_field_mask_and_skips_missing_phone() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == PLACES_URL
        assert request.headers["X-Goog-FieldMask"] == FIELD_MASK
        assert request.headers["X-Goog-Api-Key"] == "test-key"
        assert '"pageSize":2' in request.content.decode()
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "places-1",
                        "displayName": {"text": "Serviço A"},
                        "internationalPhoneNumber": "+55 85 90000-0001",
                        "rating": 4.6,
                    },
                    {"id": "places-2", "displayName": {"text": "Sem telefone"}},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = GooglePlacesAdapter("test-key", max_calls=1, client=client)
        found = await adapter.search(ProviderCategory.PLUMBER, "Fortaleza, CE", limit=2)
        assert len(found) == 1
        assert found[0].source == "google_places"
        with pytest.raises(RuntimeError, match="Limite"):
            await adapter.search(ProviderCategory.PLUMBER, "Fortaleza, CE", limit=2)


@pytest.mark.asyncio
async def test_periodic_job_reuses_one_run_id_for_all_categories(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(
        Property(
            name="Imóvel teste", description="Demo", address="Rua X", city="Fortaleza", state="CE"
        )
    )
    db_session.commit()
    monkeypatch.setattr(provider_jobs, "SessionLocal", lambda: db_session)
    collector = make_collector()
    run_id = await provider_jobs.run_periodic_collection(collector)
    UUID(run_id)
    events = db_session.scalars(select(AuditEvent).where(AuditEvent.run_id == run_id)).all()
    assert len([event for event in events if event.event_type == "collection_started"]) == len(
        ProviderCategory
    )
    assert all(event.run_id == run_id for event in events)


def test_scheduler_registers_periodic_node_s_job() -> None:
    scheduler = provider_jobs.create_provider_scheduler()
    job = scheduler.get_job("provider_collector_node_s")
    assert job is not None
    assert job.max_instances == 1


@pytest.mark.asyncio
async def test_google_source_uses_only_configured_simulator_replies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "provider_source", "google_places")
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(settings, "provider_contact_allowlist", "+55 85 90000-0001")
    monkeypatch.setattr(settings, "provider_simulated_replies", '{"places-1":"Sim, confirmo."}')
    collector = make_collector()
    allowed = ProviderCandidate(
        "places-1",
        "Prestador teste",
        ProviderCategory.PLUMBER,
        "Fortaleza, CE",
        "+55 85 90000-0001",
        "google_places",
    )
    blocked = ProviderCandidate(
        "places-2",
        "Outro teste",
        ProviderCategory.PLUMBER,
        "Fortaleza, CE",
        "+55 85 90000-0002",
        "google_places",
    )
    assert await collector.gateway.request_confirmation(allowed, "run-1") == "Sim, confirmo."
    assert await collector.gateway.request_confirmation(blocked, "run-1") is None
    assert isinstance(collector.gateway, SimulatedContactGateway)
    assert len(collector.gateway.sent) == 1


def test_provider_api_only_exposes_validated_and_masked_contacts(
    client: TestClient, db_session: Session
) -> None:
    db_session.add_all(
        [
            Provider(
                name="Ativo",
                category="plumber",
                region="Fortaleza, CE",
                phone="+55 85 90000-0001",
                is_validated=True,
            ),
            Provider(
                name="Pendente",
                category="plumber",
                region="Fortaleza, CE",
                phone="+55 85 90000-0002",
                is_validated=False,
            ),
        ]
    )
    db_session.commit()
    response = client.get("/api/providers", params={"category": "plumber"})
    assert response.status_code == 200
    assert [provider["name"] for provider in response.json()] == ["Ativo"]
    assert "+55 85 90000-0001" not in response.text


def test_manual_fallback_endpoint_is_limited_to_demo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    response = client.post(
        "/api/providers/collect", json={"category": "plumber", "region": "Fortaleza, CE"}
    )
    assert response.status_code == 403


def test_places_quota_is_persisted_between_adapter_instances(db_session: Session) -> None:
    reserve_places_call(db_session, "run-a", max_calls=1)
    with pytest.raises(RuntimeError, match="Limite global"):
        reserve_places_call(db_session, "run-b", max_calls=1)
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "places_search")
    ).all()
    assert len(events) == 1
    assert events[0].run_id == "run-a"
