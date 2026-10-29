"""Desfazer qualquer alteração registrada na auditoria (até PRAZO_DIAS).

Regra que vale pra tudo aqui: desfazer só acontece se o alvo ainda estiver
exatamente como a alteração o deixou E não houver registro posterior sobre o
mesmo alvo — comparar só o valor não basta, porque alguém pode ter mudado e
voltado ao mesmo valor (e desfazer apagaria essa decisão). Se houve, nada é
tocado e a resposta diz quem mexeu e quando.

Todo desfazer também é registrado na auditoria, com os dados pra ser desfeito
de novo (refazer). O registro original fica marcado como desfeito.

Cada `acao` do log tem um tratador em TRATADORES. Ações que não aparecem lá
são só informativas (ex.: "sugestão revogada sem reverter")."""
import json
from datetime import datetime, timedelta

from fastapi import HTTPException

from audit import SIMPLE_CARD_FIELDS, SIMPLE_CARD_FIELDS_MAP, SUBETAPA_FIELDS, _mk_log, posicao_em
from card_merge import campos_destino
from lixeira import (
    PRAZO_DIAS, linha_para_dict, RecuperacaoImpossivel, dict_para_linha, excluir_card, excluir_cargo, excluir_linha,
    excluir_usuario, recuperar_card, recuperar_cargo, recuperar_linha, recuperar_usuario,
)
from models import (
    AttachmentDB, AuditLogDB, CardDB, CardSeenDB, ColumnDB, DrawingDB, ItemSeenDB, LixeiraDB,
    RoleDB, SuggestionDB, TimeEntryDB, UserDB, UserNoteDB, UserRoleDB,
)
from rbac import PERMISSIONS, get_user_permissions, get_visible_column_ids, is_superadmin
from renomear import renomear_usuario, validar_nome
from routers.columns import coluna_de
from routers.roles import (
    cargo_de, checar_atribuicao, checar_cargo_proprio, checar_colunas, checar_concessao, validar_troca_de_cargos,
)
from routers.suggestions import apagar_sugestao, decisao_de


class Conflito(Exception):
    """Desfazer passaria por cima de algo que mudou depois — ou não é possível."""


ACAO_DO_CAMPO = {acao: campo for campo, acao in SIMPLE_CARD_FIELDS}
ROTULO_CAMPO = {
    "titulo": "O título", "descricao": "A descrição", "status": "A coluna", "prioridade": "A prioridade",
    "prazo": "O prazo", "github_url": "O link do GitHub",
}


def _fmt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return iso or ""


def _copia(x):
    return json.loads(json.dumps(x))


class _Ctx:
    def __init__(self, db, log, usuario):
        self.db = db
        self.log = log
        self.usuario = usuario
        self.nome = usuario.nome
        self.r = log.reversao or {}
        self.mensagem = "Alteração desfeita."

    def registrar(self, card_id, titulo, acao, **kw):
        kw.setdefault("detalhe", f"desfez: {self.log.usuario} em {_fmt(self.log.data)}")
        _mk_log(self.db, card_id, titulo, self.nome, acao, **kw)

    def posteriores(self, card_id=None, alvo_id=None):
        """Registros sobre o mesmo alvo feitos depois deste, mais recente primeiro."""
        q = self.db.query(AuditLogDB).filter(AuditLogDB.data > self.log.data, AuditLogDB.id != self.log.id)
        q = q.filter(AuditLogDB.card_id == card_id) if card_id else q.filter(AuditLogDB.alvo_id == alvo_id)
        return q.order_by(AuditLogDB.data.desc()).all()

    def por_quem(self, card_id=None, alvo_id=None, filtro=lambda log: True):
        for log in self.posteriores(card_id, alvo_id):
            if filtro(log):
                return f" — por {log.usuario} em {_fmt(log.data)}"
        return ""


def _card(ctx, card_id=None):
    card = ctx.db.query(CardDB).filter(CardDB.id == (card_id or ctx.log.card_id)).first()
    if card is None:
        raise Conflito("O card está na lixeira — recupere o card primeiro.")
    return card


def _mexeu(card):
    card.alteracoes = (card.alteracoes or 0) + 1
    card.updated_em = datetime.now().isoformat()


def _da_lixeira(ctx):
    item = ctx.db.query(LixeiraDB).filter(LixeiraDB.id == ctx.r.get("lixeira_id")).first()
    if item is None:
        raise Conflito("Este item já foi recuperado ou passou do prazo de 30 dias.")
    return item


def _exigir_coluna_visivel(ctx, col_id):
    """Mesma trava do update_card: quem tem colunas restritas não manda card
    pra coluna que não enxerga — desfazer não pode ser o atalho."""
    visiveis = get_visible_column_ids(ctx.db, ctx.usuario.id)
    if visiveis is not None and col_id not in visiveis:
        raise Conflito("O card voltaria para uma coluna que você não pode ver.")


def _coluna_ativa(db, col_id):
    return db.query(ColumnDB).filter(ColumnDB.id == col_id, ColumnDB.arquivado == False).first()  # noqa: E712


# ------------------------------------------------------------ campos do card

def _desfazer_campo(ctx):
    card = _card(ctx)
    acao = ctx.log.acao
    campo = ACAO_DO_CAMPO[acao]
    # Registros antigos não têm `reversao`: os valores do próprio log servem.
    antes = ctx.r["antes"] if "campo" in ctx.r else ctx.log.valor_antigo
    depois = ctx.r["depois"] if "campo" in ctx.r else ctx.log.valor_novo
    atual = getattr(card, campo)
    quem = ctx.por_quem(card.id, filtro=lambda l: l.acao == acao)
    if quem or (atual or "") != (depois or ""):
        raise Conflito(f"{ROTULO_CAMPO[campo]} foi alterado de novo depois{quem}. Desfazer apagaria essa alteração.")
    if campo == "status":
        if not _coluna_ativa(ctx.db, antes):
            raise Conflito("A coluna de antes foi arquivada ou não existe mais.")
        _exigir_coluna_visivel(ctx, antes)
    if campo == "prioridade" and not antes:
        antes = "Normal"
    if campo in ("titulo", "descricao"):
        antes = antes or ""
    setattr(card, campo, antes or (None if campo in ("prazo", "github_url") else antes))
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, acao, valor_antigo=atual or None, valor_novo=antes or None,
                  reversao={"campo": campo, "antes": atual, "depois": getattr(card, campo)})


