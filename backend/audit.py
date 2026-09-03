import uuid
from datetime import datetime

from models import AuditLogDB

CHECKLIST_ITEM_FIELDS = ("id", "texto", "concluido", "criador", "concluidoPor", "notas")
SUBETAPA_FIELDS = ("id", "texto", "concluido", "criador", "concluidoPor")

SIMPLE_CARD_FIELDS = [
    ("titulo", "titulo_alterado"),
    ("descricao", "descricao_alterada"),
    ("status", "status_alterado"),
    ("prioridade", "prioridade_alterada"),
    ("prazo", "prazo_alterado"),
    ("github_url", "github_url_alterado"),
]

# Lookup form of SIMPLE_CARD_FIELDS for callers that just need `campo -> acao`
# (e.g. applying an accepted suggestion) without re-deriving the mapping.
SIMPLE_CARD_FIELDS_MAP = dict(SIMPLE_CARD_FIELDS)


def _mk_log(db, card_id, card_titulo, usuario, acao, valor_antigo=None, valor_novo=None, detalhe=None):
    db.add(AuditLogDB(
        id=f"log-{uuid.uuid4().hex[:10]}",
        card_id=card_id,
        card_titulo=card_titulo or "",
        usuario=usuario,
        acao=acao,
        valor_antigo=valor_antigo,
        valor_novo=valor_novo,
        detalhe=detalhe,
        data=datetime.now().isoformat(),
    ))


def _sanitize_subetapas(raw_subetapas):
    out = []
    for s in raw_subetapas or []:
        if isinstance(s, dict) and "id" in s:
            out.append({k: s.get(k) for k in SUBETAPA_FIELDS if k in s})
    return out


def _sanitize_item(raw_item, old_item):
    item = {k: raw_item.get(k) for k in CHECKLIST_ITEM_FIELDS if k in raw_item}
    item["subetapas"] = _sanitize_subetapas(raw_item.get("subetapas"))
    old_notas = (old_item or {}).get("notas") or ""
    new_notas = item.get("notas") or ""
    base_versao = (old_item or {}).get("notas_versao", 0) or 0
    item["notas_versao"] = base_versao + 1 if new_notas != old_notas else base_versao
    return item


def sanitize_checklist(raw_checklist, old_checklist):
    """Rebuilds each checklist item from only the known business fields —
    discards client-computed keys (e.g. notas_nao_vista) and always recomputes
    notas_versao server-side, never trusting a client-echoed value."""
    old_by_id = {i["id"]: i for i in (old_checklist or []) if isinstance(i, dict) and "id" in i}
    result = []
    for raw in raw_checklist or []:
        if isinstance(raw, dict) and "id" in raw:
            result.append(_sanitize_item(raw, old_by_id.get(raw["id"])))
    return result


def _flatten_niveis(checklist):
    """{id: (nivel, item, id_do_pai)} cobrindo os dois níveis. Serve pra
    distinguir uma etapa que foi INDENTADA (mudou de nível) de uma que foi
    realmente excluída — sem isso, reorganizar o checklist enche a auditoria
    de "etapa excluída" + "sub-etapa criada" pra algo que só mudou de lugar."""
    mapa = {}
    for item in checklist or []:
        if isinstance(item, dict) and "id" in item:
            mapa[item["id"]] = (0, item, None)
            for s in item.get("subetapas") or []:
                if isinstance(s, dict) and "id" in s:
                    mapa[s["id"]] = (1, s, item["id"])
    return mapa


def _sequencia_ids(checklist):
    """Ordem de leitura do checklist achatada — compara posição sem se
    importar com nível."""
    seq = []
    for item in checklist or []:
        if isinstance(item, dict) and "id" in item:
            seq.append(item["id"])
            for s in item.get("subetapas") or []:
                if isinstance(s, dict) and "id" in s:
                    seq.append(s["id"])
    return seq


