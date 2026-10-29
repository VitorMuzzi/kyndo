import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

import email_envio
import notificacoes
import relatorios_envio
from audit import _mk_log

from database import get_db
from models import PedidoSenhaDB, TokenSenhaDB, UserDB
from rbac import get_user_permissions
from routers.users import pedidos_que_posso_atender, registrar_pedido_senha
from schemas import EsqueciSenha, LoginRequest
from security import check_rate_limit, create_access_token, definir_senha, get_current_user, verify_password

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
        "relatorios_nao_lidos": relatorios_envio.nao_lidos(db, current_user),
    }


VALIDADE_LINK = timedelta(hours=1)
INTERVALO_ENTRE_LINKS = timedelta(minutes=2)


class RedefinirSenha(BaseModel):
    token: str
    nova_senha: str


def _hash_token(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


@router.post("/esqueci-senha")
def esqueci_senha(req: EsqueciSenha, request: Request, db: Session = Depends(get_db)):
    """Com e-mail cadastrado (e envio configurado), manda um link de
    redefinição; senão, registra o pedido pra quem pode trocar senhas.
    Aceita o usuário ou o e-mail. A resposta é sempre a mesma, pra não
    servir de teste de quais nomes ou e-mails existem."""
    check_rate_limit(request.client.host if request.client else "unknown")
    termo = (req.nome or "").strip()
    user = db.query(UserDB).filter(UserDB.nome == termo).first()
    if user is None and "@" in termo:
        user = db.query(UserDB).filter(func.lower(UserDB.email) == termo.lower()).first()
    if user:
        if user.email and email_envio.configurado() and email_envio.url_kyndo():
            agora = datetime.now()
            recente = db.query(TokenSenhaDB).filter(
                TokenSenhaDB.user_id == user.id,
                TokenSenhaDB.criado_em > (agora - INTERVALO_ENTRE_LINKS).isoformat()).first()
            # Vários cliques seguidos não viram vários e-mails.
            if not recente:
                token = secrets.token_urlsafe(32)
                db.add(TokenSenhaDB(id=_hash_token(token), user_id=user.id, criado_em=agora.isoformat(),
                                    expira_em=(agora + VALIDADE_LINK).isoformat()))
                db.commit()
                notificacoes.enviar_link_de_redefinicao(user, email_envio.link(f"/?redefinir={token}"))
        else:
            registrar_pedido_senha(db, user)
            db.commit()
    return {"msg": "Pronto. Se esse usuário tiver e-mail cadastrado, o link para criar uma nova senha chega em "
                   "alguns minutos (confira também o spam). Se não tiver, um administrador recebeu o pedido e vai "
                   "definir uma senha temporária para você."}


@router.post("/redefinir-senha")
def redefinir_senha(req: RedefinirSenha, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request.client.host if request.client else "unknown")
    registro = db.query(TokenSenhaDB).filter(TokenSenhaDB.id == _hash_token(req.token)).first()
    user = db.query(UserDB).filter(UserDB.id == registro.user_id).first() if registro else None
    if not registro or not user or registro.expira_em < datetime.now().isoformat():
        raise HTTPException(status_code=400, detail='Este link expirou ou já foi usado. Peça um novo em "Esqueci a senha".')
    if len(req.nova_senha or "") < 4:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 4 caracteres.")
    definir_senha(user, req.nova_senha)
    user.senha_temporaria = False
    db.query(TokenSenhaDB).filter(TokenSenhaDB.user_id == user.id).delete()
    db.query(PedidoSenhaDB).filter(PedidoSenhaDB.user_id == user.id).delete()
    _mk_log(db, None, user.nome, user.nome, "senha_redefinida_por_email", alvo_tipo="usuario", alvo_id=user.id)
    db.commit()
    notificacoes.avisar_senha_alterada(user)
    return {"msg": "Senha redefinida. Entre com a nova senha."}
