"""Endpoint para reinicialização rápida de demonstração (1-Click Demo Reset).

Permite que avaliadores e jurados do hackathon restaurem o estado original
dos imóveis, reservas e prestadores com apenas um clique, limpando tickets
transacionais e acumuladores de custo sem precisar reiniciar os containers.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.budget import reset_in_memory_costs
from app.db.models import (
    AuditEvent,
    Booking,
    ChatMessageRecord,
    CostRecord,
    MaintenanceTicket,
    Property,
    Quote,
)
from app.db.seed import run_seed
from app.db.session import get_db

demo_router = APIRouter(prefix="/api/demo", tags=["Demonstração"])
DatabaseDep = Annotated[Session, Depends(get_db)]

SEED_BOOKING_IDS = {
    "book-copa-current",
    "book-copa-future",
    "book-vila-future",
    "book-recife-future",
}


@demo_router.post("/reset")
def reset_demo(db: DatabaseDep) -> dict[str, Any]:
    """Restaura o estado do banco e memória para o estado limpo de demonstração."""
    # 1. Limpa tabelas transacionais de execuções anteriores
    db.query(Quote).delete()
    db.query(MaintenanceTicket).delete()
    db.query(CostRecord).delete()
    db.query(AuditEvent).delete()
    db.query(ChatMessageRecord).delete()
    db.query(Booking).filter(~Booking.id.in_(SEED_BOOKING_IDS)).delete(synchronize_session=False)
    db.commit()

    # 2. Reseta ledger de custos em memória
    reset_in_memory_costs()

    # 3. Executa seed idempotente garantindo imóveis, reservas e prestadores
    seed_counts = run_seed(db=db)

    # 4. Registra evento de auditoria informando o reset
    audit = AuditEvent(
        run_id="run-demo-reset",
        ticket_id=None,
        node="system_demo",
        event_type="DEMO_RESET",
        payload={"details": "Ambiente de demonstração reinicializado para avaliação."},
    )
    db.add(audit)
    db.commit()

    props_count = db.query(Property).count()

    return {
        "status": "success",
        "message": "Ambiente de demonstração reinicializado com sucesso!",
        "properties_count": props_count,
        "seed_details": seed_counts,
    }
