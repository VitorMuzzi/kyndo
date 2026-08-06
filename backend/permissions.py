from fastapi import HTTPException

from models import UserDB


def compute_permission(item, current_user: UserDB, cards_by_id: dict):
    """Owner > explicit share > public-via-linked-card's responsáveis > no access."""
    if item.user_id == current_user.id:
        return 'owner'
    for share in (item.compartilhado_com or []):
        if share.get('user_id') == current_user.id:
            return share.get('nivel')
    if item.publico and item.card_id:
        card = cards_by_id.get(item.card_id)
        if card and current_user.nome in (card.responsaveis or []):
            return 'editar'
    return None


def check_share_fields_change(payload, db_item, perm: str):
    if perm == 'owner':
        return
    if perm != 'editar':
        raise HTTPException(status_code=403, detail="Você só tem permissão de visualização neste item")
    novo_compartilhado = [s.model_dump() for s in payload.compartilhado_com]
    if (payload.card_id != db_item.card_id or payload.publico != db_item.publico or
            novo_compartilhado != (db_item.compartilhado_com or [])):
        raise HTTPException(status_code=403, detail="Apenas o dono pode alterar compartilhamento, público ou tarefa vinculada")
