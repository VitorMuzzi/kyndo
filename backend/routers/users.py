import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import RoleDB, UserDB, UserRoleDB
from rbac import get_user_permissions, is_superadmin, require_permission
from schemas import PasswordUpdate, UserCreate
from security import create_access_token, definir_senha, get_current_user, get_password_hash

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
        # excluir_usuarios não pode virar atalho pra derrubar quem está acima:
        # só superadmin remove superadmin, e o último nunca sai.
        if is_superadmin(db, user):
            if not is_superadmin(db, current_user):
                raise HTTPException(status_code=403, detail="Só um Superadmin pode excluir outro Superadmin")
            if sum(1 for u in db.query(UserDB).all() if is_superadmin(db, u)) <= 1:
                raise HTTPException(status_code=400, detail="Não é possível excluir o único Superadmin do sistema")
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
    propria = current_user.id == user_id
    # Trocar a senha do superadmin e logar como ele seria uma escalada completa
    # pra quem só recebeu trocar_senha_outros.
    if not propria and is_superadmin(db, user) and not is_superadmin(db, current_user):
        raise HTTPException(status_code=403, detail="Só um Superadmin pode alterar a senha de outro Superadmin")
    definir_senha(user, req.nova_senha)
    # Senha definida por outra pessoa é conhecida por ela — o dono troca no próximo login.
    user.senha_temporaria = not propria
    db.commit()
    resposta = {"msg": "senha atualizada"}
    if propria:
        # A troca invalidou o token desta sessão também; devolve um novo pra
        # quem acabou de trocar não ser jogado pra fora.
        resposta["token"] = create_access_token(user)
    return resposta
