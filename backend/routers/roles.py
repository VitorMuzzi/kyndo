import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import RoleDB, UserDB, UserRoleDB
from rbac import PERMISSIONS, require_permission
from schemas import RoleCreate, RoleUpdate, UserRolesUpdate
from security import get_current_user

router = APIRouter()


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
    db.commit()
    return _serialize_role(role)


@router.delete("/roles/{role_id}")
def delete_role(role_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    role = db.query(RoleDB).filter(RoleDB.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    if role.protegido:
        raise HTTPException(status_code=400, detail="Este cargo é protegido e não pode ser excluído")
    db.delete(role)
    db.query(UserRoleDB).filter(UserRoleDB.role_id == role_id).delete()
    db.commit()
    return {"ok": True}


@router.put("/users/{user_id}/roles")
def set_user_roles(user_id: str, body: UserRolesUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    new_role_ids = set(body.role_ids)
    superadmin_role = db.query(RoleDB).filter(RoleDB.protegido == True).first()  # noqa: E712

    if superadmin_role:
        current_role_ids = {r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all()}
        had_super = superadmin_role.id in current_role_ids
        will_have_super = superadmin_role.id in new_role_ids

        if had_super != will_have_super:
            actor_role_ids = {r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == current_user.id).all()}
            if superadmin_role.id not in actor_role_ids:
                raise HTTPException(status_code=400, detail="Só quem já é Superadmin pode conceder ou revogar esse cargo")

        if had_super and not will_have_super:
            holders = db.query(UserRoleDB).filter(UserRoleDB.role_id == superadmin_role.id).count()
            if holders <= 1:
                raise HTTPException(status_code=400, detail="Não é possível remover o único Superadmin do sistema")

    db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).delete()
    for role_id in new_role_ids:
        db.add(UserRoleDB(user_id=user_id, role_id=role_id))
    db.commit()
    return {"ok": True}