def _desfazer_responsaveis(ctx):
    card = _card(ctx)
    separar = lambda v: [n.strip() for n in (v or "").split(",") if n.strip()]  # noqa: E731
    antes = ctx.r.get("antes", separar(ctx.log.valor_antigo))
    depois = ctx.r.get("depois", separar(ctx.log.valor_novo))
    atual = list(card.responsaveis or [])
    quem = ctx.por_quem(card.id, filtro=lambda l: l.acao == "responsaveis_alterados")
    if quem or sorted(atual) != sorted(depois):
        raise Conflito(f"Os responsáveis foram alterados de novo depois{quem}.")
    card.responsaveis = antes or [card.autor]
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, "responsaveis_alterados",
                  valor_antigo=", ".join(sorted(atual)) or None, valor_novo=", ".join(sorted(card.responsaveis)) or None,
                  reversao={"antes": atual, "depois": list(card.responsaveis)})


def _recorrencia_de(card):
    return {
        "recorrente": bool(card.recorrente), "recorrencia_dias": card.recorrencia_dias,
        "recorrencia_coluna_reset": card.recorrencia_coluna_reset,
        "recorrencia_proximo_reset": card.recorrencia_proximo_reset,
    }


def _desfazer_recorrencia(ctx):
    card = _card(ctx)
    antes, depois = ctx.r["antes"], ctx.r["depois"]
    atual = _recorrencia_de(card)
    # O próximo reinício anda sozinho com o tempo — não conta como mudança.
    chaves = ("recorrencia_dias", "recorrencia_coluna_reset", "recorrente")
    quem = ctx.por_quem(card.id, filtro=lambda l: l.acao.startswith("recorrencia_"))
    if quem or any(atual[k] != depois.get(k) for k in chaves):
        raise Conflito(f"A recorrência foi alterada de novo depois{quem}.")
    for k, v in antes.items():
        setattr(card, k, v)
    if card.recorrente:
        # Um reinício que venceu enquanto estava desligada dispararia na hora.
        proximo = card.recorrencia_proximo_reset
        if not proximo or proximo <= datetime.now().isoformat():
            card.recorrencia_proximo_reset = (datetime.now() + timedelta(days=card.recorrencia_dias or 1)).isoformat()
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, "recorrencia_configurada" if card.recorrente else "recorrencia_desativada",
                  reversao={"antes": atual, "depois": _recorrencia_de(card)})


def _sem_versao(checklist):
    """Compara checklists ignorando contadores de leitura de observação."""
    limpo = _copia(checklist or [])
    for item in limpo:
        item.pop("notas_versao", None)
        item.pop("notas_nao_vista", None)
    return limpo


def _desfazer_reinicio(ctx):
    card = _card(ctx)
    antes, depois = ctx.r["antes"], ctx.r["depois"]
    mexeu = ctx.por_quem(card.id, filtro=lambda l: l.acao.startswith(ACOES_DE_ETAPA) or l.acao == "status_alterado")
    if mexeu or _sem_versao(card.checklist) != _sem_versao(depois["checklist"]) or card.status != depois["status"]:
        raise Conflito(f"As etapas ou a coluna do card mudaram depois do reinício{mexeu} — desfazer apagaria essas mudanças.")
    if card.status != antes["status"] and not _coluna_ativa(ctx.db, antes["status"]):
        raise Conflito("A coluna de antes do reinício foi arquivada ou não existe mais.")
    atual = {"checklist": card.checklist, "status": card.status}
    card.checklist = _copia(antes["checklist"])
    card.status = antes["status"]
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, "reinicio_recorrente_desfeito", reversao={"antes": atual, "depois": antes})


# ------------------------------------------------------------ etapas

ACOES_DE_ETAPA = ("etapa", "subetapa", "tarefa_recorrente", "reinicio_recorrente")

def _localizar(checklist, item_id):
    """(id do pai ou None, índice na lista dele, o item)."""
    for i, item in enumerate(checklist):
        if item.get("id") == item_id:
            return None, i, item
        for j, s in enumerate(item.get("subetapas") or []):
            if s.get("id") == item_id:
                return item.get("id"), j, s
    return None


def _todos_ids(checklist):
    ids = set()
    for item in checklist:
        ids.add(item.get("id"))
        ids.update(s.get("id") for s in item.get("subetapas") or [])
    return ids


def _lista(checklist, pai_id):
    if pai_id is None:
        return checklist
    for item in checklist:
        if item.get("id") == pai_id:
            item.setdefault("subetapas", [])
            return item["subetapas"]
    return None


def _inserir(lista, novo, indice, anterior_id):
    if anterior_id is None:
        lista.insert(0, novo)
        return
    for i, x in enumerate(lista):
        if x.get("id") == anterior_id:
            lista.insert(i + 1, novo)
            return
    lista.insert(min(indice if indice is not None else len(lista), len(lista)), novo)


def _igual(a, b):
    return _sem_versao([a]) == _sem_versao([b])


def _nome_nivel(pai_id):
    return "sub-etapa" if pai_id else "etapa"


def _quem_mexeu_no_item(ctx, card_id, item_id, acoes=None):
    """Registro posterior sobre esta etapa (só das `acoes` dadas, se houver)."""
    def toca(log):
        if acoes and log.acao not in acoes:
            return False
        r = log.reversao or {}
        return r.get("item_id") == item_id or (r.get("item") or {}).get("id") == item_id
    return ctx.por_quem(card_id, filtro=toca)


def _desfazer_criacao_etapa(ctx):
    card = _card(ctx)
    checklist = _copia(card.checklist or [])
    snap = ctx.r["item"]
    achado = _localizar(checklist, snap["id"])
    if achado is None:
        raise Conflito(f'A {_nome_nivel(ctx.r.get("pai_id"))} "{snap.get("texto")}" já não existe mais.')
    pai_id, indice, atual = achado
    quem = _quem_mexeu_no_item(ctx, card.id, snap["id"])
    if quem or not _igual(atual, snap):
        raise Conflito(f'"{snap.get("texto")}" foi alterada depois de criada{quem}. '
                       "Desfazer a criação apagaria essas alterações — se for o caso, exclua pelo card.")
    lista = _lista(checklist, pai_id)
    _, anterior = posicao_em(lista, atual["id"])
    lista.pop(indice)
    card.checklist = checklist
    _mexeu(card)
    acao = "subetapa_excluida" if pai_id else "etapa_excluida"
    ctx.registrar(card.id, card.titulo, acao, reversao={"pai_id": pai_id, "item": atual, "indice": indice, "anterior_id": anterior})


