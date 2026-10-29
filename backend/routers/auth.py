from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import PedidoSenhaDB, UserDB
from rbac import get_user_permissions
from routers.users import pedidos_que_posso_atender, registrar_pedido_senha
from schemas import EsqueciSenha, LoginRequest
from security import check_rate_limit, create_access_token, get_current_user, verify_password

router = APIRouter()


@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    user = db.query(UserDB).filter(UserDB.nome == req.nome).first()
    if not user or not verify_password(req.senha, user.senha):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    # Lembrou a senha: o pedido de nova senha, se havia, perdeu o sentido.
    if db.query(PedidoSenhaDB).filter(PedidoSenhaDB.user_id == user.id).delete():
        db.commit()

    return {
        "id": user.id,
        "nome": user.nome,
        "role": user.role,
        "permissions": sorted(get_user_permissions(db, user.id)),
        "senha_temporaria": user.senha_temporaria,
        "token": create_access_token(user),
    }


@router.get("/me/permissions")
def minhas_permissoes(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """O login entrega as permissões uma vez; a tela consulta isto na
    sincronização pra que um cargo dado ou tirado valha sem sair e entrar."""
    return {
        "permissions": sorted(get_user_permissions(db, current_user.id)),
        # Pode ter sido renomeado por outra pessoa enquanto estava logado.
        "nome": current_user.nome,
        "pedidos_senha": len(pedidos_que_posso_atender(db, current_user)),
    }


@router.post("/esqueci-senha")
def esqueci_senha(req: EsqueciSenha, request: Request, db: Session = Depends(get_db)):
    """Sem e-mail no sistema: registra o pedido pra quem pode trocar senhas.
    A resposta é a mesma exista ou não o usuário, pra não servir de teste de
    quais nomes existem."""
    check_rate_limit(request.client.host if request.client else "unknown")
    user = db.query(UserDB).filter(UserDB.nome == (req.nome or "").strip()).first()
    if user:
        registrar_pedido_senha(db, user)
        db.commit()
    return {"msg": "Pedido registrado. Fale com um administrador para receber uma senha temporária."}
