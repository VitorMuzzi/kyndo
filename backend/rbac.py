from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import RoleDB, UserRoleDB
from security import get_current_user

PERMISSIONS = {
    "gerenciar_usuarios": "Criar e editar usuários",
    "excluir_usuarios": "Excluir usuários",
    "trocar_senha_outros": "Trocar senha de outros usuários",
    "gerenciar_cargos": "Criar, editar e atribuir cargos",
    "ver_log_auditoria": "Ver log de auditoria",
    "gerenciar_colunas": "Criar, editar, arquivar e reordenar colunas",
    "reordenar_cards": "Mover/reordenar cards (drag-and-drop)",
    "criar_card_coluna_privada": "Criar card em qualquer coluna",
    "editar_card": "Editar título/descrição de qualquer card",
    "excluir_card": "Excluir qualquer card",
    "editar_prioridade": "Editar prioridade de qualquer card",
    "editar_prazo": "Editar prazo de qualquer card",
    "gerenciar_etapas": "Criar/editar/excluir etapas e sub-etapas",
    "concluir_etapas": "Marcar etapas/sub-etapas como concluídas",
    "gerenciar_responsaveis": "Gerenciar responsáveis de um card",
    "decidir_sugestoes": "Aceitar/rejeitar sugestões",
}


def get_user_permissions(db: Session, user_id: str) -> set:
    role_ids = [r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all()]
    if not role_ids:
        return set()
    roles = db.query(RoleDB).filter(RoleDB.id.in_(role_ids)).all()
    perms = set()
    for r in roles:
        perms |= {k for k, v in (r.permissoes or {}).items() if v}
    return perms


def require_permission(key: str):
    def dependency(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
        if key not in get_user_permissions(db, current_user.id):
            raise HTTPException(status_code=403, detail=f"Sem permissão: {PERMISSIONS.get(key, key)}")
        return current_user
    return dependency


def get_visible_column_ids(db: Session, user_id: str):
    """None = no restriction (sees every column/card). A set = restricted to
    exactly those column ids. Anyone with gerenciar_colunas always sees
    everything — reordering/editing the board structure requires seeing the
    whole board, otherwise the frontend's sequential `ordem` recalculation
    (which only covers the columns it received) corrupts column ordering for
    everyone, including unrestricted users."""
    if "gerenciar_colunas" in get_user_permissions(db, user_id):
        return None
    role_ids = [r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all()]
    if not role_ids:
        return None
    roles = db.query(RoleDB).filter(RoleDB.id.in_(role_ids)).all()
    visible = set()
    for r in roles:
        if r.colunas_visiveis is None:
            return None  # any unrestricted role grants full visibility (same OR semantics as permissions)
        visible |= set(r.colunas_visiveis)
    return visible


def filter_checklist_for_permission(old_checklist, new_checklist, can_manage: bool, can_complete: bool):
    """Applies the caller's checklist permissions to an incoming payload:
    full access -> pass through untouched; complete-only -> keep the DB's
    structure/order but let concluido/concluidoPor flow through by id (per
    item and per sub-item); no access -> revert the whole checklist."""
    if can_manage:
        return new_checklist
    if not can_complete:
        return old_checklist

    new_by_id = {i.get("id"): i for i in (new_checklist or []) if isinstance(i, dict)}
    result = []
    for old_item in (old_checklist or []):
        item = dict(old_item)
        new_item = new_by_id.get(item.get("id"))
        if new_item:
            item["concluido"] = new_item.get("concluido", item.get("concluido"))
            item["concluidoPor"] = new_item.get("concluidoPor", item.get("concluidoPor"))
            new_subs_by_id = {s.get("id"): s for s in (new_item.get("subetapas") or []) if isinstance(s, dict)}
            merged_subs = []
            for old_sub in (item.get("subetapas") or []):
                sub = dict(old_sub)
                new_sub = new_subs_by_id.get(sub.get("id"))
                if new_sub:
                    sub["concluido"] = new_sub.get("concluido", sub.get("concluido"))
                    sub["concluidoPor"] = new_sub.get("concluidoPor", sub.get("concluidoPor"))
                merged_subs.append(sub)
            item["subetapas"] = merged_subs
        result.append(item)
    return result
