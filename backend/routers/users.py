import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import RoleDB, UserDB, UserRoleDB
from rbac import get_user_permissions, require_permission
from schemas import PasswordUpdate, UserCreate
from security import get_current_user, get_password_hash

router = APIRouter()


@router.get("/users")
def get_users(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    all_roles = {r.id: r for r in db.query(RoleDB).all()}
    roles_by_user = {}
    for ur in db.query(UserRoleDB).all():
        roles_by_user.setdefault(ur.user_id, []).append(ur.role_id)

    result = []
    for u in db.query(UserDB).all():
        roles = [
            {"id": rid, "nome": all_roles[rid].nome, "cor": all_roles[rid].cor, "protegido": all_roles[rid].protegido}
            for rid in roles_by_user.get(u.id, []) if rid in all_roles
        ]
        result.append({
            "id": u.id, "nome": u.nome, "role": u.role,
            "senha_temporaria": u.senha_temporaria, "roles": roles,
        })
    return result


@router.post("/users")
def create_user(req: UserCreate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_usuarios"))):
    if db.query(UserDB).filter(UserDB.nome == req.nome).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    hashed_pw = get_password_hash(req.senha)
    novo = UserDB(id=str(uuid.uuid4()), nome=req.nome, senha=hashed_pw, role="user", senha_temporaria=True)
    db.add(novo)
    # Every new user starts with just the baseline "Usuário" cargo — additional
    # cargos are granted afterward through the Cargos screen, not at creation time.
    usuario_role = db.query(RoleDB).filter(RoleDB.nome == "Usuário").first()
    if usuario_role:
        db.add(UserRoleDB(user_id=novo.id, role_id=usuario_role.id))
    db.commit()
    return {"msg": "criado"}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("excluir_usuarios"))):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user and user.nome != "admin":
        db.delete(user)
        db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).delete()
        db.commit()
    return {"msg": "deletado"}


@router.put("/users/{user_id}/password")
def update_password(user_id: str, req: PasswordUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    if current_user.id != user_id and "trocar_senha_outros" not in get_user_permissions(db, current_user.id):
        raise HTTPException(status_code=403, detail="Sem permissão para alterar senha de outro usuário")
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.senha = get_password_hash(req.nova_senha)
    user.senha_temporaria = False
    db.commit()
    return {"msg": "senha atualizada"}
