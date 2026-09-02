import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import CardDB, CardSeenDB, ColumnDB, ItemSeenDB, UserDB
from schemas import CardReorderItem, CardSchema
from security import get_current_user
from audit import _mk_log, log_card_created, log_card_deleted, process_card_update
from rbac import filter_checklist_for_permission, get_user_permissions, get_visible_column_ids, require_permission

router = APIRouter()


def _assert_card_visible(db, current_user, db_card):
    """A card whose column is outside the caller's visible set doesn't exist
    for them — 404, not 403, so a restricted cargo can't even probe for its
    existence."""
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None and db_card.status not in visible:
        raise HTTPException(status_code=404, detail="Card não encontrado")


def _norm(v):
    return v or ""


def _revert_unauthorized_fields(db, db_card, card, current_user):
    """Mutates `card` (the incoming payload) in place, reverting any field the
    current user isn't allowed to change back to the card's current DB value.
    Silent revert (not a 403) so a stale concurrent edit from someone else
    never blocks the fields this user genuinely has permission to change —
    see plan notes on why an all-or-nothing 403 would be a false positive."""
    perms = get_user_permissions(db, current_user.id)
    visible = get_visible_column_ids(db, current_user.id)
    col = db.query(ColumnDB).filter(ColumnDB.id == db_card.status).first()
    is_author = db_card.autor == current_user.nome

    if _norm(db_card.titulo) != _norm(card.titulo) or _norm(db_card.descricao) != _norm(card.descricao):
        allowed = "editar_card" in perms or (is_author and col is not None and col.publica)
        if not allowed:
            card.titulo = db_card.titulo
            card.descricao = db_card.descricao

    if _norm(db_card.prioridade) != _norm(card.prioridade) and "editar_prioridade" not in perms:
        card.prioridade = db_card.prioridade

    if _norm(db_card.prazo) != _norm(card.prazo) and "editar_prazo" not in perms:
        card.prazo = db_card.prazo

    moving_into_hidden_column = visible is not None and card.status not in visible
    if _norm(db_card.status) != _norm(card.status) and ("reordenar_cards" not in perms or moving_into_hidden_column):
        card.status = db_card.status

    if sorted(db_card.responsaveis or []) != sorted(card.responsaveis or []) and "gerenciar_responsaveis" not in perms:
        card.responsaveis = db_card.responsaveis

    card.checklist = filter_checklist_for_permission(
        db_card.checklist, card.checklist,
        can_manage="gerenciar_etapas" in perms, can_complete="concluir_etapas" in perms,
    )

    if (bool(db_card.recorrente) != card.recorrente or db_card.recorrencia_dias != card.recorrencia_dias) and "gerenciar_etapas" not in perms:
        card.recorrente = bool(db_card.recorrente)
        card.recorrencia_dias = db_card.recorrencia_dias


def _annotate_checklist(checklist, item_seen_map):
    annotated = []
    for item in checklist or []:
        item = dict(item)
        versao = item.get("notas_versao", 0) or 0
        visto = item_seen_map.get(item.get("id"), 0)
        item["notas_nao_vista"] = bool((item.get("notas") or "").strip()) and versao > visto
        annotated.append(item)
    return annotated


def _serialize_card(c: CardDB, visto_versao, item_seen_map):
    alteracoes_nao_vistas = max(0, (c.alteracoes or 0) - (visto_versao or 0))
    return {
        "id": c.id, "titulo": c.titulo, "descricao": c.descricao, "status": c.status,
        "prioridade": c.prioridade, "autor": c.autor, "prazo": c.prazo,
        "data_criacao": c.data_criacao, "checklist": _annotate_checklist(c.checklist, item_seen_map), "comentarios": c.comentarios,
        "responsaveis": c.responsaveis, "github_url": c.github_url, "ordem": c.ordem,
        "updated_em": c.updated_em,
        "alteracoes_nao_vistas": alteracoes_nao_vistas,
        "nao_visto": alteracoes_nao_vistas > 0,
        "recorrente": bool(c.recorrente), "recorrencia_dias": c.recorrencia_dias,
        "recorrencia_coluna_reset": c.recorrencia_coluna_reset, "recorrencia_proximo_reset": c.recorrencia_proximo_reset,
    }


def _reset_checklist_progress(checklist):
    reiniciado = []
    for item in checklist or []:
        item = dict(item)
        item["concluido"] = False
        item["concluidoPor"] = None
        item["subetapas"] = [{**s, "concluido": False, "concluidoPor": None} for s in (item.get("subetapas") or [])]
        reiniciado.append(item)
    return reiniciado


