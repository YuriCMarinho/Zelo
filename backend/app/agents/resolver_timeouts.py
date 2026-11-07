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


def register_quote_timeout(
    ticket_id: str,
    run_id: str,
    timeout_minutes: int,
    callback: Callable[..., Any],
    scheduler: BaseScheduler | None = None,
) -> str:
    """Registra timer de timeout para recebimento de orçamentos de prestadores.

    Se o scheduler for fornecido e estiver ativo, agenda execução com trigger date.
    Também grava metadados no acumulador em memória.
    """
    job_id = f"timeout_quote_{ticket_id}"
    run_at = datetime.now(UTC) + timedelta(minutes=timeout_minutes)

    _active_timeout_jobs[job_id] = {
        "job_id": job_id,
        "type": "quote_timeout",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "timeout_minutes": timeout_minutes,
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
                "Timer de timeout de orçamentos agendado no APScheduler",
                extra={"job_id": job_id},
            )
        except Exception as exc:
            logger.warning(
                "Não foi possível agendar no APScheduler; mantido apenas em memória",
                extra={"job_id": job_id, "error": str(exc)},
            )

    return job_id


def register_adm_reminder(
    ticket_id: str,
    run_id: str,
    reminder_minutes: int,
    callback: Callable[..., Any],
    scheduler: BaseScheduler | None = None,
) -> str:
    """Registra lembrete na sessão do ADM caso a aprovação não ocorra no prazo previsto."""
    job_id = f"reminder_adm_{ticket_id}"
    run_at = datetime.now(UTC) + timedelta(minutes=reminder_minutes)

    _active_timeout_jobs[job_id] = {
        "job_id": job_id,
        "type": "adm_reminder",
        "ticket_id": ticket_id,
        "run_id": run_id,
        "reminder_minutes": reminder_minutes,
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
            logger.info("Lembrete para o ADM agendado no APScheduler", extra={"job_id": job_id})
        except Exception as exc:
            logger.warning(
                "Não foi possível agendar no APScheduler; mantido apenas em memória",
                extra={"job_id": job_id, "error": str(exc)},
            )

    return job_id


def cancel_timeout_job(job_id: str, scheduler: BaseScheduler | None = None) -> bool:
    """Cancela um job de timeout previamente agendado quando a ação esperada ocorre a tempo."""
    removed_from_memory = _active_timeout_jobs.pop(job_id, None) is not None

    if scheduler is not None:
        with contextlib.suppress(Exception):
            scheduler.remove_job(job_id)

    return removed_from_memory
