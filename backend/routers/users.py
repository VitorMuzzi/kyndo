import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from audit import _mk_log
from database import get_db
from lixeira import excluir_usuario
import notificacoes
from models import PedidoSenhaDB, RoleDB, TokenSenhaDB, UserDB, UserRoleDB
from rbac import get_user_permissions, is_superadmin, require_permission
from renomear import renomear_usuario, validar_nome
from schemas import PasswordUpdate, UserCreate, UserRename
from security import create_access_token, definir_senha, get_current_user, get_password_hash, verify_password

router = APIRouter()


@router.get("/users")
def get_users(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    all_roles = {r.id: r for r in db.query(RoleDB).all()}
    roles_by_user = {}
    for ur in db.query(UserRoleDB).all():
        roles_by_user.setdefault(ur.user_id, []).append(ur.role_id)

    # E-mail é dado pessoal: só aparece pra quem administra usuários.
    ve_email = bool({"gerenciar_usuarios", "trocar_senha_outros"} & get_user_permissions(db, current_user.id))
    result = []
    for u in db.query(UserDB).all():
        roles = [
            {"id": rid, "nome": all_roles[rid].nome, "cor": all_roles[rid].cor, "protegido": all_roles[rid].protegido}
            for rid in roles_by_user.get(u.id, []) if rid in all_roles
        ]
        result.append({
            "id": u.id, "nome": u.nome, "role": u.role,
            "senha_temporaria": u.senha_temporaria, "roles": roles,
            **({"email": u.email} if ve_email else {}),
        })
    return result


@router.post("/users")
def create_user(req: UserCreate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_usuarios"))):
    if db.query(UserDB).filter(UserDB.nome == req.nome).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    from routers.emails import validar_email
    email = validar_email(db, req.email)
    hashed_pw = get_password_hash(req.senha)
    novo = UserDB(id=str(uuid.uuid4()), nome=req.nome, senha=hashed_pw, role="user", senha_temporaria=True, email=email)
    db.add(novo)
    # Every new user starts with just the baseline "Usuário" cargo — additional
    # cargos are granted afterward through the Cargos screen, not at creation time.
    usuario_role = db.query(RoleDB).filter(RoleDB.nome == "Usuário").first()
    if usuario_role:
        db.add(UserRoleDB(user_id=novo.id, role_id=usuario_role.id))
    _mk_log(db, None, novo.nome, current_user.nome, "usuario_criado", alvo_tipo="usuario", alvo_id=novo.id,
            reversao={"user_id": novo.id, "senha_versao": 0})
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
        db.query(PedidoSenhaDB).filter(PedidoSenhaDB.user_id == user.id).delete()
        lixeira_id = excluir_usuario(db, user, current_user.nome)
        _mk_log(db, None, user.nome, current_user.nome, "usuario_excluido", alvo_tipo="usuario", alvo_id=user.id,
                lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})
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
    if len(req.nova_senha or "") < 4:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 4 caracteres.")
    # Sessão esquecida aberta ou token vazado não bastam pra tomar a conta:
    # trocar a própria senha pede a atual. A temporária do primeiro login
    # acabou de ser digitada, então dispensa.
    if propria and not user.senha_temporaria:
        if not req.senha_atual or not verify_password(req.senha_atual, user.senha):
            raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    definir_senha(user, req.nova_senha)
    # Senha definida por outra pessoa é conhecida por ela — o dono troca no próximo login.
    user.senha_temporaria = not propria
    db.query(PedidoSenhaDB).filter(PedidoSenhaDB.user_id == user.id).delete()
    db.query(TokenSenhaDB).filter(TokenSenhaDB.user_id == user.id).delete()
    if not propria:
        _mk_log(db, None, user.nome, current_user.nome, "senha_redefinida", alvo_tipo="usuario", alvo_id=user.id,
                detalhe="senha temporária definida por outra pessoa")
    db.commit()
    notificacoes.avisar_senha_alterada(user, por_outra_pessoa=not propria)
    resposta = {"msg": "senha atualizada"}
    if propria:
        # A troca invalidou o token desta sessão também; devolve um novo pra
        # quem acabou de trocar não ser jogado pra fora.
        resposta["token"] = create_access_token(user)
    return resposta


@router.put("/users/{user_id}")
def rename_user(user_id: str, body: UserRename, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_usuarios"))):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    # init_data procura a conta de recuperação pelo nome "admin": renomeada,
    # ela seria recriada com a senha padrão no próximo start.
    if user.nome == "admin":
        raise HTTPException(status_code=400, detail="A conta admin é a de recuperação do sistema e não pode ser renomeada.")
    if is_superadmin(db, user) and not is_superadmin(db, current_user):
        raise HTTPException(status_code=403, detail="Só um Superadmin pode renomear outro Superadmin")
    novo = validar_nome(db, body.nome, user.id)
    if novo == user.nome:
        return {"msg": "sem alteração", "nome": novo}
    antigo = renomear_usuario(db, user, novo)
    _mk_log(db, None, novo, current_user.nome, "usuario_renomeado", alvo_tipo="usuario", alvo_id=user.id,
            valor_antigo=antigo, valor_novo=novo, reversao={"user_id": user.id, "antes": antigo, "depois": novo})
    db.commit()
    return {"msg": "renomeado", "nome": novo}


# ------------------------------------------------------------ esqueci a senha

def pedidos_que_posso_atender(db, actor):
    """Pedidos de nova senha que `actor` consegue resolver: nenhum sem
    trocar_senha_outros, e os de Superadmin só pra outro Superadmin."""
    if "trocar_senha_outros" not in get_user_permissions(db, actor.id):
        return []
    sou_super = is_superadmin(db, actor)
    resultado = []
    for p in db.query(PedidoSenhaDB).order_by(PedidoSenhaDB.criado_em).all():
        user = db.query(UserDB).filter(UserDB.id == p.user_id).first()
        if user is None or user.id == actor.id or (is_superadmin(db, user) and not sou_super):
            continue
        resultado.append({"id": p.id, "user_id": user.id, "nome": user.nome, "criado_em": p.criado_em})
    return resultado


def registrar_pedido_senha(db, user):
    if not db.query(PedidoSenhaDB).filter(PedidoSenhaDB.user_id == user.id).first():
        db.add(PedidoSenhaDB(id=str(uuid.uuid4()), user_id=user.id, criado_em=datetime.now().isoformat()))


@router.get("/pedidos-senha")
def listar_pedidos_senha(db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("trocar_senha_outros"))):
    return pedidos_que_posso_atender(db, current_user)


@router.delete("/pedidos-senha/{pedido_id}")
def descartar_pedido_senha(pedido_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("trocar_senha_outros"))):
    if pedido_id not in {p["id"] for p in pedidos_que_posso_atender(db, current_user)}:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    db.query(PedidoSenhaDB).filter(PedidoSenhaDB.id == pedido_id).delete()
    db.commit()
    return {"msg": "descartado"}
