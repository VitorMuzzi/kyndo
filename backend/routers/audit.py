from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from lixeira import expira_em, purgar_lixeira
from models import AuditLogDB, CardDB, LixeiraDB, UserDB
from rbac import get_user_permissions, get_visible_column_ids, require_permission
from reversao import EXCLUSOES, Conflito, desfazer, disponibilidade, permissao_extra
from security import get_current_user

router = APIRouter()


@router.get("/audit-log")
def get_audit_log(
    card_id: Optional[str] = None,
    somente: Optional[str] = None,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_permission("ver_log_auditoria")),
):
    purgar_lixeira(db)
    q = db.query(AuditLogDB).order_by(AuditLogDB.data.desc())
    if card_id:
        q = q.filter(AuditLogDB.card_id == card_id)
    if somente == "exclusoes":
        q = q.filter(AuditLogDB.acao.in_(EXCLUSOES))

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
    permissoes = get_user_permissions(db, current_user.id)
    pode_restaurar = "restaurar_alteracoes" in permissoes
    lixeira_viva = {i for (i,) in db.query(LixeiraDB.id).all()}
    agora = datetime.now()

    def estado(r):
        motivo = disponibilidade(r, agora, lixeira_viva)
        return {
            # `reversao` nunca sai daqui: é dado interno (e numa nota apagada
            # aponta pra lixeira de outra pessoa).
            "pode_desfazer": pode_restaurar and motivo == "" and permissao_extra(r) in (None, *permissoes),
            "motivo_indisponivel": motivo or None,
            "eh_exclusao": r.acao in EXCLUSOES,
        }

    return [
        {
            "id": r.id, "card_id": r.card_id, "card_titulo": r.card_titulo,
            "usuario": r.usuario, "acao": r.acao, "campo": r.campo,
            "valor_antigo": r.valor_antigo, "valor_novo": r.valor_novo,
            "detalhe": r.detalhe, "data": r.data, "alvo_tipo": r.alvo_tipo,
            "revertido_por": r.revertido_por, "revertido_em": r.revertido_em,
            **estado(r),
        }
        for r in rows
    ]


@router.post("/audit-log/{log_id}/desfazer")
def desfazer_registro(log_id: str, db: Session = Depends(get_db),
                      current_user: UserDB = Depends(require_permission("restaurar_alteracoes"))):
    log = db.query(AuditLogDB).filter(AuditLogDB.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    # Mesma régua da listagem: quem tem colunas restritas só mexe no que
    # enxerga — card existente e numa coluna visível.
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None:
        card = db.query(CardDB).filter(CardDB.id == log.card_id).first() if log.card_id else None
        if card is None or card.status not in visible:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
    try:
        mensagem = desfazer(db, log, current_user)
    except Conflito as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    db.commit()
    return {"ok": True, "mensagem": mensagem}


@router.get("/lixeira")
def minha_lixeira(tipo: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Lixeira pessoal de notas e desenhos — o dono recupera sem depender de
    quem tem acesso à auditoria."""
    if tipo not in ("nota", "desenho"):
        raise HTTPException(status_code=400, detail="tipo deve ser nota ou desenho")
    purgar_lixeira(db)
    itens = db.query(LixeiraDB).filter(LixeiraDB.tipo == tipo, LixeiraDB.dono_id == current_user.id) \
        .order_by(LixeiraDB.excluido_em.desc()).all()
    return [
        {"id": i.id, "alvo_id": i.alvo_id, "titulo": i.titulo, "excluido_em": i.excluido_em,
         "expira_em": expira_em(i.excluido_em).isoformat(), "excluido_por": i.excluido_por}
        for i in itens
    ]


@router.post("/lixeira/{item_id}/recuperar")
def recuperar_da_minha_lixeira(item_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    item = db.query(LixeiraDB).filter(LixeiraDB.id == item_id).first()
    if not item or item.tipo not in ("nota", "desenho") or item.dono_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item não encontrado na sua lixeira")
    # Passa pelo mesmo caminho da auditoria, pra que o registro da exclusão
    # fique marcado como desfeito e a recuperação também apareça no log.
    log = db.query(AuditLogDB).filter(AuditLogDB.lixeira_id == item.id).first()
    if not log:
        raise HTTPException(status_code=409, detail="Não achei o registro desta exclusão")
    try:
        mensagem = desfazer(db, log, current_user)
    except Conflito as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    db.commit()
    return {"ok": True, "mensagem": mensagem}
