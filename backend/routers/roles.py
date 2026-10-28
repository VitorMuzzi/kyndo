import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from audit import _mk_log
from database import get_db
from lixeira import excluir_cargo
from models import RoleDB, UserDB, UserRoleDB
from rbac import PERMISSIONS, require_permission
from schemas import RoleCreate, RoleUpdate, UserRolesUpdate
from security import get_current_user

router = APIRouter()


CAMPOS_CARGO = ("nome", "cor", "permissoes", "colunas_visiveis")


def cargo_de(r: RoleDB):
    return {c: getattr(r, c) for c in CAMPOS_CARGO}


def validar_troca_de_cargos(db, actor, user_id, novos_ids):
    """Regras do Superadmin: só quem já é concede ou revoga, e o último nunca
    sai. Usada aqui e ao desfazer uma troca de cargos pela auditoria."""
    superadmin_role = db.query(RoleDB).filter(RoleDB.protegido == True).first()  # noqa: E712
    if not superadmin_role:
        return
    current_role_ids = {r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all()}
    had_super = superadmin_role.id in current_role_ids
    will_have_super = superadmin_role.id in novos_ids

    if had_super != will_have_super:
        actor_role_ids = {r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == actor.id).all()}
        if superadmin_role.id not in actor_role_ids:
            raise HTTPException(status_code=400, detail="Só quem já é Superadmin pode conceder ou revogar esse cargo")

    if had_super and not will_have_super:
        holders = db.query(UserRoleDB).filter(UserRoleDB.role_id == superadmin_role.id).count()
        if holders <= 1:
            raise HTTPException(status_code=400, detail="Não é possível remover o único Superadmin do sistema")


def _serialize_role(r: RoleDB):
    return {
        "id": r.id, "nome": r.nome, "cor": r.cor, "protegido": r.protegido,
        "permissoes": r.permissoes or {}, "ordem": r.ordem,
        "colunas_visiveis": r.colunas_visiveis,
    }


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return [_serialize_role(r) for r in db.query(RoleDB).order_by(RoleDB.ordem).all()]


@router.get("/permissions")
def list_permissions(current_user: UserDB = Depends(get_current_user)):
    return [{"key": k, "label": v} for k, v in PERMISSIONS.items()]


@router.post("/roles")
def create_role(body: RoleCreate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    novo = RoleDB(
        id=f"role-{uuid.uuid4().hex[:8]}", nome=body.nome, cor=body.cor,
        permissoes=body.permissoes, protegido=False, ordem=db.query(RoleDB).count(),
        colunas_visiveis=(body.colunas_visiveis if body.colunas_restritas else None),
    )
    db.add(novo)
    _mk_log(db, None, novo.nome, current_user.nome, "cargo_criado", alvo_tipo="cargo", alvo_id=novo.id,
            reversao={"role_id": novo.id})
    db.commit()
    db.refresh(novo)
    return _serialize_role(novo)


@router.put("/roles/{role_id}")
def update_role(role_id: str, body: RoleUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    role = db.query(RoleDB).filter(RoleDB.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    if role.protegido:
        raise HTTPException(status_code=400, detail="Este cargo é protegido e não pode ser editado")
    antes = cargo_de(role)
    if body.nome is not None:
        role.nome = body.nome
    if body.cor is not None:
        role.cor = body.cor
    if body.permissoes is not None:
        role.permissoes = body.permissoes
    if body.colunas_restritas is True:
        role.colunas_visiveis = body.colunas_visiveis or []
    elif body.colunas_restritas is False:
        role.colunas_visiveis = None
    depois = cargo_de(role)
    if depois != antes:
        _mk_log(db, None, role.nome, current_user.nome, "cargo_alterado", alvo_tipo="cargo", alvo_id=role.id,
                reversao={"role_id": role.id, "antes": antes, "depois": depois})
    db.commit()
    return _serialize_role(role)


@router.delete("/roles/{role_id}")
def delete_role(role_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    role = db.query(RoleDB).filter(RoleDB.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    if role.protegido:
        raise HTTPException(status_code=400, detail="Este cargo é protegido e não pode ser excluído")
    lixeira_id = excluir_cargo(db, role, current_user.nome)
    _mk_log(db, None, role.nome, current_user.nome, "cargo_excluido", alvo_tipo="cargo", alvo_id=role.id,
            lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})
    db.commit()
    return {"ok": True}


@router.put("/users/{user_id}/roles")
def set_user_roles(user_id: str, body: UserRolesUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    new_role_ids = set(body.role_ids)
    validar_troca_de_cargos(db, current_user, user_id, new_role_ids)

    antes = sorted(r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all())
    db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).delete()
    for role_id in new_role_ids:
        db.add(UserRoleDB(user_id=user_id, role_id=role_id))
    if sorted(new_role_ids) != antes:
        nomes = {r.id: r.nome for r in db.query(RoleDB).all()}
        _mk_log(db, None, user.nome, current_user.nome, "cargos_do_usuario_alterados", alvo_tipo="usuario", alvo_id=user.id,
                valor_antigo=", ".join(nomes.get(i, i) for i in antes) or None,
                valor_novo=", ".join(nomes.get(i, i) for i in sorted(new_role_ids)) or None,
                reversao={"user_id": user.id, "antes": antes, "depois": sorted(new_role_ids)})
    db.commit()
    return {"ok": True}
