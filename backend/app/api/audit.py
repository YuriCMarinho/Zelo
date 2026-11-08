"""Endpoints HTTP para consulta de eventos de auditoria e trilha dos agentes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models.audit import AuditEvent
from app.db.session import get_db
from app.schemas.audit import AuditEventRead

router = APIRouter(prefix="/api/audit", tags=["Auditoria"])
DatabaseDep = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[AuditEventRead],
    summary="Listar eventos de auditoria",
    description="Retorna a trilha cronológica de ações dos agentes e nós do sistema.",
)
def list_audit_events(
    db: DatabaseDep,
    ticket_id: str | None = None,
    run_id: str | None = None,
    node: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditEvent]:
    query = db.query(AuditEvent)
    if ticket_id:
        query = query.filter(AuditEvent.ticket_id == ticket_id)
    if run_id:
        query = query.filter(AuditEvent.run_id == run_id)
    if node:
        query = query.filter(AuditEvent.node == node)
    return query.order_by(AuditEvent.created_at.desc()).limit(limit).all()