def _diff_estrutura(db, card_id, titulo, old_flat, new_flat, old_checklist, new_checklist, usuario):
    """Registra mudanças de organização (indentar, desindentar, trocar de pai,
    reordenar) e devolve o conjunto de ids que só se MOVERAM — esses não devem
    ser logados como criados nem excluídos pelos diffs de nível.

    Nada disso conta como `meaningful`: reorganizar não é mudança de conteúdo,
    então não acende o aviso de "não visto", igual já acontece com exclusão."""
    movidos = set()
    for iid, (novo_nivel, novo_item, novo_pai) in new_flat.items():
        antigo = old_flat.get(iid)
        if antigo is None:
            continue
        antigo_nivel, antigo_item, antigo_pai = antigo
        texto = novo_item.get("texto") or antigo_item.get("texto") or ""
        if antigo_nivel != novo_nivel:
            movidos.add(iid)
            if novo_nivel == 1:
                pai = (new_flat.get(novo_pai, (None, {}, None))[1] or {}).get("texto") or ""
                _mk_log(db, card_id, titulo, usuario, "etapa_indentada",
                        detalhe=f"{texto} virou sub-etapa de {pai}")
            else:
                _mk_log(db, card_id, titulo, usuario, "etapa_desindentada",
                        detalhe=f"{texto} deixou de ser sub-etapa e virou etapa")
        elif novo_nivel == 1 and antigo_pai != novo_pai:
            movidos.add(iid)
            pai_antigo = (old_flat.get(antigo_pai, (None, {}, None))[1] or {}).get("texto") or ""
            pai_novo = (new_flat.get(novo_pai, (None, {}, None))[1] or {}).get("texto") or ""
            _mk_log(db, card_id, titulo, usuario, "subetapa_movida",
                    detalhe=f"{texto}: de {pai_antigo} para {pai_novo}")

    # Reordenação pura só é registrada quando nada mudou de nível nem de pai —
    # se mudou, os logs acima já explicam o rearranjo.
    if not movidos:
        old_seq, new_seq = _sequencia_ids(old_checklist), _sequencia_ids(new_checklist)
        if set(old_seq) == set(new_seq) and old_seq != new_seq:
            _mk_log(db, card_id, titulo, usuario, "etapas_reordenadas",
                    detalhe=f"{len(new_seq)} item(ns) reorganizado(s)")
    return movidos


def _diff_subetapas(db, card_id, titulo, item_texto, old_subs, new_subs, usuario, movidos=frozenset()):
    old_by_id = {s["id"]: s for s in (old_subs or []) if isinstance(s, dict) and "id" in s}
    new_by_id = {s["id"]: s for s in (new_subs or []) if isinstance(s, dict) and "id" in s}
    meaningful = False
    for sid, s in new_by_id.items():
        old = old_by_id.get(sid)
        if old is None:
            if sid in movidos:
                continue  # não é nova: veio de outro nível/pai, já logado em _diff_estrutura
            _mk_log(db, card_id, titulo, usuario, "subetapa_criada", detalhe=f"{item_texto} > {s.get('texto')}")
            meaningful = True
            continue
        if (old.get("texto") or "") != (s.get("texto") or ""):
            _mk_log(db, card_id, titulo, usuario, "subetapa_editada", detalhe=item_texto, valor_antigo=old.get("texto"), valor_novo=s.get("texto"))
            meaningful = True
        if bool(old.get("concluido")) != bool(s.get("concluido")):
            acao = "subetapa_concluida" if s.get("concluido") else "subetapa_reaberta"
            _mk_log(db, card_id, titulo, usuario, acao, detalhe=f"{item_texto} > {s.get('texto')}")
            meaningful = True
    for sid, old in old_by_id.items():
        if sid not in new_by_id:
            if sid in movidos:
                continue  # não foi excluída: mudou de nível/pai, já logado em _diff_estrutura
            # Deleting a sub-step doesn't count toward the home-screen badge — logged only.
            _mk_log(db, card_id, titulo, usuario, "subetapa_excluida", detalhe=f"{item_texto} > {old.get('texto')}")
    return meaningful


