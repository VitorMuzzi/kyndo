from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AuditLogDB, CardDB, ColumnDB, SuggestionDB, UserDB
from rbac import get_visible_column_ids
from security import get_current_user

router = APIRouter()


def _tempo_medio_conclusao_dias(db, card_ids_concluidos, concluido_ids):
    """Average days from a card's creation to the most recent time it moved
    into a 'concluído' column, over cards currently sitting in one. Reads the
    audit log server-side only — the raw entries never leave this function,
    just the aggregate number, so this doesn't require ver_log_auditoria."""
    if not card_ids_concluidos:
        return None
    logs = db.query(AuditLogDB).filter(
        AuditLogDB.card_id.in_(card_ids_concluidos),
        AuditLogDB.acao.in_(["card_criado", "status_alterado"]),
    ).order_by(AuditLogDB.data.asc()).all()

    criado_em, concluido_em = {}, {}
    for log in logs:
        if log.acao == "card_criado":
            criado_em.setdefault(log.card_id, log.data)
        elif log.acao == "status_alterado" and log.valor_novo in concluido_ids:
            concluido_em[log.card_id] = log.data  # keep overwriting — last move into "concluído" wins

    dias_list = []
    for card_id, inicio in criado_em.items():
        fim = concluido_em.get(card_id)
        if not fim:
            continue
        try:
            dias = (datetime.fromisoformat(fim) - datetime.fromisoformat(inicio)).total_seconds() / 86400
        except ValueError:
            continue
        if dias >= 0:
            dias_list.append(dias)

    return round(sum(dias_list) / len(dias_list), 1) if dias_list else None


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    visible = get_visible_column_ids(db, current_user.id)
    cols = db.query(ColumnDB).filter(ColumnDB.arquivado == False).order_by(ColumnDB.ordem).all()  # noqa: E712
    if visible is not None:
        cols = [c for c in cols if c.id in visible]
    col_ids = {c.id for c in cols}
    concluido_ids = {c.id for c in cols if c.auto_concluido}

    cards = db.query(CardDB).filter(CardDB.status.in_(col_ids)).all() if col_ids else []
    hoje = datetime.now().date()

    cards_por_coluna = [
        {"coluna_id": c.id, "titulo": c.titulo, "cor": c.cor, "total": sum(1 for card in cards if card.status == c.id)}
        for c in cols
    ]

    cards_por_prioridade = defaultdict(int)
    for card in cards:
        cards_por_prioridade[card.prioridade or "Normal"] += 1

    atrasados = []
    for card in cards:
        if not card.prazo or card.status in concluido_ids:
            continue
        try:
            prazo_date = datetime.strptime(card.prazo, "%Y-%m-%d").date()
        except ValueError:
            continue
        if prazo_date < hoje:
            atrasados.append({
                "id": card.id, "titulo": card.titulo, "prazo": card.prazo,
                "responsaveis": card.responsaveis or ([card.autor] if card.autor else []),
            })
    atrasados.sort(key=lambda a: a["prazo"])
    atrasado_ids = {a["id"] for a in atrasados}

    por_responsavel = defaultdict(lambda: {"total": 0, "atrasados": 0})
    for card in cards:
        for nome in (card.responsaveis or ([card.autor] if card.autor else [])):
            nome = (nome or "").strip()  # tolerate stray whitespace in older data so it doesn't split one person into two rows
            if not nome:
                continue
            por_responsavel[nome]["total"] += 1
            if card.id in atrasado_ids:
                por_responsavel[nome]["atrasados"] += 1

    sugestoes = (
        db.query(SuggestionDB).join(CardDB, SuggestionDB.card_id == CardDB.id)
        .filter(CardDB.status.in_(col_ids)).all()
        if col_ids else []
    )
    sug_status = {"pendente": 0, "aceita": 0, "rejeitada": 0}
    por_decisor = defaultdict(lambda: {"aceitas": 0, "recusadas": 0})
    for s in sugestoes:
        sug_status[s.status] = sug_status.get(s.status, 0) + 1
        if s.status == "aceita" and s.decidido_por:
            por_decisor[s.decidido_por]["aceitas"] += 1
        elif s.status == "rejeitada" and s.decidido_por:
            por_decisor[s.decidido_por]["recusadas"] += 1

    return {
        "total_cards": len(cards),
        "cards_por_coluna": cards_por_coluna,
        "cards_por_prioridade": dict(cards_por_prioridade),
        "cards_atrasados": atrasados,
        "cards_por_responsavel": sorted(
            ({"nome": k, **v} for k, v in por_responsavel.items()), key=lambda r: -r["total"]
        ),
        "tempo_medio_conclusao_dias": _tempo_medio_conclusao_dias(
            db, [card.id for card in cards if card.status in concluido_ids], concluido_ids
        ),
        "sugestoes": sug_status,
        "sugestoes_por_decisor": [{"usuario": k, **v} for k, v in por_decisor.items()],
    }
