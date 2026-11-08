import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm import generate
from app.db.models import CostRecord
from app.demo.replay import RecordedDemoError, recordings
from app.observability.langfuse_client import langfuse_client
from app.services.provider_collector import FixturePlacesAdapter, make_collector


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_mode", "recorded_demo")
    monkeypatch.setattr(settings, "recorded_demo_latency_ms", 0)
    monkeypatch.setattr(httpx, "AsyncClient", Mock(side_effect=AssertionError("Rede proibida")))
    monkeypatch.setattr(langfuse_client, "_client", Mock())
    monkeypatch.setattr(
        langfuse_client,
        "_init_client",
        Mock(side_effect=AssertionError("Langfuse externo proibido")),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key",
    [
        "router.commercial",
        "router.maintenance",
        "commercial.greeting",
        "commercial.unavailable",
        "validator_node2",
        "resolver_adm_summary",
        "resolver_notify_tenant",
        "scraper_nodeS",
    ],
)
async def test_recorded_scenarios_run_without_network_and_bill_zero(
    key: str,
    offline: None,
    db_session: Session,
) -> None:
    entry = recordings()[key]
    messages = entry["messages"]
    if key == "resolver_notify_tenant":
        messages = [
            {
                "role": "user",
                "content": ("Serviço: Vazamento na cozinha. Data/Hora: 2026-11-10T14:00:00+00:00."),
            }
        ]
    response = await generate(
        messages,
        entry["model"],
        320,
        run_id=f"replay-{key}",
        node=entry["node"],
        db=db_session,
    )
    assert response.content
    assert response.cost_usd == 0
    assert response.is_mock
    assert langfuse_client._client is not None
    langfuse_client._client.trace.assert_not_called()
    cost = db_session.query(CostRecord).filter_by(run_id=f"replay-{key}").one()
    assert cost.cost_usd == 0
    assert cost.is_mock
    if key == "resolver_notify_tenant":
        assert "2026-11-10T14:00:00+00:00" in response.content
        assert "Vazamento na cozinha" in response.content
        assert "{{" not in response.content


def test_recordings_have_real_capture_provenance() -> None:
    for entry in recordings().values():
        assert entry["source"] == "featherless"
        assert entry["capture_run_id"].startswith("recorded-demo-capture-")
        assert entry["capture_cost_usd"] > 0
        digest = hashlib.sha256(json.dumps(entry["messages"]).encode()).hexdigest()
        assert entry["prompt_sha256"] == digest


@pytest.mark.asyncio
async def test_unknown_mode_never_falls_back_to_paid_inference(
    offline: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_mode", "typo")
    with pytest.raises(ValueError, match="LLM_MODE inválido"):
        await generate([], "Qwen/Qwen3.5-4B", 48, run_id="bad-mode", node="router")


@pytest.mark.asyncio
async def test_unsupported_recording_fails_without_paid_fallback(offline: None) -> None:
    with pytest.raises(RecordedDemoError, match="Sem gravação"):
        await generate([], "Qwen/Qwen3.5-4B", 48, run_id="no-record", node="unknown")


@pytest.mark.asyncio
async def test_recorded_structured_output_is_validated(offline: None) -> None:
    class Decision(BaseModel):
        confirmed: bool

    response = await generate(
        [{"role": "user", "content": "Talvez."}],
        "Qwen/Qwen3.5-4B",
        64,
        run_id="contact-replay",
        node="scraper_nodeS",
        response_format=Decision,
    )
    assert isinstance(response.parsed, Decision)
    assert response.parsed.confirmed is False


@pytest.mark.asyncio
async def test_contingency_still_works_when_inference_budget_is_exhausted(
    offline: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "max_cost_global_usd", 0)
    response = await generate(
        [{"role": "user", "content": "Olá!"}],
        "Qwen/Qwen3.5-9B",
        256,
        run_id="exhausted-budget-replay",
        node="commercial_node1",
    )
    assert response.cost_usd == 0


@pytest.mark.parametrize("mode", ["recorded_demo", "RECORDED_DEMO"])
def test_contingency_forces_local_provider_source(
    offline: None,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setattr(settings, "llm_mode", mode)
    monkeypatch.setattr(settings, "provider_source", "google_places")
    assert isinstance(make_collector().source, FixturePlacesAdapter)


def test_missing_recordings_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    recordings.cache_clear()
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=FileNotFoundError))
    with pytest.raises(RecordedDemoError, match="indisponível"):
        recordings()
    recordings.cache_clear()
