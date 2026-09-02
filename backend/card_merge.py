"""Fusão de cards: move tudo que pertence a um card de origem para um card de
destino e apaga a origem. Vive fora do router porque toca sete tabelas — o
endpoint em routers/cards.py fica só com a validação de entrada."""
import uuid
from datetime import datetime

from models import (
    AttachmentDB, AuditLogDB, CardDB, CardSeenDB, DrawingDB,
    ItemSeenDB, SuggestionDB, UserNoteDB,
)
from audit import _mk_log

# Palavra que o admin precisa digitar. Comparada em maiúsculas e sem espaços
# nas pontas — a fricção pretendida é ter que digitar a palavra, não acertar
# o caps lock.
CONFIRMACAO = "CONFIRMO"

SEPARADOR = "─" * 24


def confirmacao_valida(texto: str) -> bool:
    return (texto or "").strip().upper() == CONFIRMACAO


def _remap_checklist(origem_checklist, destino_checklist):
    """Reidentifica as etapas da origem que colidiriam com ids já usados no
    destino. ItemSeenDB tem chave (card_id, item_id), então dois ids iguais no
    mesmo card fundiriam silenciosamente o estado de "lido" de etapas
    diferentes. Devolve (checklist_da_origem, {id_antigo: id_novo})."""
    usados = set()
    for item in destino_checklist or []:
        if isinstance(item, dict):
            usados.add(item.get("id"))
            for s in item.get("subetapas") or []:
                if isinstance(s, dict):
                    usados.add(s.get("id"))

    remap = {}

    def _unico(old_id):
        if old_id not in usados:
            usados.add(old_id)
            return old_id
        novo = f"{old_id}-m{uuid.uuid4().hex[:6]}"
        while novo in usados:
            novo = f"{old_id}-m{uuid.uuid4().hex[:6]}"
        usados.add(novo)
        remap[old_id] = novo
        return novo

    resultado = []
    for item in origem_checklist or []:
        if not isinstance(item, dict) or "id" not in item:
            continue
        novo_item = dict(item)
        novo_item["id"] = _unico(item["id"])
        novo_item["subetapas"] = [
            {**s, "id": _unico(s["id"])}
            for s in (item.get("subetapas") or [])
            if isinstance(s, dict) and "id" in s
        ]
        resultado.append(novo_item)
    return resultado, remap


def _remap_comentarios(origem_comentarios, destino_comentarios):
    """Mesmo cuidado do checklist: diff_comentarios identifica comentário novo
    por id, então id repetido faria um comentário da origem nunca aparecer
    como novo no log."""
    usados = {c.get("id") for c in (destino_comentarios or []) if isinstance(c, dict)}
    resultado = []
    for c in origem_comentarios or []:
        if not isinstance(c, dict):
            continue
        novo = dict(c)
        if novo.get("id") in usados:
            novo["id"] = f"{novo.get('id')}-m{uuid.uuid4().hex[:6]}"
        usados.add(novo.get("id"))
        resultado.append(novo)
    return resultado


def _bloco_fusao(origem, destino, usuario, agora, herdados):
    """Bloco anexado ao fim da descrição do destino. Recebe `herdados` (campos
    que a origem preencheu por estarem vazios no destino) para não listar como
    descartado algo que na verdade foi aproveitado."""
    linhas = [
        SEPARADOR,
        f'Fundido de "{origem.titulo}" ({origem.id})',
        f'por {usuario} em {agora.strftime("%d/%m/%Y %H:%M")}',
    ]

    desc_origem = (origem.descricao or "").strip()
    if desc_origem:
        linhas += ["", desc_origem]

    descartados = []
    if "prazo" not in herdados and (origem.prazo or "").strip() and (origem.prazo or "") != (destino.prazo or ""):
        descartados.append(f"Prazo na origem: {origem.prazo}")
    if "github_url" not in herdados and (origem.github_url or "").strip() and (origem.github_url or "") != (destino.github_url or ""):
        descartados.append(f"GitHub na origem: {origem.github_url}")
    # Prioridade nunca fica vazia (o default é "Normal"), então não entra na
    # regra de "preencher vazios" — o destino manda e a divergência fica aqui.
    if (origem.prioridade or "Normal") != (destino.prioridade or "Normal"):
        descartados.append(f"Prioridade na origem: {origem.prioridade}")
    if "recorrencia" not in herdados and origem.recorrente:
        descartados.append(
            f"A origem era recorrente a cada {origem.recorrencia_dias} dia(s) — recorrência não foi transferida"
        )
    if (origem.autor or "") and origem.autor != destino.autor:
        descartados.append(f"Autor da origem: {origem.autor}")

    if descartados:
        linhas += [""] + descartados
    return "\n".join(linhas)


