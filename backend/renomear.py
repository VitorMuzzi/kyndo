"""Renomear usuário.

O nome é a identidade gravada em todo canto: autor e responsáveis do card,
quem criou ou concluiu cada etapa, comentários, sugestões, anexos, tempo,
auditoria e lixeira. Trocar só o UserDB.nome faria a pessoa perder a autoria
do que já fez (e as permissões de autor), então a troca vale em tudo."""
from fastapi import HTTPException

from models import AttachmentDB, AuditLogDB, CardDB, LixeiraDB, SuggestionDB, TimeEntryDB, UserDB

# Chaves, em qualquer nível de um JSON gravado, cujo valor é nome de usuário
# (ou lista de nomes, no caso de responsaveis).
CHAVES_DE_NOME = {
    "autor", "criador", "concluidoPor", "usuario", "responsaveis",
    "enviado_por", "decidido_por", "excluido_por", "revertido_por",
}
TAMANHO_MAXIMO = 40


def validar_nome(db, nome, user_id=None):
    """Nome novo de usuário, já sem espaços nas pontas. Recusa nome em uso —
    inclusive por usuário na lixeira, que voltaria em conflito ao ser recuperado."""
    nome = (nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="O nome não pode ficar vazio.")
    if len(nome) > TAMANHO_MAXIMO:
        raise HTTPException(status_code=400, detail=f"O nome pode ter no máximo {TAMANHO_MAXIMO} caracteres.")
    outro = db.query(UserDB).filter(UserDB.nome == nome).first()
    if outro and outro.id != user_id:
        raise HTTPException(status_code=400, detail=f'Já existe um usuário chamado "{nome}".')
    if db.query(LixeiraDB).filter(LixeiraDB.tipo == "usuario", LixeiraDB.titulo == nome).first():
        raise HTTPException(status_code=400, detail=f'Há um usuário excluído chamado "{nome}" na lixeira — escolha outro nome.')
    return nome


def _no_valor(v, antigo, novo):
    if v == antigo:
        return novo
    if isinstance(v, list):
        return [novo if e == antigo else trocar_nome_em(e, antigo, novo) for e in v]
    return trocar_nome_em(v, antigo, novo)


def trocar_nome_em(x, antigo, novo):
    """Cópia de `x` (JSON) com `antigo` trocado por `novo` nas CHAVES_DE_NOME."""
    if isinstance(x, dict):
        return {k: (_no_valor(v, antigo, novo) if k in CHAVES_DE_NOME else trocar_nome_em(v, antigo, novo))
                for k, v in x.items()}
    if isinstance(x, list):
        return [trocar_nome_em(e, antigo, novo) for e in x]
    return x


def _na_lista(lista, antigo, novo):
    return [novo if e == antigo else e for e in lista]


def _no_texto_de_lista(texto, antigo, novo):
    """valor_antigo/valor_novo de responsaveis_alterados: nomes separados por vírgula."""
    if not texto:
        return texto
    return ", ".join(_na_lista(texto.split(", "), antigo, novo))


def _atualizar_json(linha, attr, antigo, novo, funcao=trocar_nome_em):
    atual = getattr(linha, attr)
    if atual is None:
        return
    trocado = funcao(atual, antigo, novo)
    if trocado != atual:
        # Objeto novo: o SQLAlchemy não percebe mutação dentro de coluna JSON.
        setattr(linha, attr, trocado)


def _reversao_de_log(reversao, antigo, novo, acao):
    trocado = trocar_nome_em(reversao, antigo, novo)
    if acao == "responsaveis_alterados":
        # Aqui antes/depois são listas de nomes sem chave que diga isso.
        for lado in ("antes", "depois"):
            if isinstance(trocado.get(lado), list):
                trocado[lado] = _na_lista(trocado[lado], antigo, novo)
    return trocado


def renomear_usuario(db, user, novo):
    """Troca o nome de `user` por `novo` em todo lugar. Não faz commit."""
    antigo = user.nome
    user.nome = novo

    for card in db.query(CardDB).all():
        if card.autor == antigo:
            card.autor = novo
        if antigo in (card.responsaveis or []):
            card.responsaveis = _na_lista(card.responsaveis, antigo, novo)
        _atualizar_json(card, "checklist", antigo, novo)
        _atualizar_json(card, "comentarios", antigo, novo)

    db.query(SuggestionDB).filter(SuggestionDB.autor == antigo).update({"autor": novo})
    db.query(SuggestionDB).filter(SuggestionDB.decidido_por == antigo).update({"decidido_por": novo})
    db.query(AttachmentDB).filter(AttachmentDB.enviado_por == antigo).update({"enviado_por": novo})
    db.query(TimeEntryDB).filter(TimeEntryDB.user_id == user.id).update({"usuario": novo})

    db.query(AuditLogDB).filter(AuditLogDB.usuario == antigo).update({"usuario": novo})
    db.query(AuditLogDB).filter(AuditLogDB.revertido_por == antigo).update({"revertido_por": novo})
    db.query(AuditLogDB).filter(AuditLogDB.alvo_tipo == "usuario", AuditLogDB.alvo_id == user.id).update({"card_titulo": novo})
    for log in db.query(AuditLogDB).filter(AuditLogDB.reversao != None).all():  # noqa: E711
        _atualizar_json(log, "reversao", antigo, novo, lambda r, a, n: _reversao_de_log(r, a, n, log.acao))
    for log in db.query(AuditLogDB).filter(AuditLogDB.acao == "responsaveis_alterados").all():
        log.valor_antigo = _no_texto_de_lista(log.valor_antigo, antigo, novo)
        log.valor_novo = _no_texto_de_lista(log.valor_novo, antigo, novo)

    db.query(LixeiraDB).filter(LixeiraDB.excluido_por == antigo).update({"excluido_por": novo})
    for item in db.query(LixeiraDB).all():
        _atualizar_json(item, "dados", antigo, novo)
    return antigo
