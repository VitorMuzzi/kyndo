import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from audit import SIMPLE_CARD_FIELDS_MAP, _mk_log
from database import get_db
from models import CardDB, CardSeenDB, SuggestionDB, UserDB
from rbac import get_visible_column_ids, require_permission
from schemas import SuggestionCreate, SuggestionDecision
from security import get_current_user

router = APIRouter()

# Explicit whitelist of fields a suggestion may target — deliberately excludes
# "status" (moving a card between columns skips the frontend's auto-status
# logic tied to checklist completion) even though it exists in
# SIMPLE_CARD_FIELDS_MAP (which is only a campo->acao lookup, not a permission list).
ALLOWED_SUGGESTION_FIELDS = ("titulo", "descricao", "prioridade", "prazo", "github_url")
PRIORIDADES_VALIDAS = ("Baixa", "Normal", "Alta", "Urgente")


def _validate_campo_alvo(campo_alvo, valor_proposto):
    if campo_alvo is None:
        return
    if not valor_proposto:
        raise HTTPException(status_code=400, detail="valor_proposto é obrigatório quando campo_alvo é informado")
    if campo_alvo.startswith("etapa:"):
        return
    if campo_alvo not in ALLOWED_SUGGESTION_FIELDS:
        raise HTTPException(status_code=400, detail=f"campo_alvo inválido: {campo_alvo}")
    if campo_alvo == "prioridade" and valor_proposto not in PRIORIDADES_VALIDAS:
        raise HTTPException(status_code=400, detail="valor_proposto inválido para prioridade")


def _assert_card_visible(db, current_user, db_card):
    """Mirrors the same guard in routers/cards.py — a card whose column is
    outside the caller's visible set doesn't exist for them."""
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None and db_card.status not in visible:
        raise HTTPException(status_code=404, detail="Card não encontrado")


def _serialize(s: SuggestionDB):
    return {
        "id": s.id, "card_id": s.card_id, "autor": s.autor, "texto": s.texto,
        "campo_alvo": s.campo_alvo, "valor_proposto": s.valor_proposto, "status": s.status,
        "data": s.data, "decidido_por": s.decidido_por, "decidido_em": s.decidido_em,
    }


def _bump_card(db, db_card, card_id, current_user, now_iso):
    db_card.alteracoes = (db_card.alteracoes or 0) + 1
    db_card.updated_em = now_iso
    seen_row = db.query(CardSeenDB).filter(CardSeenDB.card_id == card_id, CardSeenDB.user_id == current_user.id).first()
    if seen_row:
        seen_row.visto_em = now_iso
        seen_row.visto_versao = db_card.alteracoes
    else:
        db.add(CardSeenDB(card_id=card_id, user_id=current_user.id, visto_em=now_iso, visto_versao=db_card.alteracoes))


@router.get("/cards/{card_id}/suggestions")
def list_suggestions(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)
    rows = db.query(SuggestionDB).filter(SuggestionDB.card_id == card_id).order_by(SuggestionDB.data.asc()).all()
    return [_serialize(s) for s in rows]


@router.post("/cards/{card_id}/suggestions")
def create_suggestion(card_id: str, body: SuggestionCreate, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)
    _validate_campo_alvo(body.campo_alvo, body.valor_proposto)

    now_iso = datetime.now().isoformat()
    nova = SuggestionDB(
        id=f"sug-{uuid.uuid4().hex[:10]}", card_id=card_id, autor=current_user.nome,
        texto=body.texto, campo_alvo=body.campo_alvo, valor_proposto=body.valor_proposto,
        status="pendente", data=now_iso,
    )
    db.add(nova)
    _bump_card(db, db_card, card_id, current_user, now_iso)
    _mk_log(db, card_id, db_card.titulo, current_user.nome, "sugestao_criada", detalhe=body.texto[:200])
    db.commit()
    db.refresh(nova)
    return _serialize(nova)


def _apply_suggestion(db, db_card, campo_alvo, valor_proposto, usuario, autor_sugestao):
    """Applies an accepted suggestion's proposed value to the card. Returns
    True if the card actually changed (drives the home-screen badge)."""
    detalhe = f"aceitou sugestão de {autor_sugestao}"

    if campo_alvo in SIMPLE_CARD_FIELDS_MAP:
        old = getattr(db_card, campo_alvo) or ""
        novo = valor_proposto or ""
        if old == novo:
            return False
        setattr(db_card, campo_alvo, valor_proposto)
        _mk_log(db, db_card.id, db_card.titulo, usuario, SIMPLE_CARD_FIELDS_MAP[campo_alvo], valor_antigo=old, valor_novo=novo, detalhe=detalhe)
        return True

    if campo_alvo.startswith("etapa:"):
        item_id = campo_alvo.split(":", 1)[1]
        checklist = db_card.checklist or []
        alvo = next((i for i in checklist if i.get("id") == item_id), None)
        if alvo is None:
            # The etapa was deleted between the suggestion being made and decided —
            # log that nothing was applied rather than pretending it was.
            _mk_log(db, db_card.id, db_card.titulo, usuario, "sugestao_aceita_sem_aplicar", detalhe=f"etapa não encontrada — {detalhe}")
            return False
        if (alvo.get("texto") or "") == (valor_proposto or ""):
            return False
        nova_checklist = []
        for item in checklist:
            item = dict(item)
            if item.get("id") == item_id:
                _mk_log(db, db_card.id, db_card.titulo, usuario, "etapa_editada", detalhe=item.get("texto"), valor_antigo=item.get("texto"), valor_novo=valor_proposto)
                item["texto"] = valor_proposto
            nova_checklist.append(item)
        db_card.checklist = nova_checklist  # reassign whole list — JSON column isn't Mutable-tracked
        return True

    return False


@router.patch("/cards/{card_id}/suggestions/{suggestion_id}")
def decide_suggestion(card_id: str, suggestion_id: str, body: SuggestionDecision, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("decidir_sugestoes"))):
    if body.status not in ("aceita", "rejeitada"):
        raise HTTPException(status_code=400, detail="status inválido")
    sugestao = db.query(SuggestionDB).filter(SuggestionDB.id == suggestion_id, SuggestionDB.card_id == card_id).first()
    if not sugestao:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    if sugestao.status != "pendente":
        raise HTTPException(status_code=409, detail="Sugestão já foi decidida")
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)

    now_iso = datetime.now().isoformat()
    meaningful = False
    if body.status == "aceita" and sugestao.campo_alvo:
        meaningful = _apply_suggestion(db, db_card, sugestao.campo_alvo, sugestao.valor_proposto, current_user.nome, sugestao.autor)

    if meaningful:
        _bump_card(db, db_card, card_id, current_user, now_iso)

    sugestao.status = body.status
    sugestao.decidido_por = current_user.nome
    sugestao.decidido_em = now_iso
    _mk_log(db, card_id, db_card.titulo, current_user.nome, f"sugestao_{body.status}", detalhe=sugestao.texto[:200])
    db.commit()
    return {"ok": True}