def _apply_due_recurrences(db):
    """Lazily reopens recurring cards whose period has elapsed — checked on
    every read instead of via a background scheduler, matching this app's
    no-cron-process architecture. Catches up (advances proximo_reset in a
    loop) if the server was down across more than one period, so a card
    never fires its reset more than once per call regardless of how long
    it's been."""
    now = datetime.now()
    now_iso = now.isoformat()
    due = db.query(CardDB).filter(
        CardDB.recorrente == True, CardDB.recorrencia_proximo_reset != None,  # noqa: E711,E712
        CardDB.recorrencia_proximo_reset <= now_iso,
    ).all()
    if not due:
        return
    for card in due:
        card.checklist = _reset_checklist_progress(card.checklist)
        dias = card.recorrencia_dias or 1
        if card.recorrencia_coluna_reset and db.query(ColumnDB).filter(ColumnDB.id == card.recorrencia_coluna_reset).first():
            card.status = card.recorrencia_coluna_reset
        proximo = datetime.fromisoformat(card.recorrencia_proximo_reset)
        while proximo <= now:
            proximo += timedelta(days=dias)
        card.recorrencia_proximo_reset = proximo.isoformat()
        card.alteracoes = (card.alteracoes or 0) + 1
        card.updated_em = now_iso
        _mk_log(db, card.id, card.titulo, "sistema", "tarefa_recorrente_reiniciada", detalhe=f"checklist reiniciado (recorrência de {dias} dia{'s' if dias != 1 else ''})")
    db.commit()


