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


def _diff_subetapas(db, card_id, titulo, item_texto, old_subs, new_subs, usuario):
    old_by_id = {s["id"]: s for s in (old_subs or []) if isinstance(s, dict) and "id" in s}
    new_by_id = {s["id"]: s for s in (new_subs or []) if isinstance(s, dict) and "id" in s}
    meaningful = False
    for sid, s in new_by_id.items():
        old = old_by_id.get(sid)
        if old is None:
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
            # Deleting a sub-step doesn't count toward the home-screen badge — logged only.
            _mk_log(db, card_id, titulo, usuario, "subetapa_excluida", detalhe=f"{item_texto} > {old.get('texto')}")
    return meaningful


def diff_checklist(db, card_id, titulo, old_checklist, new_checklist, usuario):
    old_by_id = {i["id"]: i for i in (old_checklist or []) if isinstance(i, dict) and "id" in i}
    new_ids = {i["id"] for i in new_checklist}
    meaningful = False
    for item in new_checklist:
        old = old_by_id.get(item["id"])
        if old is None:
            _mk_log(db, card_id, titulo, usuario, "etapa_criada", detalhe=item.get("texto"))
            meaningful = True
            continue
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
        if _diff_subetapas(db, card_id, titulo, item.get("texto"), old.get("subetapas"), item.get("subetapas"), usuario):
            meaningful = True
    for iid, old in old_by_id.items():
        if iid not in new_ids:
            # Deleting a step doesn't count toward the home-screen badge — logged only.
            n_subs = len(old.get("subetapas") or [])
            detalhe = old.get("texto") or ""
            if n_subs:
                detalhe += f" (incluía {n_subs} sub-etapa{'s' if n_subs != 1 else ''})"
            _mk_log(db, card_id, titulo, usuario, "etapa_excluida", detalhe=detalhe)
    return meaningful


def diff_comentarios(db, card_id, titulo, old_comentarios, new_comentarios, usuario):
    old_ids = {c["id"] for c in (old_comentarios or []) if isinstance(c, dict) and "id" in c}
    meaningful = False
    for c in new_comentarios or []:
        if isinstance(c, dict) and c.get("id") not in old_ids:
            _mk_log(db, card_id, titulo, usuario, "comentario_adicionado", detalhe=c.get("texto"))
            meaningful = True
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
