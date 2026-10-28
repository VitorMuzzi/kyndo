"""Lixeira: nada é apagado na hora.

Excluir guarda uma fotografia completa (a linha e o que depende dela) em
LixeiraDB e só então tira as linhas das tabelas vivas. Arquivos de anexo ficam
no disco até a lixeira expirar — sem a linha em AttachmentDB ninguém consegue
baixá-los, então continuam tão inacessíveis quanto antes.

Depois de PRAZO_DIAS, purgar_lixeira() apaga de vez (linha e arquivos).
Não há processo agendado neste app: a purga roda na subida e nas leituras da
auditoria/lixeira, como _apply_due_recurrences faz com a recorrência."""
import os
import uuid
from datetime import datetime, timedelta

from attachment_storage import caminho_do_anexo
from models import (
    AttachmentDB, CardDB, CardSeenDB, ColumnDB, DrawingDB, ItemSeenDB, LixeiraDB,
    RoleDB, SuggestionDB, TimeEntryDB, UserDB, UserNoteDB, UserRoleDB,
)

PRAZO_DIAS = 30


class RecuperacaoImpossivel(Exception):
    """O item não pode voltar sem passar por cima de algo que existe agora."""


def linha_para_dict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def dict_para_linha(model, dados):
    colunas = {c.name for c in model.__table__.columns}
    return model(**{k: v for k, v in (dados or {}).items() if k in colunas})


def expira_em(excluido_em_iso: str) -> datetime:
    return datetime.fromisoformat(excluido_em_iso) + timedelta(days=PRAZO_DIAS)


def _guardar(db, tipo, alvo_id, titulo, dados, usuario, card_id=None, dono_id=None):
    item = LixeiraDB(
        id=f"lix-{uuid.uuid4().hex[:12]}", tipo=tipo, alvo_id=alvo_id, titulo=titulo or "",
        card_id=card_id, dono_id=dono_id, dados=dados, excluido_por=usuario,
        excluido_em=datetime.now().isoformat(),
    )
    db.add(item)
    return item.id


# --------------------------------------------------------------------- card

def excluir_card(db, card, usuario):
    """Manda o card e tudo que só existe por causa dele pra lixeira. Sugestões,
    notas e desenhos vinculados continuam nas tabelas deles apontando pro id
    do card — reaparecem sozinhos quando ele volta. Não faz commit."""
    agora = datetime.now().isoformat()
    # Cronômetro rodando aqui para agora: recuperado depois, ele voltaria
    # "rodando" e a pessoa ficaria com dois ligados ao mesmo tempo.
    for e in db.query(TimeEntryDB).filter(TimeEntryDB.card_id == card.id, TimeEntryDB.fim == None).all():  # noqa: E711
        e.fim = agora
    db.flush()

    tempo = db.query(TimeEntryDB).filter(TimeEntryDB.card_id == card.id).all()
    anexos = db.query(AttachmentDB).filter(AttachmentDB.card_id == card.id).all()
    vistos = db.query(CardSeenDB).filter(CardSeenDB.card_id == card.id).all()
    itens_vistos = db.query(ItemSeenDB).filter(ItemSeenDB.card_id == card.id).all()
    dados = {
        "card": linha_para_dict(card),
        "tempo": [linha_para_dict(r) for r in tempo],
        "anexos": [linha_para_dict(r) for r in anexos],
        "card_seen": [linha_para_dict(r) for r in vistos],
        "item_seen": [linha_para_dict(r) for r in itens_vistos],
    }
    for r in tempo + anexos + vistos + itens_vistos:
        db.delete(r)
    db.delete(card)
    return _guardar(db, "card", card.id, card.titulo, dados, usuario, card_id=card.id)