def diff_checklist(db, card_id, titulo, old_checklist, new_checklist, usuario):
    old_by_id = {i["id"]: i for i in (old_checklist or []) if isinstance(i, dict) and "id" in i}
    new_ids = {i["id"] for i in new_checklist}
    old_flat = _flatten_niveis(old_checklist)
    new_flat = _flatten_niveis(new_checklist)
    # Precisa vir ANTES dos diffs por nível: é o que identifica quem só mudou
    # de lugar, pra esses não serem contados como criados nem excluídos.
    movidos = _diff_estrutura(db, card_id, titulo, old_flat, new_flat, old_checklist, new_checklist, usuario)
    meaningful = False
    for item in new_checklist:
        old = old_by_id.get(item["id"])
        if old is None:
            if item["id"] not in movidos:
                _mk_log(db, card_id, titulo, usuario, "etapa_criada", detalhe=item.get("texto"))
                meaningful = True
                continue
            # Desindentada: já veio de uma sub-etapa. Segue pro diff de campos
            # abaixo comparando com o registro antigo dela no outro nível.
            old = old_flat[item["id"]][1]
        if (old.get("texto") or "") != (item.get("texto") or ""):
            _mk_log(db, card_id, titulo, usuario, "etapa_editada", detalhe=item.get("texto"), valor_antigo=old.get("texto"), valor_novo=item.get("texto"))
            meaningful = True
        if bool(old.get("concluido")) != bool(item.get("concluido")):
            acao = "etapa_concluida" if item.get("concluido") else "etapa_reaberta"
            _mk_log(db, card_id, titulo, usuario, acao, detalhe=item.get("texto"))
            meaningful = True
        if (old.get("notas") or "") != (item.get("notas") or ""):
            _mk_log(db, card_id, titulo, usuario, "etapa_observacao_editada", detalhe=item.get("texto"), valor_antigo=old.get("notas"), valor_novo=item.get("notas"))
            meaningful = True
        if _diff_subetapas(db, card_id, titulo, item.get("texto"), old.get("subetapas"), item.get("subetapas"), usuario, movidos):
            meaningful = True
    for iid, old in old_by_id.items():
        if iid not in new_ids:
            if iid in movidos:
                continue  # indentada, não excluída — já logado em _diff_estrutura
            # Deleting a step doesn't count toward the home-screen badge — logged only.
            n_subs = len(old.get("subetapas") or [])
            detalhe = old.get("texto") or ""
            if n_subs:
                detalhe += f" (incluía {n_subs} sub-etapa{'s' if n_subs != 1 else ''})"
            _mk_log(db, card_id, titulo, usuario, "etapa_excluida", detalhe=detalhe)
    return meaningful


def diff_comentarios(db, card_id, titulo, old_comentarios, new_comentarios, usuario):
    old_by_id = {c["id"]: c for c in (old_comentarios or []) if isinstance(c, dict) and "id" in c}
    new_ids = {c["id"] for c in (new_comentarios or []) if isinstance(c, dict) and "id" in c}
    meaningful = False
    for c in new_comentarios or []:
        if isinstance(c, dict) and c.get("id") not in old_by_id:
            _mk_log(db, card_id, titulo, usuario, "comentario_adicionado", detalhe=c.get("texto"))
            meaningful = True
    # Só quem tem editar_card chega aqui com comentário faltando (o router
    # reverte os demais), mas mesmo essa pessoa não pode apagar conversa sem
    # deixar rastro. Como na exclusão de etapa, é logado sem contar pro badge.
    for cid, old in old_by_id.items():
        if cid not in new_ids:
            autor = old.get("autor") or "?"
            _mk_log(db, card_id, titulo, usuario, "comentario_removido",
                    detalhe=f"de {autor}: {old.get('texto')}")
    return meaningful


def diff_card_fields(db, db_card, new, usuario, titulo_ref):
    meaningful = False
    for field, acao in SIMPLE_CARD_FIELDS:
        old_v = getattr(db_card, field) or ""
        new_v = getattr(new, field) or ""
        if old_v != new_v:
            _mk_log(db, db_card.id, titulo_ref, usuario, acao, valor_antigo=old_v or None, valor_novo=new_v or None)
            meaningful = True
    old_resp = sorted(db_card.responsaveis or [])
    new_resp = sorted(new.responsaveis or []) if new.responsaveis else old_resp
    if old_resp != new_resp:
        _mk_log(db, db_card.id, titulo_ref, usuario, "responsaveis_alterados", valor_antigo=", ".join(old_resp) or None, valor_novo=", ".join(new_resp) or None)
        meaningful = True
    return meaningful


def process_card_update(db, db_card, new, usuario):
    """Diffs the incoming payload against the stored card, logging every atomic
    change to AuditLogDB. Returns (sanitized_checklist, meaningful) where
    `meaningful` is False when the only checklist changes were deletions —
    those are logged but must not trigger the home-screen "unseen" badge."""
    titulo_ref = new.titulo or db_card.titulo
    sanitized_checklist = sanitize_checklist(new.checklist, db_card.checklist)
    meaningful = diff_card_fields(db, db_card, new, usuario, titulo_ref)
    if diff_checklist(db, db_card.id, titulo_ref, db_card.checklist, sanitized_checklist, usuario):
        meaningful = True
    if diff_comentarios(db, db_card.id, titulo_ref, db_card.comentarios, new.comentarios, usuario):
        meaningful = True
    return sanitized_checklist, meaningful


def log_card_created(db, card, usuario):
    _mk_log(db, card.id, card.titulo, usuario, "card_criado")


def log_card_deleted(db, card, usuario):
    _mk_log(db, card.id, card.titulo, usuario, "card_excluido")