def _desfazer_exclusao_etapa(ctx):
    card = _card(ctx)
    checklist = _copia(card.checklist or [])
    item = _copia(ctx.r["item"])
    pai_id = ctx.r.get("pai_id")
    ids_item = {item["id"]} | {s.get("id") for s in item.get("subetapas") or []}
    if ids_item & _todos_ids(checklist):
        raise Conflito(f'"{item.get("texto")}" já está no card — provavelmente já foi recuperada.')
    lista = _lista(checklist, pai_id)
    if lista is None:
        raise Conflito(f'A etapa-mãe de "{item.get("texto")}" não existe mais — recupere-a primeiro.')
    _inserir(lista, item, ctx.r.get("indice"), ctx.r.get("anterior_id"))
    card.checklist = checklist
    _mexeu(card)
    ctx.mensagem = f'"{item.get("texto")}" voltou para o card.'
    acao = "subetapa_criada" if pai_id else "etapa_criada"
    ctx.registrar(card.id, card.titulo, acao, reversao={"pai_id": pai_id, "item": item})


def _item_existente(ctx, card, checklist):
    achado = _localizar(checklist, ctx.r["item_id"])
    if achado is None:
        raise Conflito("Esta etapa não existe mais no card.")
    return achado


def _desfazer_texto_etapa(ctx):
    card = _card(ctx)
    checklist = _copia(card.checklist or [])
    _, _, item = _item_existente(ctx, card, checklist)
    quem = _quem_mexeu_no_item(ctx, card.id, item["id"], ("etapa_editada", "subetapa_editada"))
    if quem or (item.get("texto") or "") != (ctx.r["depois"] or ""):
        raise Conflito(f"O texto foi alterado de novo depois{quem}.")
    atual = item.get("texto")
    item["texto"] = ctx.r["antes"]
    card.checklist = checklist
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, ctx.log.acao, valor_antigo=atual, valor_novo=ctx.r["antes"],
                  reversao={"item_id": item["id"], "antes": atual, "depois": ctx.r["antes"]})


def _desfazer_conclusao(ctx):
    card = _card(ctx)
    checklist = _copia(card.checklist or [])
    pai_id, _, item = _item_existente(ctx, card, checklist)
    antes, depois = ctx.r["antes"], ctx.r["depois"]
    quem = _quem_mexeu_no_item(ctx, card.id, item["id"],
                               ("etapa_concluida", "etapa_reaberta", "subetapa_concluida", "subetapa_reaberta"))
    if quem or bool(item.get("concluido")) != bool(depois["concluido"]) \
            or item.get("concluidoPor") != depois.get("concluidoPor"):
        raise Conflito(f'"{item.get("texto")}" mudou de estado de novo depois{quem}.')
    atual = {"concluido": bool(item.get("concluido")), "concluidoPor": item.get("concluidoPor")}
    item["concluido"] = antes["concluido"]
    item["concluidoPor"] = antes["concluidoPor"]
    card.checklist = checklist
    _mexeu(card)
    nivel = "subetapa" if pai_id else "etapa"
    acao = f"{nivel}_concluida" if antes["concluido"] else f"{nivel}_reaberta"
    ctx.registrar(card.id, card.titulo, acao, reversao={"item_id": item["id"], "antes": atual, "depois": antes})


def _desfazer_observacao(ctx):
    card = _card(ctx)
    checklist = _copia(card.checklist or [])
    _, _, item = _item_existente(ctx, card, checklist)
    quem = _quem_mexeu_no_item(ctx, card.id, item["id"], ("etapa_observacao_editada",))
    if quem or (item.get("notas") or "") != (ctx.r["depois"] or ""):
        raise Conflito(f"A observação foi alterada de novo depois{quem}.")
    atual = item.get("notas")
    item["notas"] = ctx.r["antes"]
    item["notas_versao"] = (item.get("notas_versao") or 0) + 1
    card.checklist = checklist
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, "etapa_observacao_editada", valor_antigo=atual, valor_novo=ctx.r["antes"],
                  reversao={"item_id": item["id"], "antes": atual, "depois": ctx.r["antes"]})


def _desfazer_movimento(ctx):
    card = _card(ctx)
    checklist = _copia(card.checklist or [])
    pai_atual, indice_atual, item = _item_existente(ctx, card, checklist)
    quem = _quem_mexeu_no_item(ctx, card.id, item["id"], ("etapa_indentada", "etapa_desindentada", "subetapa_movida"))
    if quem or pai_atual != ctx.r["depois"]["pai_id"]:
        raise Conflito(f'"{item.get("texto")}" mudou de lugar de novo depois{quem}.')
    destino_pai = ctx.r["antes"]["pai_id"]
    if destino_pai is not None and item.get("subetapas"):
        raise Conflito(f'"{item.get("texto")}" agora tem sub-etapas — não dá para ela voltar a ser sub-etapa.')
    if destino_pai is not None and (item.get("notas") or "").strip():
        raise Conflito(f'"{item.get("texto")}" tem observação agora, e sub-etapa não guarda observação — '
                       "voltar a ser sub-etapa apagaria a observação.")
    destino = _lista(checklist, destino_pai)
    if destino is None:
        raise Conflito("A etapa-mãe de antes não existe mais.")
    _lista(checklist, pai_atual).pop(indice_atual)
    if destino_pai is None:
        movido = {**item, "subetapas": item.get("subetapas") or []}
    else:
        movido = {k: item[k] for k in SUBETAPA_FIELDS if k in item}
    indice = ctx.r["antes"].get("indice")
    destino.insert(min(indice if indice is not None else len(destino), len(destino)), movido)
    card.checklist = checklist
    _mexeu(card)
    if pai_atual is None:
        acao = "etapa_indentada"
    elif destino_pai is None:
        acao = "etapa_desindentada"
    else:
        acao = "subetapa_movida"
    ctx.registrar(card.id, card.titulo, acao, reversao={
        "item_id": item["id"], "antes": {"pai_id": pai_atual, "indice": indice_atual}, "depois": {"pai_id": destino_pai}})


def _sequencia(checklist):
    seq = []
    for item in checklist:
        seq.append(item.get("id"))
        seq.extend(s.get("id") for s in item.get("subetapas") or [])
    return seq


def _desfazer_reordenacao(ctx):
    card = _card(ctx)
    checklist = _copia(card.checklist or [])
    quem = ctx.por_quem(card.id, filtro=lambda l: l.acao in (
        "etapas_reordenadas", "etapa_indentada", "etapa_desindentada", "subetapa_movida"))
    if quem or _sequencia(checklist) != ctx.r["depois"]:
        raise Conflito(f"As etapas mudaram de novo depois{quem}.")
    ordem = {iid: i for i, iid in enumerate(ctx.r["antes"])}
    fim = len(ordem)
    checklist.sort(key=lambda it: ordem.get(it.get("id"), fim))
    for item in checklist:
        item["subetapas"] = sorted(item.get("subetapas") or [], key=lambda s: ordem.get(s.get("id"), fim))
    card.checklist = checklist
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, "etapas_reordenadas", reversao={"antes": ctx.r["depois"], "depois": ctx.r["antes"]})