def recuperar_card(db, dados):
    """Devolve o card. Se a coluna dele foi arquivada ou não existe mais, ele
    volta pra primeira coluna ativa — e o aviso diz isso. Retorna (card, aviso)."""
    base = dados["card"]
    if db.query(CardDB).filter(CardDB.id == base["id"]).first():
        raise RecuperacaoImpossivel("Já existe um card com este id — ele provavelmente já foi recuperado.")
    card = dict_para_linha(CardDB, base)
    aviso = None
    coluna = db.query(ColumnDB).filter(ColumnDB.id == card.status, ColumnDB.arquivado == False).first()  # noqa: E712
    if coluna is None:
        primeira = db.query(ColumnDB).filter(ColumnDB.arquivado == False).order_by(ColumnDB.ordem).first()  # noqa: E712
        if primeira is None:
            raise RecuperacaoImpossivel("Não há nenhuma coluna ativa para receber o card.")
        aviso = f'A coluna original não existe mais — o card voltou para "{primeira.titulo}".'
        card.status = primeira.id
    db.add(card)
    for r in dados.get("tempo") or []:
        if not db.query(TimeEntryDB).filter(TimeEntryDB.id == r["id"]).first():
            db.add(dict_para_linha(TimeEntryDB, r))
    for r in dados.get("anexos") or []:
        if not db.query(AttachmentDB).filter(AttachmentDB.id == r["id"]).first():
            db.add(dict_para_linha(AttachmentDB, r))
    for r in dados.get("card_seen") or []:
        if not db.query(CardSeenDB).filter(CardSeenDB.card_id == r["card_id"], CardSeenDB.user_id == r["user_id"]).first():
            db.add(dict_para_linha(CardSeenDB, r))
    for r in dados.get("item_seen") or []:
        if not db.query(ItemSeenDB).filter(ItemSeenDB.card_id == r["card_id"], ItemSeenDB.item_id == r["item_id"],
                                           ItemSeenDB.user_id == r["user_id"]).first():
            db.add(dict_para_linha(ItemSeenDB, r))
    return card, aviso


# ------------------------------------------------------- itens de uma linha

# tipo -> (modelo, como achar o título, card_id da linha, dono da linha)
TIPOS_SIMPLES = {
    "anexo": (AttachmentDB, lambda r: r.nome_original, lambda r: r.card_id, lambda r: None),
    "sugestao": (SuggestionDB, lambda r: (r.texto or "")[:80], lambda r: r.card_id, lambda r: None),
    "tempo": (TimeEntryDB, lambda r: r.usuario, lambda r: r.card_id, lambda r: None),
    "nota": (UserNoteDB, lambda r: r.titulo, lambda r: r.card_id, lambda r: r.user_id),
    "desenho": (DrawingDB, lambda r: r.titulo, lambda r: r.card_id, lambda r: r.user_id),
}


def excluir_linha(db, tipo, row, usuario):
    model, titulo, card_de, dono_de = TIPOS_SIMPLES[tipo]
    dados = {"linha": linha_para_dict(row)}
    lixeira_id = _guardar(db, tipo, row.id, titulo(row), dados, usuario, card_id=card_de(row), dono_id=dono_de(row))
    db.delete(row)
    return lixeira_id


def recuperar_linha(db, tipo, dados):
    model = TIPOS_SIMPLES[tipo][0]
    base = dados["linha"]
    if db.query(model).filter(model.id == base["id"]).first():
        raise RecuperacaoImpossivel("Este item já existe — provavelmente já foi recuperado.")
    card_id = base.get("card_id")
    # Nota/desenho podem ficar sem card; anexo, sugestão e tempo não existem sem ele.
    if tipo in ("anexo", "sugestao", "tempo") and not db.query(CardDB).filter(CardDB.id == card_id).first():
        raise RecuperacaoImpossivel("O card deste item está na lixeira — recupere o card primeiro.")
    linha = dict_para_linha(model, base)
    if tipo in ("nota", "desenho") and card_id and not db.query(CardDB).filter(CardDB.id == card_id).first():
        linha.card_id = None
    db.add(linha)
    return linha


# ------------------------------------------------------------- usuário/cargo

