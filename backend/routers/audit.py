from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AuditLogDB, UserDB
from rbac import require_permission

router = APIRouter()


@router.get("/audit-log")
def get_audit_log(
    card_id: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_permission("ver_log_auditoria")),
):
    q = db.query(AuditLogDB).order_by(AuditLogDB.data.desc())
    if card_id:
        q = q.filter(AuditLogDB.card_id == card_id)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id, "card_id": r.card_id, "card_titulo": r.card_titulo,
            "usuario": r.usuario, "acao": r.acao, "campo": r.campo,
            "valor_antigo": r.valor_antigo, "valor_novo": r.valor_novo,
            "detalhe": r.detalhe, "data": r.data,
        }
        for r in rows
    ]