# ------------------------------------------------------------ comentários

def _desfazer_comentario_adicionado(ctx):
    card = _card(ctx)
    comentarios = _copia(card.comentarios or [])
    snap = ctx.r["comentario"]
    indice, anterior = posicao_em(comentarios, snap.get("id"))
    if indice is None:
        raise Conflito("Este comentário já foi removido.")
    if comentarios[indice] != snap:
        raise Conflito("O comentário foi alterado depois.")
    comentarios.pop(indice)
    card.comentarios = comentarios
    _mexeu(card)
    ctx.registrar(card.id, card.titulo, "comentario_removido",
                  reversao={"comentario": snap, "indice": indice, "anterior_id": anterior})


def _desfazer_comentario_removido(ctx):
    card = _card(ctx)
    comentarios = _copia(card.comentarios or [])
    snap = ctx.r["comentario"]
    if any(c.get("id") == snap.get("id") for c in comentarios):
        raise Conflito("Este comentário já está no card.")
    _inserir(comentarios, snap, ctx.r.get("indice"), ctx.r.get("anterior_id"))
    card.comentarios = comentarios
    _mexeu(card)
    ctx.mensagem = "O comentário voltou para o card."
    ctx.registrar(card.id, card.titulo, "comentario_adicionado", reversao={"comentario": snap})


# ------------------------------------------------------------ card inteiro

def _desfazer_existencia_card(ctx):
    """card_criado / card_restaurado: tira o card — só se ninguém mexeu nele depois."""
    card = _card(ctx)
    depois = ctx.posteriores(card.id)
    if depois:
        raise Conflito(f"O card teve {len(depois)} alteração(ões) depois (a última por {depois[0].usuario} "
                       f"em {_fmt(depois[0].data)}). Para removê-lo mesmo assim, exclua o card.")
    # Cronômetro não entra no log: sem esta checagem, desfazer pararia o
    # cronômetro de alguém e levaria as horas dele pra lixeira.
    if ctx.db.query(TimeEntryDB).filter(TimeEntryDB.card_id == card.id).count():
        raise Conflito("Já tem tempo registrado neste card. Para removê-lo mesmo assim, exclua o card.")
    lixeira_id = excluir_card(ctx.db, card, ctx.nome)
    ctx.mensagem = "O card foi para a lixeira."
    ctx.registrar(card.id, card.titulo, "card_excluido", lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})


def _desfazer_exclusao_card(ctx):
    item = _da_lixeira(ctx)
    card, aviso = recuperar_card(ctx.db, item.dados)
    ctx.db.delete(item)
    ctx.mensagem = aviso or "O card foi recuperado."
    ctx.registrar(card.id, card.titulo, "card_restaurado", detalhe=aviso or f"recuperou o card excluído por {ctx.log.usuario}")


def _desfazer_fusao(ctx):
    r = ctx.r
    destino = ctx.db.query(CardDB).filter(CardDB.id == r["destino_id"]).first()
    if destino is None:
        raise Conflito("O card que recebeu a fusão está na lixeira — recupere-o primeiro.")
    origem_base = r["origem"]
    if ctx.db.query(CardDB).filter(CardDB.id == origem_base["id"]).first():
        raise Conflito("O card de origem já existe de novo.")
    depois = ctx.posteriores(destino.id)
    if depois or _copia(campos_destino(destino)) != _copia(r["destino_depois"]):
        quem = f" (a última por {depois[0].usuario} em {_fmt(depois[0].data)})" if depois else ""
        raise Conflito(f'"{destino.titulo}" foi alterado depois da fusão{quem}. Desfazer a fusão apagaria essas alterações.')
    tempo_novo = ctx.db.query(TimeEntryDB).filter(
        TimeEntryDB.card_id == destino.id, TimeEntryDB.inicio > ctx.log.data).count()
    if tempo_novo:
        raise Conflito(f'Registraram tempo em "{destino.titulo}" depois da fusão — desfazer deixaria essas horas '
                       "apontando para etapas que voltariam para o outro card.")

    for campo, valor in r["destino_antes"].items():
        setattr(destino, campo, valor)
    origem = dict_para_linha(CardDB, origem_base)
    if not _coluna_ativa(ctx.db, origem.status):
        origem.status = destino.status
    _exigir_coluna_visivel(ctx, origem.status)
    ctx.db.add(origem)

    m = r["movidos"]
    for model, chave in ((AttachmentDB, "anexos"), (SuggestionDB, "sugestoes"), (UserNoteDB, "notas"),
                         (DrawingDB, "desenhos"), (AuditLogDB, "logs")):
        if m.get(chave):
            ctx.db.query(model).filter(model.id.in_(m[chave]), model.card_id == destino.id).update(
                {model.card_id: origem.id}, synchronize_session=False)
    if m.get("logs"):
        # Desmarca: os registros voltaram pro card deles e podem ser desfeitos de novo.
        ctx.db.query(AuditLogDB).filter(AuditLogDB.id.in_(m["logs"])).update(
            {AuditLogDB.alvo_id: None}, synchronize_session=False)
    for t in m.get("tempo") or []:
        row = ctx.db.query(TimeEntryDB).filter(TimeEntryDB.id == t["id"], TimeEntryDB.card_id == destino.id).first()
        if row:
            row.card_id = origem.id
            row.item_id = t["item_id"]
    for linha in r.get("card_seen") or []:
        ctx.db.add(dict_para_linha(CardSeenDB, linha))
    for linha in r.get("item_seen") or []:
        ctx.db.add(dict_para_linha(ItemSeenDB, linha))
    _mexeu(destino)
    ctx.mensagem = f'"{origem.titulo}" voltou a ser um card separado.'
    ctx.registrar(destino.id, destino.titulo, "fusao_desfeita", detalhe=f'"{origem.titulo}" voltou a ser um card separado')
    ctx.registrar(origem.id, origem.titulo, "fusao_desfeita", detalhe=f'separado de "{destino.titulo}" de novo')


# ------------------------------------------------------------ itens de uma linha

def _desfazer_exclusao_linha(tipo, acao_restaurada):
    def tratador(ctx):
        item = _da_lixeira(ctx)
        dados = item.dados
        if tipo == "tempo" and dados["linha"].get("fim") is None:
            # Cronômetro apagado enquanto rodava volta parado no momento da exclusão.
            dados = {"linha": {**dados["linha"], "fim": item.excluido_em}}
        if tipo == "sugestao" and ctx.r.get("reverteu"):
            _reaplicar_sugestao(ctx, dados["linha"])
        linha = recuperar_linha(ctx.db, tipo, dados)
        ctx.db.delete(item)
        ctx.mensagem = "Item recuperado."
        # A fotografia de como voltou: desfazer a recuperação só vale se nada mudou desde então.
        rev = {"id": linha.id, "linha": _copia(linha_para_dict(linha))}
        if tipo in ("nota", "desenho"):
            ctx.registrar(None, item.titulo, acao_restaurada, alvo_tipo=tipo, alvo_id=linha.id, reversao=rev)
        else:
            card = ctx.db.query(CardDB).filter(CardDB.id == linha.card_id).first()
            ctx.registrar(linha.card_id, card.titulo if card else "", acao_restaurada, reversao=rev,
                          detalhe=f"recuperou: {item.titulo}")
    return tratador