def excluir_usuario(db, user, usuario):
    vinculos = db.query(UserRoleDB).filter(UserRoleDB.user_id == user.id).all()
    dados = {"usuario": linha_para_dict(user), "cargos": [v.role_id for v in vinculos]}
    for v in vinculos:
        db.delete(v)
    db.delete(user)
    return _guardar(db, "usuario", user.id, user.nome, dados, usuario)


def recuperar_usuario(db, dados):
    base = dados["usuario"]
    if db.query(UserDB).filter(UserDB.id == base["id"]).first():
        raise RecuperacaoImpossivel("Este usuário já existe — provavelmente já foi recuperado.")
    if db.query(UserDB).filter(UserDB.nome == base["nome"]).first():
        raise RecuperacaoImpossivel(f'Já existe outro usuário chamado "{base["nome"]}" — renomeie ou exclua esse antes.')
    user = dict_para_linha(UserDB, base)
    # Sessões abertas antes da exclusão não voltam a valer junto com a conta.
    user.senha_versao = (user.senha_versao or 0) + 1
    db.add(user)
    cargos = [rid for rid in dados.get("cargos") or [] if db.query(RoleDB).filter(RoleDB.id == rid).first()]
    for rid in cargos:
        db.add(UserRoleDB(user_id=user.id, role_id=rid))
    return user, len(cargos) < len(dados.get("cargos") or [])


def excluir_cargo(db, role, usuario):
    vinculos = db.query(UserRoleDB).filter(UserRoleDB.role_id == role.id).all()
    dados = {"cargo": linha_para_dict(role), "usuarios": [v.user_id for v in vinculos]}
    for v in vinculos:
        db.delete(v)
    db.delete(role)
    return _guardar(db, "cargo", role.id, role.nome, dados, usuario)


def recuperar_cargo(db, dados):
    base = dados["cargo"]
    if db.query(RoleDB).filter(RoleDB.id == base["id"]).first():
        raise RecuperacaoImpossivel("Este cargo já existe — provavelmente já foi recuperado.")
    if db.query(RoleDB).filter(RoleDB.nome == base["nome"]).first():
        raise RecuperacaoImpossivel(f'Já existe outro cargo chamado "{base["nome"]}" — renomeie esse antes.')
    role = dict_para_linha(RoleDB, base)
    db.add(role)
    usuarios = [uid for uid in dados.get("usuarios") or [] if db.query(UserDB).filter(UserDB.id == uid).first()]
    for uid in usuarios:
        db.add(UserRoleDB(user_id=uid, role_id=role.id))
    return role, usuarios


# ------------------------------------------------------------------- purga

def _arquivos(item: LixeiraDB):
    dados = item.dados or {}
    if item.tipo == "anexo":
        return [dados.get("linha", {}).get("nome_arquivo")]
    if item.tipo == "card":
        return [a.get("nome_arquivo") for a in dados.get("anexos") or []]
    return []


def purgar_lixeira(db):
    """Apaga de vez o que passou do prazo. Faz commit."""
    limite = (datetime.now() - timedelta(days=PRAZO_DIAS)).isoformat()
    vencidos = db.query(LixeiraDB).filter(LixeiraDB.excluido_em < limite).all()
    if not vencidos:
        return 0
    for item in vencidos:
        for nome in _arquivos(item):
            if not nome:
                continue
            caminho = caminho_do_anexo(nome)
            if os.path.isfile(caminho):
                try:
                    os.remove(caminho)
                except OSError:
                    pass  # arquivo travado fica pra próxima purga; a linha some de qualquer jeito
        if item.tipo == "card":
            # O card não volta mais: o que ficou apontando pra ele perde o vínculo.
            db.query(SuggestionDB).filter(SuggestionDB.card_id == item.alvo_id).delete(synchronize_session=False)
            db.query(UserNoteDB).filter(UserNoteDB.card_id == item.alvo_id).update({UserNoteDB.card_id: None}, synchronize_session=False)
            db.query(DrawingDB).filter(DrawingDB.card_id == item.alvo_id).update({DrawingDB.card_id: None}, synchronize_session=False)
        db.delete(item)
    db.commit()
    return len(vencidos)
