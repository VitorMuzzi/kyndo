"""E-mail do usuário, preferências de aviso e configuração dos e-mails automáticos."""
import re
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

import email_envio
import notificacoes
from audit import _mk_log
from database import get_db
from models import TokenSenhaDB, UserDB
from rbac import get_user_permissions, is_superadmin, require_permission
from security import get_current_user, verify_password

router = APIRouter()

_FORMATO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailUpdate(BaseModel):
    email: Optional[str] = None  # vazio/nulo = tirar o e-mail
    senha_atual: Optional[str] = None  # obrigatória ao trocar o próprio


class ModosUpdate(BaseModel):
    modos: Dict[str, str]


def validar_email(db, email, user_id=None):
    """E-mail normalizado (minúsculo, sem espaços) ou None. Único entre os
    usuários: dois com o mesmo e-mail deixariam o "esqueci a senha" ambíguo."""
    email = (email or "").strip().lower()
    if not email:
        return None
    if len(email) > 254 or not _FORMATO_EMAIL.match(email):
        raise HTTPException(status_code=400, detail="E-mail inválido.")
    outro = db.query(UserDB).filter(func.lower(UserDB.email) == email).first()
    if outro and outro.id != user_id:
        raise HTTPException(status_code=400, detail="Esse e-mail já está no cadastro de outro usuário.")
    return email


def trocar_email(db, user, novo, ator, detalhe=None):
    """Grava, invalida links de redefinição pendentes (iam pro e-mail antigo)
    e registra na auditoria. Não faz commit nem manda os avisos."""
    antigo = user.email
    user.email = novo
    db.query(TokenSenhaDB).filter(TokenSenhaDB.user_id == user.id).delete()
    _mk_log(db, None, user.nome, ator.nome, "email_alterado", alvo_tipo="usuario", alvo_id=user.id,
            valor_antigo=antigo, valor_novo=novo, detalhe=detalhe,
            reversao={"user_id": user.id, "antes": antigo, "depois": novo})
    return antigo


# ------------------------------------------------------------- minha conta

@router.get("/me/conta")
def minha_conta(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return {
        "nome": current_user.nome,
        "email": current_user.email,
        "email_ativo": email_envio.configurado(),
        "entrega": notificacoes.entrega(current_user),
        "hora_resumo_avisos": notificacoes.HORA_DO_RESUMO_DE_AVISOS,
        "preferencias": notificacoes.preferencias(db, current_user),
    }


class PreferenciasUpdate(BaseModel):
    avisos: Dict[str, str] = {}  # tipo -> alcance (nenhum/meus/seguidos/todos)
    entrega: Optional[str] = None  # imediato | resumo


@router.put("/me/preferencias")
def minhas_preferencias(body: PreferenciasUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    notificacoes.gravar_preferencias(db, current_user, body.avisos, body.entrega)
    db.commit()
    return {"entrega": notificacoes.entrega(current_user), "preferencias": notificacoes.preferencias(db, current_user)}


@router.put("/users/{user_id}/email")
def alterar_email(user_id: str, body: EmailUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == current_user.id:
        # Com o e-mail dá pra redefinir a senha: uma sessão esquecida aberta
        # não pode bastar pra tomar a conta.
        if not body.senha_atual or not verify_password(body.senha_atual, user.senha):
            raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    else:
        # Pôr o próprio e-mail na conta de outra pessoa e pedir "esqueci a
        # senha" é o mesmo que trocar a senha dela — exige a mesma permissão.
        if "trocar_senha_outros" not in get_user_permissions(db, current_user.id):
            raise HTTPException(status_code=403, detail="Sem permissão para alterar o e-mail de outro usuário")
        if is_superadmin(db, user) and not is_superadmin(db, current_user):
            raise HTTPException(status_code=403, detail="Só um Superadmin pode alterar o e-mail de outro Superadmin")
    novo = validar_email(db, body.email, user.id)
    if novo == user.email:
        return {"email": novo}
    antigo = trocar_email(db, user, novo, current_user)
    db.commit()
    notificacoes.avisar_email_alterado(user, antigo, novo)
    return {"email": novo}


# ------------------------------------------------------- configuração geral

def _visao_config(db):
    atuais = notificacoes.modos(db)
    return {
        "configurado": email_envio.configurado(),
        "remetente": email_envio.remetente(),
        "url": email_envio.url_kyndo(),
        "hora_resumo": notificacoes.HORA_DO_RESUMO,
        "hora_resumo_avisos": notificacoes.HORA_DO_RESUMO_DE_AVISOS,
        "tipos": [{"tipo": t, "rotulo": info[0], "grupo": info[1], "modo": atuais[t]} for t, info in notificacoes.TIPOS.items()],
    }


@router.get("/config/emails")
def config_emails(db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("configurar_emails"))):
    return _visao_config(db)


@router.put("/config/emails")
def alterar_config_emails(body: ModosUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("configurar_emails"))):
    antes = notificacoes.modos(db)
    depois = dict(antes)
    for tipo, modo in body.modos.items():
        if tipo not in notificacoes.TIPOS or modo not in notificacoes.MODOS:
            raise HTTPException(status_code=400, detail="Tipo de aviso ou modo inválido.")
        depois[tipo] = modo
    if depois != antes:
        notificacoes.gravar_modos(db, depois)
        mudou = [f'{notificacoes.TIPOS[t][0]}: {depois[t]}' for t in notificacoes.TIPOS if antes[t] != depois[t]]
        _mk_log(db, None, "E-mails automáticos", current_user.nome, "config_emails_alterada",
                alvo_tipo="config", alvo_id=notificacoes.CHAVE_MODOS, detalhe="; ".join(mudou),
                reversao={"antes": antes, "depois": depois})
        db.commit()
    return _visao_config(db)


@router.post("/config/emails/teste")
def testar_email(db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("configurar_emails"))):
    if not current_user.email:
        raise HTTPException(status_code=400, detail="Cadastre o seu e-mail em Minha conta para receber o teste.")
    erro = email_envio.enviar_agora(
        current_user.email, "Teste de e-mail do Kyndo",
        [f"Olá, {current_user.nome}.", "Se você está lendo isto, o envio de e-mails do Kyndo está funcionando."],
        botao=("Abrir o Kyndo", email_envio.link("/")),
    )
    if erro:
        raise HTTPException(status_code=400, detail=erro)
    return {"msg": f"E-mail de teste enviado para {current_user.email}."}