def _desfazer_existencia_linha(tipo, model, acao_excluida):
    def tratador(ctx):
        rid = ctx.r.get("id") or ctx.r.get("anexo_id") or ctx.r.get("sug_id")
        row = ctx.db.query(model).filter(model.id == rid).first()
        if row is None:
            raise Conflito("Este item já não existe mais.")
        if "linha" in ctx.r and _copia(linha_para_dict(row)) != ctx.r["linha"]:
            raise Conflito("O item foi alterado depois de recuperado — desfazer apagaria essas alterações.")
        if tipo == "sugestao":
            card = _card(ctx, row.card_id)
            if ctx.log.acao == "sugestao_criada" and row.status != "pendente":
                raise Conflito("A sugestão já foi decidida — desfaça a decisão primeiro.")
            if row.status == "aceita" and row.campo_alvo and row.valor_anterior is not None \
                    and (_valor_alvo(card, row.campo_alvo) or "") != (row.valor_proposto or ""):
                raise Conflito("O campo que a sugestão alterou mudou de novo depois.")
            _, reverteu = apagar_sugestao(ctx.db, row, card, ctx.nome)
            if reverteu:
                _mexeu(card)
            ctx.mensagem = "A sugestão foi para a lixeira."
            return
        lixeira_id = excluir_linha(ctx.db, tipo, row, ctx.nome)
        ctx.mensagem = "O item foi para a lixeira."
        if tipo in ("nota", "desenho"):
            ctx.registrar(None, row.titulo, acao_excluida, alvo_tipo=tipo, alvo_id=row.id,
                          lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})
        else:
            card = ctx.db.query(CardDB).filter(CardDB.id == row.card_id).first()
            ctx.registrar(row.card_id, card.titulo if card else "", acao_excluida,
                          lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})
    return tratador


# ------------------------------------------------------------ sugestões

def _valor_alvo(card, campo_alvo):
    if campo_alvo.startswith("etapa:"):
        achado = _localizar(card.checklist or [], campo_alvo.split(":", 1)[1])
        return achado[2].get("texto") if achado else None
    return getattr(card, campo_alvo)


def _definir_alvo(ctx, card, campo_alvo, valor):
    atual = _valor_alvo(card, campo_alvo)
    if campo_alvo.startswith("etapa:"):
        checklist = _copia(card.checklist or [])
        achado = _localizar(checklist, campo_alvo.split(":", 1)[1])
        if achado is None:
            raise Conflito("A etapa que a sugestão alterava não existe mais.")
        achado[2]["texto"] = valor
        card.checklist = checklist
        ctx.registrar(card.id, card.titulo, "etapa_editada", valor_antigo=atual, valor_novo=valor,
                      reversao={"item_id": achado[2]["id"], "antes": atual, "depois": valor})
    else:
        setattr(card, campo_alvo, valor)
        ctx.registrar(card.id, card.titulo, SIMPLE_CARD_FIELDS_MAP[campo_alvo], valor_antigo=atual or None, valor_novo=valor or None,
                      reversao={"campo": campo_alvo, "antes": atual, "depois": valor})
    _mexeu(card)


def _reaplicar_sugestao(ctx, linha):
    """Recuperar uma sugestão aceita cuja exclusão desfez o que ela aplicou:
    aplica de novo — se o campo ainda estiver como a exclusão o deixou."""
    card = _card(ctx, linha["card_id"])
    if (_valor_alvo(card, linha["campo_alvo"]) or "") != (linha.get("valor_anterior") or ""):
        raise Conflito("O campo que a sugestão alterava mudou depois da exclusão.")
    _definir_alvo(ctx, card, linha["campo_alvo"], linha["valor_proposto"])


def _desfazer_decisao(ctx):
    r = ctx.r
    sug = ctx.db.query(SuggestionDB).filter(SuggestionDB.id == r["sug_id"]).first()
    if sug is None:
        raise Conflito("A sugestão não existe mais (está na lixeira?).")
    card = _card(ctx, sug.card_id)
    quem = ctx.por_quem(card.id, filtro=lambda l: (l.reversao or {}).get("sug_id") == sug.id)
    if quem or decisao_de(sug) != r["depois"]:
        raise Conflito(f"A decisão desta sugestão mudou de novo depois{quem}.")
    if r.get("aplicou"):
        if (_valor_alvo(card, sug.campo_alvo) or "") != (sug.valor_proposto or ""):
            raise Conflito("O campo que a sugestão alterou mudou de novo depois.")
        _definir_alvo(ctx, card, sug.campo_alvo, r["depois"]["valor_anterior"])
    if r.get("reverteu"):
        if (_valor_alvo(card, sug.campo_alvo) or "") != (r["antes"]["valor_anterior"] or ""):
            raise Conflito("O campo que a sugestão alterava mudou depois.")
        _definir_alvo(ctx, card, sug.campo_alvo, sug.valor_proposto)
    for campo, valor in r["antes"].items():
        setattr(sug, campo, valor)
    ctx.mensagem = f'A sugestão voltou para "{sug.status}".'
    ctx.registrar(card.id, card.titulo, "sugestao_decisao_desfeita", reversao={
        "sug_id": sug.id, "antes": r["depois"], "depois": r["antes"],
        "aplicou": bool(r.get("reverteu")), "reverteu": bool(r.get("aplicou"))})


# ------------------------------------------------------------ usuários e cargos

def _regra(funcao, *args):
    """As regras de cargo do router levantam HTTPException; aqui viram Conflito."""
    try:
        return funcao(*args)
    except HTTPException as e:
        raise Conflito(e.detail)


def _checar_superadmin(ctx, alvo_ids_de_cargo):
    protegidos = {r.id for r in ctx.db.query(RoleDB).filter(RoleDB.protegido == True).all()}  # noqa: E712
    if protegidos & set(alvo_ids_de_cargo) and not is_superadmin(ctx.db, ctx.usuario):
        raise Conflito("Só um Superadmin pode mexer em quem tem o cargo Superadmin.")


