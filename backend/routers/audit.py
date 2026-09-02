from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AuditLogDB, CardDB, UserDB
from rbac import get_visible_column_ids, require_permission

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

    # `ver_log_auditoria` diz que a pessoa pode ler o histórico, não que ela
    # pode ler o histórico de cards que a restrição de colunas do cargo dela
    # esconde — sem isso o log entrega título, valores antigos/novos e texto
    # das etapas de tudo que ela não deveria enxergar. Entradas órfãs (card já
    # excluído) ficam de fora porque não há mais como provar a visibilidade.
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None:
        visiveis = [
            c.id for c in db.query(CardDB.id).filter(CardDB.status.in_(visible)).all()
        ]
        q = q.filter(AuditLogDB.card_id.in_(visiveis))

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