def fundir_cards(db, origem: CardDB, destino: CardDB, usuario: str):
    """Move todo o conteúdo da origem para o destino e apaga a origem.
    Não faz commit — quem chama decide a fronteira da transação."""
    agora = datetime.now()
    agora_iso = agora.isoformat()

    # --- campos de vaga única: destino manda, origem preenche o que está vazio
    herdados = []
    if not (destino.prazo or "").strip() and (origem.prazo or "").strip():
        destino.prazo = origem.prazo
        herdados.append("prazo")
    if not (destino.github_url or "").strip() and (origem.github_url or "").strip():
        destino.github_url = origem.github_url
        herdados.append("github_url")
    if not destino.recorrente and origem.recorrente:
        destino.recorrente = True
        destino.recorrencia_dias = origem.recorrencia_dias
        destino.recorrencia_coluna_reset = destino.status
        destino.recorrencia_proximo_reset = origem.recorrencia_proximo_reset
        herdados.append("recorrencia")

    bloco = _bloco_fusao(origem, destino, usuario, agora, herdados)
    desc_destino = (destino.descricao or "").rstrip()
    destino.descricao = f"{desc_destino}\n\n{bloco}" if desc_destino else bloco

    # --- coleções JSON do próprio card
    checklist_origem, remap = _remap_checklist(origem.checklist, destino.checklist)
    destino.checklist = list(destino.checklist or []) + checklist_origem

    comentarios_origem = _remap_comentarios(origem.comentarios, destino.comentarios)
    destino.comentarios = list(destino.comentarios or []) + comentarios_origem

    responsaveis = list(destino.responsaveis or [])
    for nome in origem.responsaveis or []:
        if nome not in responsaveis:
            responsaveis.append(nome)
    destino.responsaveis = responsaveis

    # --- tabelas que referenciam card_id
    n_anexos = db.query(AttachmentDB).filter(AttachmentDB.card_id == origem.id).update(
        {AttachmentDB.card_id: destino.id}, synchronize_session=False)
    n_sugestoes = db.query(SuggestionDB).filter(SuggestionDB.card_id == origem.id).update(
        {SuggestionDB.card_id: destino.id}, synchronize_session=False)
    n_notas = db.query(UserNoteDB).filter(UserNoteDB.card_id == origem.id).update(
        {UserNoteDB.card_id: destino.id}, synchronize_session=False)
    n_desenhos = db.query(DrawingDB).filter(DrawingDB.card_id == origem.id).update(
        {DrawingDB.card_id: destino.id}, synchronize_session=False)
    # card_titulo fica como estava de propósito: é o nome que o card tinha na
    # hora do evento, e reescrever isso falsificaria o histórico.
    n_log = db.query(AuditLogDB).filter(AuditLogDB.card_id == origem.id).update(
        {AuditLogDB.card_id: destino.id}, synchronize_session=False)

    # --- estado de "lido" por etapa acompanha a etapa (com o id já remapeado)
    for row in db.query(ItemSeenDB).filter(ItemSeenDB.card_id == origem.id).all():
        novo_item_id = remap.get(row.item_id, row.item_id)
        ja_existe = db.query(ItemSeenDB).filter(
            ItemSeenDB.card_id == destino.id,
            ItemSeenDB.item_id == novo_item_id,
            ItemSeenDB.user_id == row.user_id,
        ).first()
        if ja_existe is None:
            db.add(ItemSeenDB(card_id=destino.id, item_id=novo_item_id,
                              user_id=row.user_id, visto_versao=row.visto_versao))
        db.delete(row)

    # O "lido" do card em si não migra: a fusão é uma mudança que todo mundo
    # precisa enxergar como não vista no destino.
    db.query(CardSeenDB).filter(CardSeenDB.card_id == origem.id).delete(synchronize_session=False)

    resumo = {
        "etapas": len(checklist_origem),
        "comentarios": len(comentarios_origem),
        "anexos": n_anexos,
        "sugestoes": n_sugestoes,
        "notas": n_notas,
        "desenhos": n_desenhos,
        "eventos_log": n_log,
    }

    detalhe = (
        f"{resumo['etapas']} etapa(s), {resumo['comentarios']} comentário(s), "
        f"{resumo['anexos']} anexo(s), {resumo['sugestoes']} sugestão(ões), "
        f"{resumo['notas']} anotação(ões), {resumo['desenhos']} desenho(s)"
    )
    _mk_log(db, destino.id, destino.titulo, usuario, "card_fundido",
            valor_antigo=origem.titulo, valor_novo=destino.titulo, detalhe=detalhe)

    # A fusão conta como alteração para todo mundo, menos para quem a fez.
    destino.alteracoes = (destino.alteracoes or 0) + 1
    destino.updated_em = agora_iso

    db.delete(origem)
    return resumo