def _desfazer_existencia_usuario(ctx):
    user = ctx.db.query(UserDB).filter(UserDB.id == ctx.r.get("user_id")).first()
    if user is None:
        raise Conflito("Este usuário já não existe mais.")
    if user.nome == "admin" or user.id == ctx.usuario.id:
        raise Conflito("Esta conta não pode ser removida por aqui.")
    # A pessoa já usou a conta (trocou a senha, agiu no sistema) ou alguém
    # mexeu nela: remover agora passaria por cima disso.
    usou = ctx.db.query(AuditLogDB).filter(AuditLogDB.data > ctx.log.data, AuditLogDB.usuario == user.nome).first()
    if usou or (user.senha_versao or 0) != ctx.r.get("senha_versao", user.senha_versao or 0):
        raise Conflito(f"{user.nome} já usou a conta depois disso. Para removê-la mesmo assim, exclua o usuário.")
    quem = ctx.por_quem(alvo_id=user.id)
    if quem:
        raise Conflito(f"A conta de {user.nome} foi alterada depois{quem}.")
    cargos = [v.role_id for v in ctx.db.query(UserRoleDB).filter(UserRoleDB.user_id == user.id).all()]
    _checar_superadmin(ctx, cargos)
    if is_superadmin(ctx.db, user) and sum(1 for u in ctx.db.query(UserDB).all() if is_superadmin(ctx.db, u)) <= 1:
        raise Conflito("É o único Superadmin do sistema.")
    lixeira_id = excluir_usuario(ctx.db, user, ctx.nome)
    ctx.mensagem = "O usuário foi para a lixeira."
    ctx.registrar(None, user.nome, "usuario_excluido", alvo_tipo="usuario", alvo_id=user.id,
                  lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})


def _desfazer_renomeacao(ctx):
    r = ctx.r
    user = ctx.db.query(UserDB).filter(UserDB.id == r["user_id"]).first()
    if user is None:
        raise Conflito("Este usuário não existe mais (está na lixeira?).")
    quem = ctx.por_quem(alvo_id=user.id, filtro=lambda l: l.acao == "usuario_renomeado")
    if quem or user.nome != r["depois"]:
        raise Conflito(f"{user.nome} foi renomeado de novo depois{quem}.")
    if is_superadmin(ctx.db, user) and not is_superadmin(ctx.db, ctx.usuario):
        raise Conflito("Só um Superadmin pode renomear outro Superadmin.")
    _regra(validar_nome, ctx.db, r["antes"], user.id)
    renomear_usuario(ctx.db, user, r["antes"])
    ctx.registrar(None, user.nome, "usuario_renomeado", alvo_tipo="usuario", alvo_id=user.id,
                  valor_antigo=r["depois"], valor_novo=r["antes"],
                  reversao={"user_id": user.id, "antes": r["depois"], "depois": r["antes"]})


def _desfazer_email(ctx):
    from routers.emails import trocar_email, validar_email
    r = ctx.r
    user = ctx.db.query(UserDB).filter(UserDB.id == r["user_id"]).first()
    if user is None:
        raise Conflito("Este usuário não existe mais (está na lixeira?).")
    quem = ctx.por_quem(alvo_id=user.id, filtro=lambda l: l.acao == "email_alterado")
    if quem or user.email != r["depois"]:
        raise Conflito(f"O e-mail de {user.nome} foi alterado de novo depois{quem}.")
    if is_superadmin(ctx.db, user) and not is_superadmin(ctx.db, ctx.usuario):
        raise Conflito("Só um Superadmin pode alterar o e-mail de outro Superadmin.")
    antes = _regra(validar_email, ctx.db, r["antes"], user.id) if r["antes"] else None
    trocar_email(ctx.db, user, antes, ctx.usuario, detalhe=f"desfez: {ctx.log.usuario} em {_fmt(ctx.log.data)}")


def _desfazer_config_emails(ctx):
    import notificacoes
    r = ctx.r
    quem = ctx.por_quem(alvo_id=notificacoes.CHAVE_MODOS, filtro=lambda l: l.acao == "config_emails_alterada")
    if quem or notificacoes.modos(ctx.db) != r["depois"]:
        raise Conflito(f"A configuração dos e-mails foi alterada de novo depois{quem}.")
    notificacoes.gravar_modos(ctx.db, r["antes"])
    ctx.registrar(None, "E-mails automáticos", "config_emails_alterada", alvo_tipo="config",
                  alvo_id=notificacoes.CHAVE_MODOS, reversao={"antes": r["depois"], "depois": r["antes"]})


def _desfazer_exclusao_usuario(ctx):
    item = _da_lixeira(ctx)
    _checar_superadmin(ctx, item.dados.get("cargos") or [])
    user, faltou_cargo = recuperar_usuario(ctx.db, item.dados)
    ctx.db.delete(item)
    ctx.mensagem = "Usuário recuperado." + (" Algum cargo dele foi excluído e não voltou." if faltou_cargo else "")
    ctx.registrar(None, user.nome, "usuario_restaurado", alvo_tipo="usuario", alvo_id=user.id,
                  reversao={"user_id": user.id, "senha_versao": user.senha_versao})


def _desfazer_cargos_do_usuario(ctx):
    r = ctx.r
    user = ctx.db.query(UserDB).filter(UserDB.id == r["user_id"]).first()
    if user is None:
        raise Conflito("Este usuário não existe mais.")
    atual = sorted(v.role_id for v in ctx.db.query(UserRoleDB).filter(UserRoleDB.user_id == user.id).all())
    quem = ctx.por_quem(alvo_id=user.id, filtro=lambda l: l.acao == "cargos_do_usuario_alterados")
    if quem or atual != sorted(r["depois"]):
        raise Conflito(f"Os cargos de {user.nome} foram alterados de novo depois{quem}.")
    existentes = {x.id: x.nome for x in ctx.db.query(RoleDB).all()}
    faltando = [rid for rid in r["antes"] if rid not in existentes]
    if faltando:
        raise Conflito("Um dos cargos de antes foi excluído — recupere-o primeiro.")
    _regra(checar_atribuicao, ctx.db, ctx.usuario, user.id, set(r["antes"]))
    _regra(validar_troca_de_cargos, ctx.db, ctx.usuario, user.id, set(r["antes"]))
    ctx.db.query(UserRoleDB).filter(UserRoleDB.user_id == user.id).delete()
    for rid in r["antes"]:
        ctx.db.add(UserRoleDB(user_id=user.id, role_id=rid))
    ctx.registrar(None, user.nome, "cargos_do_usuario_alterados", alvo_tipo="usuario", alvo_id=user.id,
                  valor_antigo=", ".join(existentes[i] for i in atual) or None,
                  valor_novo=", ".join(existentes[i] for i in sorted(r["antes"])) or None,
                  reversao={"user_id": user.id, "antes": atual, "depois": sorted(r["antes"])})


