"""Gestão de timeouts e lembretes para o Nó 3 (Resolvedor).

Permite registrar jobs de timeout para respostas de prestadores e lembretes para
aprovação do ADM via APScheduler sem acoplar diretamente em backend/app/scheduler/.
"""

import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.base import BaseScheduler  # type: ignore[import-untyped]

logger = logging.getLogger("smartrepair.resolver_timeouts")

# Registro em memória de timers ativos para rastreamento e facilidade de testes
_active_timeout_jobs: dict[str, dict[str, Any]] = {}


def clear_active_timeouts() -> None:
    """Limpa o registro de timers ativos (útil para testes unitários)."""
    _active_timeout_jobs.clear()


def get_active_timeouts() -> dict[str, dict[str, Any]]:
    """Retorna cópia do dicionário de timeouts ativos."""
    return dict(_active_timeout_jobs)


def _register_job(
    job_id: str,
    job_type: str,
    ticket_id: str,
    run_id: str,
    delay_minutes: int,
    callback: Callable[..., Any],
    scheduler: BaseScheduler | None = None,
) -> str:
    """Função utilitária interna para agendamento compartilhado de jobs e lembretes."""
    run_at = datetime.now(UTC) + timedelta(minutes=delay_minutes)

    _active_timeout_jobs[job_id] = {
        "job_id": job_id,
        "type": job_type,
        "ticket_id": ticket_id,
        "run_id": run_id,
        "delay_minutes": delay_minutes,
        "run_at": run_at,
        "callback": callback,
    }

    if scheduler is not None:
        try:
            scheduler.add_job(
                callback,
                trigger="date",
                run_date=run_at,
                id=job_id,
                replace_existing=True,
                args=[ticket_id, run_id],
            )
            logger.info(
                f"Timer de {job_type} agendado no APScheduler",
                extra={"job_id": job_id, "ticket_id": ticket_id, "run_id": run_id},
            )
        except Exception as exc:
            logger.warning(
                f"Não foi possível agendar {job_type} no APScheduler; mantido apenas em memória",
                extra={
                    "job_id": job_id,
                    "ticket_id": ticket_id,
                    "run_id": run_id,
                    "error": str(exc),
                },
            )

    return job_id


def register_quote_timeout(
    ticket_id: str,
    run_id: str,
    timeout_minutes: int,
    callback: Callable[..., Any],
    scheduler: BaseScheduler | None = None,
) -> str:
    """Registra timer de timeout para recebimento de orçamentos de prestadores."""
    job_id = f"timeout_quote_{ticket_id}"
    return _register_job(
        job_id=job_id,
        job_type="quote_timeout",
        ticket_id=ticket_id,
        run_id=run_id,
        delay_minutes=timeout_minutes,
        callback=callback,
        scheduler=scheduler,
    )


def register_adm_reminder(
    ticket_id: str,
    run_id: str,
    reminder_minutes: int,
    callback: Callable[..., Any],
    scheduler: BaseScheduler | None = None,
) -> str:
    """Registra lembrete na sessão do ADM caso a aprovação não ocorra no prazo previsto."""
    job_id = f"reminder_adm_{ticket_id}"
    return _register_job(
        job_id=job_id,
        job_type="adm_reminder",
        ticket_id=ticket_id,
        run_id=run_id,
        delay_minutes=reminder_minutes,
        callback=callback,
        scheduler=scheduler,
    )


def cancel_timeout_job(job_id: str, scheduler: BaseScheduler | None = None) -> bool:
    """Cancela um job de timeout previamente agendado quando a ação esperada ocorre a tempo."""
    removed_from_memory = _active_timeout_jobs.pop(job_id, None) is not None

    if scheduler is not None:
        with contextlib.suppress(Exception):
            scheduler.remove_job(job_id)

    return removed_from_memory