@router.get("/cards")
def get_cards(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    _apply_due_recurrences(db)
    all_cards = db.query(CardDB).all()
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None:
        all_cards = [c for c in all_cards if c.status in visible]
    seen_map = {s.card_id: s.visto_versao for s in db.query(CardSeenDB).filter(CardSeenDB.user_id == current_user.id).all()}
    item_seen_map = {}
    for r in db.query(ItemSeenDB).filter(ItemSeenDB.user_id == current_user.id).all():
        item_seen_map.setdefault(r.card_id, {})[r.item_id] = r.visto_versao
    return [_serialize_card(c, seen_map.get(c.id), item_seen_map.get(c.id, {})) for c in all_cards]


@router.post("/cards")
def create_card(card: CardSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None and card.status not in visible:
        raise HTTPException(status_code=404, detail="Coluna não encontrada")

    col = db.query(ColumnDB).filter(ColumnDB.id == card.status).first()
    perms = get_user_permissions(db, current_user.id)
    if not (col is not None and col.publica) and "criar_card_coluna_privada" not in perms:
        raise HTTPException(status_code=403, detail="Sem permissão para criar card nesta coluna")

    now = datetime.now()
    data_atual = now.strftime("%d/%m/%Y")
    now_iso = now.isoformat()
    max_ordem = db.query(CardDB).filter(CardDB.status == card.status).count()
    recorrente = bool(card.recorrente and card.recorrencia_dias)
    novo = CardDB(
        id=f"card-{uuid.uuid4().hex[:8]}",
        titulo=card.titulo,
        descricao=card.descricao,
        status=card.status,
        prioridade=card.prioridade,
        autor=card.autor,
        prazo=card.prazo,
        data_criacao=data_atual,
        checklist=card.checklist,
        comentarios=card.comentarios,
        responsaveis=card.responsaveis if card.responsaveis else [card.autor],
        github_url=card.github_url or None,
        ordem=max_ordem,
        updated_em=now_iso,
        recorrente=recorrente,
        recorrencia_dias=card.recorrencia_dias if recorrente else None,
        recorrencia_coluna_reset=card.status if recorrente else None,
        recorrencia_proximo_reset=(now + timedelta(days=card.recorrencia_dias)).isoformat() if recorrente else None,
    )
    db.add(novo)
    log_card_created(db, novo, current_user.nome)
    # Badge counts unseen EDITS (alteracoes - visto_versao); a new card has zero edits,
    # so nobody gets a badge yet. The creator's seen row anchors their baseline at 0.
    db.add(CardSeenDB(card_id=novo.id, user_id=current_user.id, visto_em=now_iso, visto_versao=0))
    db.commit()
    db.refresh(novo)
    return novo


@router.put("/cards/reorder")
def reorder_cards(reorders: List[CardReorderItem], db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("reordenar_cards"))):
    for r in reorders:
        card = db.query(CardDB).filter(CardDB.id == r.id).first()
        if card:
            card.ordem = r.ordem
    db.commit()
    return {"ok": True}


@router.put("/cards/{card_id}")
def update_card(card_id: str, card: CardSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if db_card:
        _assert_card_visible(db, current_user, db_card)
        # Revert any field the caller isn't allowed to change BEFORE the diff/log
        # runs, so an unauthorized (or just stale, from a concurrent edit) change
        # never gets logged or persisted — no 403 here, see rbac plan notes.
        _revert_unauthorized_fields(db, db_card, card, current_user)
        # Diff against the still-unmutated db_card, logging every atomic change
        # and deciding whether it's "meaningful" (etapa/subetapa deletions alone
        # are logged but don't count toward the home-screen badge).
        sanitized_checklist, meaningful = process_card_update(db, db_card, card, current_user.nome)
        db_card.titulo = card.titulo
        db_card.descricao = card.descricao
        db_card.status = card.status
        db_card.prioridade = card.prioridade
        db_card.prazo = card.prazo
        db_card.checklist = sanitized_checklist
        db_card.comentarios = card.comentarios
        db_card.responsaveis = card.responsaveis if card.responsaveis else [card.autor]
        db_card.github_url = card.github_url or None
        db_card.ordem = card.ordem
        now_iso = datetime.now().isoformat()

        recorrente_novo = bool(card.recorrente and card.recorrencia_dias)
        rearmar = recorrente_novo and (not db_card.recorrente or db_card.recorrencia_dias != card.recorrencia_dias)
        if rearmar:
            db_card.recorrencia_coluna_reset = db_card.status
            db_card.recorrencia_proximo_reset = (datetime.now() + timedelta(days=card.recorrencia_dias)).isoformat()
            _mk_log(db, card_id, db_card.titulo, current_user.nome, "recorrencia_configurada", detalhe=f"a cada {card.recorrencia_dias} dia(s), volta para {db_card.status}")
        elif not recorrente_novo and db_card.recorrente:
            db_card.recorrencia_coluna_reset = None
            db_card.recorrencia_proximo_reset = None
            _mk_log(db, card_id, db_card.titulo, current_user.nome, "recorrencia_desativada")
        db_card.recorrente = recorrente_novo
        db_card.recorrencia_dias = card.recorrencia_dias if recorrente_novo else None

        db_card.updated_em = now_iso
        if meaningful:
            db_card.alteracoes = (db_card.alteracoes or 0) + 1
        # The editor made this change themselves — it shouldn't show up as "unseen" for them.
        seen_row = db.query(CardSeenDB).filter(CardSeenDB.card_id == card_id, CardSeenDB.user_id == current_user.id).first()
        if seen_row:
            seen_row.visto_em = now_iso
            seen_row.visto_versao = db_card.alteracoes
        else:
            db.add(CardSeenDB(card_id=card_id, user_id=current_user.id, visto_em=now_iso, visto_versao=db_card.alteracoes))
        # The editor just reviewed every step's notes in the modal — anchor their
        # per-item baseline so they don't see a badge for their own edit.
        for item in sanitized_checklist:
            versao = item.get("notas_versao", 0) or 0
            item_row = db.query(ItemSeenDB).filter(
                ItemSeenDB.card_id == card_id, ItemSeenDB.item_id == item["id"], ItemSeenDB.user_id == current_user.id
            ).first()
            if item_row:
                item_row.visto_versao = versao
            else:
                db.add(ItemSeenDB(card_id=card_id, item_id=item["id"], user_id=current_user.id, visto_versao=versao))
        db.commit()
    return {"msg": "atualizado"}


@router.delete("/cards/{card_id}")
def delete_card(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if db_card:
        _assert_card_visible(db, current_user, db_card)
        perms = get_user_permissions(db, current_user.id)
        is_author = db_card.autor == current_user.nome
        if "excluir_card" not in perms and not (is_author and db_card.status == "col-1"):
            raise HTTPException(status_code=403, detail="Sem permissão para excluir este card")
        log_card_deleted(db, db_card, current_user.nome)
        db.delete(db_card)
        db.query(CardSeenDB).filter(CardSeenDB.card_id == card_id).delete()
        db.query(ItemSeenDB).filter(ItemSeenDB.card_id == card_id).delete()
        db.commit()
    return {"msg": "deletado"}


@router.post("/cards/{card_id}/seen")
def mark_card_seen(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)
    now_iso = datetime.now().isoformat()
    row = db.query(CardSeenDB).filter(CardSeenDB.card_id == card_id, CardSeenDB.user_id == current_user.id).first()
    if row:
        row.visto_em = now_iso
        row.visto_versao = db_card.alteracoes
    else:
        db.add(CardSeenDB(card_id=card_id, user_id=current_user.id, visto_em=now_iso, visto_versao=db_card.alteracoes))
    db.commit()
    return {"ok": True}


@router.post("/cards/{card_id}/items/{item_id}/seen")
def mark_item_seen(card_id: str, item_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)
    item = next((i for i in (db_card.checklist or []) if i.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Etapa não encontrada")
    versao = item.get("notas_versao", 0) or 0
    row = db.query(ItemSeenDB).filter(
        ItemSeenDB.card_id == card_id, ItemSeenDB.item_id == item_id, ItemSeenDB.user_id == current_user.id
    ).first()
    if row:
        row.visto_versao = versao
    else:
        db.add(ItemSeenDB(card_id=card_id, item_id=item_id, user_id=current_user.id, visto_versao=versao))
    db.commit()
    return {"ok": True}