def _desfazer_existencia_cargo(ctx):
    role = ctx.db.query(RoleDB).filter(RoleDB.id == ctx.r.get("role_id")).first()
    if role is None:
        raise Conflito("Este cargo já não existe mais.")
    if role.protegido:
        raise Conflito("O cargo protegido não pode ser removido.")
    _regra(checar_cargo_proprio, ctx.db, ctx.usuario, role.id)
    _regra(checar_concessao, ctx.db, ctx.usuario, {}, role.permissoes)
    titulares = sorted(v.user_id for v in ctx.db.query(UserRoleDB).filter(UserRoleDB.role_id == role.id).all())
    esperados = sorted(ctx.r.get("usuarios") or [])
    if titulares != esperados:
        raise Conflito(f"O cargo foi atribuído ou retirado de alguém depois ({len(titulares)} pessoa(s) com ele agora).")
    posteriores = [l for l in ctx.posteriores(alvo_id=role.id) if l.acao == "cargo_alterado"]
    if posteriores:
        raise Conflito(f"O cargo foi alterado depois — por {posteriores[0].usuario} em {_fmt(posteriores[0].data)}.")
    lixeira_id = excluir_cargo(ctx.db, role, ctx.nome)
    ctx.mensagem = "O cargo foi para a lixeira."
    ctx.registrar(None, role.nome, "cargo_excluido", alvo_tipo="cargo", alvo_id=role.id,
                  lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})


def _desfazer_alteracao_cargo(ctx):
    r = ctx.r
    role = ctx.db.query(RoleDB).filter(RoleDB.id == r["role_id"]).first()
    if role is None:
        raise Conflito("Este cargo não existe mais (está na lixeira?).")
    quem = ctx.por_quem(alvo_id=role.id, filtro=lambda l: l.acao == "cargo_alterado")
    if quem or cargo_de(role) != r["depois"]:
        raise Conflito(f"O cargo foi alterado de novo depois{quem}.")
    _regra(checar_cargo_proprio, ctx.db, ctx.usuario, role.id)
    _regra(checar_concessao, ctx.db, ctx.usuario, r["antes"]["permissoes"], role.permissoes)
    _regra(checar_colunas, ctx.db, ctx.usuario, r["antes"]["colunas_visiveis"])
    if r["antes"]["nome"] != role.nome and ctx.db.query(RoleDB).filter(RoleDB.nome == r["antes"]["nome"]).first():
        raise Conflito(f'Já existe outro cargo chamado "{r["antes"]["nome"]}".')
    atual = cargo_de(role)
    for campo, valor in r["antes"].items():
        setattr(role, campo, valor)
    ctx.registrar(None, role.nome, "cargo_alterado", alvo_tipo="cargo", alvo_id=role.id,
                  reversao={"role_id": role.id, "antes": atual, "depois": r["antes"]})


def _desfazer_exclusao_cargo(ctx):
    item = _da_lixeira(ctx)
    cargo = item.dados["cargo"]
    _regra(checar_concessao, ctx.db, ctx.usuario, cargo.get("permissoes"))
    _regra(checar_colunas, ctx.db, ctx.usuario, cargo.get("colunas_visiveis"))
    role, usuarios = recuperar_cargo(ctx.db, item.dados)
    ctx.db.delete(item)
    ctx.mensagem = f"Cargo recuperado e devolvido a {len(usuarios)} pessoa(s)."
    ctx.registrar(None, role.nome, "cargo_restaurado", alvo_tipo="cargo", alvo_id=role.id,
                  reversao={"role_id": role.id, "usuarios": usuarios})


# ------------------------------------------------------------ colunas

def _coluna(ctx):
    col = ctx.db.query(ColumnDB).filter(ColumnDB.id == ctx.r.get("col_id")).first()
    if col is None:
        raise Conflito("Esta coluna não existe mais.")
    return col


def _desfazer_criacao_coluna(ctx):
    col = _coluna(ctx)
    if ctx.db.query(CardDB).filter(CardDB.status == col.id).count():
        raise Conflito("A coluna já tem cards — mova-os antes de desfazer a criação.")
    quem = ctx.por_quem(alvo_id=col.id)
    if quem or coluna_de(col) != ctx.r["depois"]:
        raise Conflito(f"A coluna foi alterada depois de criada{quem}.")
    antes = coluna_de(col)
    col.arquivado = True
    ctx.mensagem = "A coluna foi arquivada."
    ctx.registrar(None, col.titulo, "coluna_arquivada", alvo_tipo="coluna", alvo_id=col.id,
                  reversao={"col_id": col.id, "antes": antes, "depois": coluna_de(col)})


def _desfazer_alteracao_coluna(ctx):
    col = _coluna(ctx)
    quem = ctx.por_quem(alvo_id=col.id)
    if quem or coluna_de(col) != ctx.r["depois"]:
        raise Conflito(f"A coluna foi alterada de novo depois{quem}.")
    atual = coluna_de(col)
    for campo, valor in ctx.r["antes"].items():
        setattr(col, campo, valor)
    acao = "coluna_arquivada" if col.arquivado and not atual["arquivado"] else "coluna_alterada"
    ctx.registrar(None, col.titulo, acao, alvo_tipo="coluna", alvo_id=col.id,
                  reversao={"col_id": col.id, "antes": atual, "depois": ctx.r["antes"]})


# ------------------------------------------------------------ tabela

