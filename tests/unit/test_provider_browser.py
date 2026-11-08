from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditEvent
from app.schemas.common import ProviderCategory
from app.services.provider_browser import AgentBrowserAdapter, BrowserSearchError, parse_cards
from app.services.provider_collector import (
    SimulatedContactGateway,
    make_collector,
    reserve_browser_search,
)


def card(name: str = "Serviços teste", phone: str = "(85) 98888-1234") -> dict:
    return {
        "name": name,
        "url": "https://www.google.com/maps/place/Servicos/data=!4m7!1s0xabc:0x123!8m2?tracking=1",
        "text": f"{name}\n4,8\nEncanador · Fortaleza\nAberto 24 horas · {phone}",
    }


def test_cards_require_public_phone_and_deduplicate_formatted_numbers() -> None:
    results = parse_cards(
        [card(), card(phone="+55 85 98888-1234"), card("Sem contato", "não informado")],
        ProviderCategory.PLUMBER,
        "Fortaleza, CE",
        5,
    )
    assert len(results) == 1
    result = results[0]
    assert result.phone == "+5585988881234"
    assert result.rating == 4.8
    assert result.source == "agent_browser"
    assert result.place_id == "maps:0xabc:0x123"
    assert "tracking" not in result.source_url


def test_cards_ignore_invalid_links_and_respect_limit() -> None:
    invalid = card()
    invalid["url"] = "https://example.com/forged"
    results = parse_cards(
        [invalid, {}, None, card(), card("Outro", "(85) 98888-5678")],
        ProviderCategory.PLUMBER,
        "Fortaleza, CE",
        1,
    )
    assert len(results) == 1
    assert results[0].name == "Serviços teste"


@pytest.mark.asyncio
async def test_search_uses_isolated_session_encoded_query_and_always_closes() -> None:
    source = AgentBrowserAdapter()
    source._run = AsyncMock(
        side_effect=[{}, {}, {"result": {"blocked": False, "providers": [card()]}}, {}]
    )
    results = await source.search(ProviderCategory.PLUMBER, "Fortaleza, CE")
    assert len(results) == 1
    calls = source._run.await_args_list
    assert len({call.args[0] for call in calls}) == 1
    assert calls[0].args[1] == "open"
    assert "encanador%20em%20Fortaleza%2C%20CE" in calls[0].args[2]
    assert calls[-1].args[1] == "close"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [{"result": {"blocked": True, "providers": []}}, {"result": "unexpected"}],
)
async def test_blocked_or_changed_page_fails_without_fabricating_results(response: dict) -> None:
    source = AgentBrowserAdapter()
    source._run = AsyncMock(side_effect=[{}, {}, response, {}])
    with pytest.raises(BrowserSearchError):
        await source.search(ProviderCategory.PLUMBER, "Fortaleza, CE")
    assert source._run.await_args_list[-1].args[1] == "close"


@pytest.mark.asyncio
async def test_navigation_timeout_still_closes_session() -> None:
    source = AgentBrowserAdapter()
    source._run = AsyncMock(side_effect=[TimeoutError(), {}])
    with pytest.raises(BrowserSearchError, match="Tempo limite"):
        await source.search(ProviderCategory.PLUMBER, "Fortaleza, CE")
    assert source._run.await_args_list[-1].args[1] == "close"


@pytest.mark.asyncio
async def test_missing_browser_reports_installation_instructions() -> None:
    source = AgentBrowserAdapter(command="/nonexistent/agent-browser")
    with pytest.raises(BrowserSearchError, match="npm ci"):
        await source.search(ProviderCategory.PLUMBER, "Fortaleza, CE")


def test_real_browser_source_preserves_contact_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "provider_source", "agent_browser")
    monkeypatch.setattr(settings, "provider_contact_allowlist", "+5585988881234")
    monkeypatch.setattr(settings, "provider_simulated_replies", '{"maps:abc":"Sim, confirmo."}')
    collector = make_collector()
    assert isinstance(collector.source, AgentBrowserAdapter)
    assert isinstance(collector.gateway, SimulatedContactGateway)
    assert collector.gateway.allowed_phones == {"+5585988881234"}


def test_browser_search_limit_is_persistent(db_session: Session) -> None:
    reserve_browser_search(db_session, "browser-1", 1)
    with pytest.raises(RuntimeError, match="Limite global"):
        reserve_browser_search(db_session, "browser-2", 1)
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "browser_search")
    ).all()
    assert len(events) == 1


def test_recorded_demo_never_starts_a_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "provider_source", "agent_browser")
    monkeypatch.setattr(settings, "llm_mode", "recorded_demo")
    assert not isinstance(make_collector().source, AgentBrowserAdapter)
