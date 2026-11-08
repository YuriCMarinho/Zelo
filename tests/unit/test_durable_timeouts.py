import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.agents.resolver_graph import on_quote_timeout
from app.agents.resolver_timeouts import cancel_timeout_job, register_quote_timeout
from app.scheduler.provider_jobs import create_provider_scheduler


@pytest.mark.asyncio
async def test_pending_timeout_survives_scheduler_restart(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    monkeypatch.setattr("app.db.session.engine", engine)
    first = create_provider_scheduler()
    first.start(paused=True)
    job_id = register_quote_timeout("durable-ticket", "durable-run", 30, on_quote_timeout, first)
    original_deadline = first.get_job(job_id).next_run_time
    first.shutdown(wait=False)
    await asyncio.sleep(0)
    second = create_provider_scheduler()
    second.start(paused=True)
    try:
        restored = second.get_job(job_id)
        assert restored is not None
        assert restored.next_run_time == original_deadline
        assert restored.misfire_grace_time is None
        assert cancel_timeout_job(job_id, second)
        assert second.get_job(job_id) is None
    finally:
        second.remove_all_jobs()
        second.shutdown(wait=False)
        await asyncio.sleep(0)