TRATADORES = {
    **{acao: _desfazer_campo for acao in ACAO_DO_CAMPO},
    "responsaveis_alterados": _desfazer_responsaveis,
    "recorrencia_configurada": _desfazer_recorrencia,
    "recorrencia_desativada": _desfazer_recorrencia,
    "tarefa_recorrente_reiniciada": _desfazer_reinicio,
    "reinicio_recorrente_desfeito": _desfazer_reinicio,
    "etapa_criada": _desfazer_criacao_etapa,
    "subetapa_criada": _desfazer_criacao_etapa,
    "etapa_excluida": _desfazer_exclusao_etapa,
    "subetapa_excluida": _desfazer_exclusao_etapa,
    "etapa_editada": _desfazer_texto_etapa,
    "subetapa_editada": _desfazer_texto_etapa,
    "etapa_concluida": _desfazer_conclusao,
    "etapa_reaberta": _desfazer_conclusao,
    "subetapa_concluida": _desfazer_conclusao,
    "subetapa_reaberta": _desfazer_conclusao,
    "etapa_observacao_editada": _desfazer_observacao,
    "etapa_indentada": _desfazer_movimento,
    "etapa_desindentada": _desfazer_movimento,
    "subetapa_movida": _desfazer_movimento,
    "etapas_reordenadas": _desfazer_reordenacao,
    "comentario_adicionado": _desfazer_comentario_adicionado,
    "comentario_removido": _desfazer_comentario_removido,
    "card_criado": _desfazer_existencia_card,
    "card_restaurado": _desfazer_existencia_card,
    "card_excluido": _desfazer_exclusao_card,
    "card_fundido": _desfazer_fusao,
    "anexo_adicionado": _desfazer_existencia_linha("anexo", AttachmentDB, "anexo_removido"),
    "anexo_restaurado": _desfazer_existencia_linha("anexo", AttachmentDB, "anexo_removido"),
    "anexo_removido": _desfazer_exclusao_linha("anexo", "anexo_restaurado"),
    "tempo_restaurado": _desfazer_existencia_linha("tempo", TimeEntryDB, "tempo_apagado"),
    "tempo_apagado": _desfazer_exclusao_linha("tempo", "tempo_restaurado"),
    "nota_restaurada": _desfazer_existencia_linha("nota", UserNoteDB, "nota_excluida"),
    "nota_excluida": _desfazer_exclusao_linha("nota", "nota_restaurada"),
    "desenho_restaurado": _desfazer_existencia_linha("desenho", DrawingDB, "desenho_excluido"),
    "desenho_excluido": _desfazer_exclusao_linha("desenho", "desenho_restaurado"),
    "sugestao_criada": _desfazer_existencia_linha("sugestao", SuggestionDB, "sugestao_apagada"),
    "sugestao_restaurada": _desfazer_existencia_linha("sugestao", SuggestionDB, "sugestao_apagada"),
    "sugestao_apagada": _desfazer_exclusao_linha("sugestao", "sugestao_restaurada"),
    "sugestao_aceita": _desfazer_decisao,
    "sugestao_rejeitada": _desfazer_decisao,
    "sugestao_decisao_desfeita": _desfazer_decisao,
    "usuario_criado": _desfazer_existencia_usuario,
    "usuario_restaurado": _desfazer_existencia_usuario,
    "usuario_excluido": _desfazer_exclusao_usuario,
    "usuario_renomeado": _desfazer_renomeacao,
    "email_alterado": _desfazer_email,
    "config_emails_alterada": _desfazer_config_emails,
    "cargos_do_usuario_alterados": _desfazer_cargos_do_usuario,
    "cargo_criado": _desfazer_existencia_cargo,
    "cargo_restaurado": _desfazer_existencia_cargo,
    "cargo_alterado": _desfazer_alteracao_cargo,
    "cargo_excluido": _desfazer_exclusao_cargo,
    "coluna_criada": _desfazer_criacao_coluna,
    "coluna_alterada": _desfazer_alteracao_coluna,
    "coluna_arquivada": _desfazer_alteracao_coluna,
}

# Funcionam mesmo em registros de antes desta função (sem `reversao`): os
# valores do próprio log bastam.
SEM_REVERSAO_OK = set(ACAO_DO_CAMPO) | {"responsaveis_alterados", "card_criado"}

EXCLUSOES = {acao for acao in TRATADORES if acao.endswith(("_excluido", "_excluida", "_removido", "_apagada", "_apagado"))}


def disponibilidade(log, agora=None, lixeira_viva=None):
    """None = registro só informativo (sem botão). "" = pode desfazer.
    Texto = por que não dá mais. `lixeira_viva` (ids ainda na lixeira), quando
    passado, já marca exclusões cujo item foi recuperado por outro caminho."""
    if log.acao not in TRATADORES:
        return None
    if log.revertido_em:
        return f"Desfeito por {log.revertido_por} em {_fmt(log.revertido_em)}"
    agora = agora or datetime.now()
    try:
        if datetime.fromisoformat(log.data) < agora - timedelta(days=PRAZO_DIAS):
            return f"Passou do prazo de {PRAZO_DIAS} dias"
    except (TypeError, ValueError):
        return "Data do registro inválida"
    if not log.reversao and log.acao not in SEM_REVERSAO_OK:
        return "Registro de antes desta função — não guardou o necessário para desfazer"
    lixeira_id = (log.reversao or {}).get("lixeira_id")
    if lixeira_viva is not None and lixeira_id and lixeira_id not in lixeira_viva:
        return "Já recuperado ou fora da lixeira"
    if log.card_id and log.alvo_tipo is None and log.alvo_id and log.alvo_id != log.card_id:
        # A fusão trouxe este registro de outro card (alvo_id guarda qual):
        # desfazer aqui aplicaria o histórico daquele card neste.
        return "Veio de um card fundido neste — desfaça a fusão primeiro"
    return ""


# Desfazer em usuário, cargo e coluna mexe em administração: além de
# restaurar_alteracoes, exige a permissão de administrar aquilo.
PERMISSAO_POR_ALVO = {"usuario": "gerenciar_usuarios", "cargo": "gerenciar_cargos", "coluna": "gerenciar_colunas",
                      "config": "configurar_emails"}


def permissao_extra(log):
    if log.acao == "cargos_do_usuario_alterados":
        return "gerenciar_cargos"
    if log.acao == "email_alterado":
        # Mesma exigência de alterar o e-mail de outra pessoa.
        return "trocar_senha_outros"
    return PERMISSAO_POR_ALVO.get(log.alvo_tipo)


def desfazer(db, log, usuario):
    """Desfaz `log` em nome de `usuario`. Levanta Conflito se não der. Não faz commit."""
    motivo = disponibilidade(log)
    if motivo is None:
        raise Conflito("Este registro é só informativo — não há o que desfazer.")
    if motivo:
        raise Conflito(motivo)
    extra = permissao_extra(log)
    if extra and extra not in get_user_permissions(db, usuario.id):
        raise Conflito(f'Desfazer isto exige também a permissão "{PERMISSIONS[extra]}".')
    if log.card_id and log.alvo_tipo is None:
        # Fusões de antes desta função não marcavam os registros que trouxeram
        # de outro card — na dúvida, nada anterior a uma delas é desfeito aqui.
        fusao_antiga = db.query(AuditLogDB).filter(
            AuditLogDB.card_id == log.card_id, AuditLogDB.acao == "card_fundido",
            AuditLogDB.data > log.data, AuditLogDB.reversao == None).first()  # noqa: E711
        if fusao_antiga:
            raise Conflito("Este card recebeu uma fusão depois deste registro — não dá para desfazer com segurança.")
    ctx = _Ctx(db, log, usuario)
    try:
        TRATADORES[log.acao](ctx)
    except RecuperacaoImpossivel as e:
        raise Conflito(str(e))
    log.revertido_em = datetime.now().isoformat()
    log.revertido_por = usuario.nome
    return ctx.mensagem
