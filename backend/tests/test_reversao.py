"""Lixeira de 30 dias e desfazer pela auditoria."""
import io
import os
from datetime import datetime, timedelta

from attachment_storage import caminho_do_anexo
from database import SessionLocal
from lixeira import purgar_lixeira
from models import AttachmentDB, AuditLogDB, LixeiraDB, TimeEntryDB
from tests.conftest import auth, create_user


def _create_card(client, token, **overrides):
    payload = {"titulo": "Card reversao", "status": "col-1", "autor": "admin", **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _get_card(client, token, card_id):
    r = client.get("/cards", headers=auth(token))
    assert r.status_code == 200
    return next((c for c in r.json() if c["id"] == card_id), None)


def _put(client, token, card_id, **overrides):
    card = _get_card(client, token, card_id)
    payload = {
        "titulo": card["titulo"], "descricao": card.get("descricao") or "",
        "status": card["status"], "prioridade": card.get("prioridade") or "Normal",
        "autor": card["autor"], "prazo": card.get("prazo") or "",
        "checklist": card.get("checklist") or [], "comentarios": card.get("comentarios") or [],
        "responsaveis": card.get("responsaveis") or [], "github_url": card.get("github_url") or "",
        "ordem": card.get("ordem", 0),
    }
    payload.update(overrides)
    r = client.put(f"/cards/{card_id}", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text


def _logs(client, token, card_id=None, acao=None):
    url = "/audit-log" + (f"?card_id={card_id}" if card_id else "")
    r = client.get(url, headers=auth(token))
    assert r.status_code == 200, r.text
    return [l for l in r.json() if acao is None or l["acao"] == acao]


def _ultimo(client, token, acao, card_id=None):
    return _logs(client, token, card_id, acao)[0]


def _desfazer(client, token, log_id):
    return client.post(f"/audit-log/{log_id}/desfazer", headers=auth(token))


def _etapa(iid, texto, subetapas=None, concluido=False):
    return {"id": iid, "texto": texto, "concluido": concluido, "subetapas": subetapas or []}


# ------------------------------------------------------------- card inteiro

def test_deleted_card_comes_back_with_time_and_attachments(client, admin_token):
    card = _create_card(client, admin_token, titulo="Volta inteiro")
    up = client.post(f"/cards/{card['id']}/attachments", files={"file": ("a.txt", io.BytesIO(b"oi"), "text/plain")},
                     headers=auth(admin_token))
    assert up.status_code == 200, up.text
    client.post(f"/cards/{card['id']}/tempo/iniciar", json={"item_id": None}, headers=auth(admin_token))

    assert client.delete(f"/cards/{card['id']}", headers=auth(admin_token)).status_code == 200
    assert _get_card(client, admin_token, card["id"]) is None
    # Cronômetro que rodava no card parou junto — não volta "rodando".
    assert client.get("/tempo/atual", headers=auth(admin_token)).json() is None

    log = _ultimo(client, admin_token, "card_excluido", card["id"])
    assert log["pode_desfazer"] is True and log["eh_exclusao"] is True
    r = _desfazer(client, admin_token, log["id"])
    assert r.status_code == 200, r.text

    assert _get_card(client, admin_token, card["id"])["titulo"] == "Volta inteiro"
    anexos = client.get(f"/cards/{card['id']}/attachments", headers=auth(admin_token)).json()
    assert len(anexos) == 1
    assert client.get(f"/attachments/{anexos[0]['id']}/download", headers=auth(admin_token)).content == b"oi"
    tempo = client.get(f"/cards/{card['id']}/tempo", headers=auth(admin_token)).json()
    assert len(tempo["registros"]) == 1 and tempo["registros"][0]["fim"] is not None
    assert client.get("/tempo/atual", headers=auth(admin_token)).json() is None

    # O registro original fica marcado e não dá pra desfazer duas vezes.
    log = next(l for l in _logs(client, admin_token, card["id"]) if l["id"] == log["id"])
    assert log["revertido_por"] == "admin" and log["pode_desfazer"] is False
    assert _desfazer(client, admin_token, log["id"]).status_code == 409


def test_undo_card_creation_blocked_after_later_changes(client, admin_token):
    card = _create_card(client, admin_token, titulo="Criado e mexido")
    _put(client, admin_token, card["id"], prazo="2030-01-01")
    criado = _ultimo(client, admin_token, "card_criado", card["id"])
    r = _desfazer(client, admin_token, criado["id"])
    assert r.status_code == 409
    assert "alteração" in r.json()["detail"]
    assert _get_card(client, admin_token, card["id"]) is not None


# ------------------------------------------------------------- campos

def test_field_undo_and_redo(client, admin_token):
    card = _create_card(client, admin_token, titulo="Antes")
    _put(client, admin_token, card["id"], titulo="Depois")
    log = _ultimo(client, admin_token, "titulo_alterado", card["id"])
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    assert _get_card(client, admin_token, card["id"])["titulo"] == "Antes"

    # O próprio desfazer entra no log e pode ser desfeito (refazer).
    refazer = _ultimo(client, admin_token, "titulo_alterado", card["id"])
    assert refazer["id"] != log["id"] and refazer["pode_desfazer"] is True
    assert _desfazer(client, admin_token, refazer["id"]).status_code == 200
    assert _get_card(client, admin_token, card["id"])["titulo"] == "Depois"


def test_field_undo_never_overwrites_a_later_change(client, admin_token):
    card = _create_card(client, admin_token, prioridade="Normal")
    _put(client, admin_token, card["id"], prioridade="Alta")
    primeira = _ultimo(client, admin_token, "prioridade_alterada", card["id"])
    _put(client, admin_token, card["id"], prioridade="Urgente")

    r = _desfazer(client, admin_token, primeira["id"])
    assert r.status_code == 409
    assert "admin" in r.json()["detail"]  # diz quem mexeu depois
    assert _get_card(client, admin_token, card["id"])["prioridade"] == "Urgente"


# ------------------------------------------------------------- etapas

def test_deleted_step_returns_to_its_place_without_touching_later_steps(client, admin_token):
    card = _create_card(client, admin_token, checklist=[_etapa("e1", "um"), _etapa("e2", "dois"), _etapa("e3", "tres")])
    atual = _get_card(client, admin_token, card["id"])["checklist"]
    _put(client, admin_token, card["id"], checklist=[atual[0], atual[2]])
    excluida = _ultimo(client, admin_token, "etapa_excluida", card["id"])
    # Depois da exclusão, alguém cria outra etapa e conclui a primeira.
    atual = _get_card(client, admin_token, card["id"])["checklist"]
    atual[0]["concluido"] = True
    _put(client, admin_token, card["id"], checklist=atual + [_etapa("e4", "quatro")])

    assert _desfazer(client, admin_token, excluida["id"]).status_code == 200
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    assert [i["id"] for i in cl] == ["e1", "e2", "e3", "e4"]
    assert cl[0]["concluido"] is True  # o que mudou depois continua lá


def test_subetapa_needs_parent_back_first(client, admin_token):
    card = _create_card(client, admin_token, checklist=[_etapa("p1", "mae", [{"id": "s1", "texto": "filha", "concluido": False}])])
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    cl[0]["subetapas"] = []
    _put(client, admin_token, card["id"], checklist=cl)
    sub_excluida = _ultimo(client, admin_token, "subetapa_excluida", card["id"])
    _put(client, admin_token, card["id"], checklist=[])
    mae_excluida = _ultimo(client, admin_token, "etapa_excluida", card["id"])

    r = _desfazer(client, admin_token, sub_excluida["id"])
    assert r.status_code == 409 and "recupere-a primeiro" in r.json()["detail"]
    assert _desfazer(client, admin_token, mae_excluida["id"]).status_code == 200
    assert _desfazer(client, admin_token, sub_excluida["id"]).status_code == 200
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    assert cl[0]["id"] == "p1" and [s["id"] for s in cl[0]["subetapas"]] == ["s1"]


def test_undo_step_creation_blocked_if_step_changed(client, admin_token):
    card = _create_card(client, admin_token)
    _put(client, admin_token, card["id"], checklist=[_etapa("n1", "nova")])
    criada = _ultimo(client, admin_token, "etapa_criada", card["id"])
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    cl[0]["concluido"] = True
    _put(client, admin_token, card["id"], checklist=cl)

    assert _desfazer(client, admin_token, criada["id"]).status_code == 409
    assert len(_get_card(client, admin_token, card["id"])["checklist"]) == 1


def test_reorder_undo(client, admin_token):
    card = _create_card(client, admin_token, checklist=[_etapa("a", "A"), _etapa("b", "B"), _etapa("c", "C")])
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    _put(client, admin_token, card["id"], checklist=[cl[2], cl[0], cl[1]])
    log = _ultimo(client, admin_token, "etapas_reordenadas", card["id"])
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    assert [i["id"] for i in _get_card(client, admin_token, card["id"])["checklist"]] == ["a", "b", "c"]


def test_indent_undo(client, admin_token):
    card = _create_card(client, admin_token, checklist=[_etapa("m", "mae"), _etapa("x", "vai indentar")])
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    cl[0]["subetapas"] = [{"id": "x", "texto": "vai indentar", "concluido": False}]
    _put(client, admin_token, card["id"], checklist=[cl[0]])
    log = _ultimo(client, admin_token, "etapa_indentada", card["id"])
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    assert [i["id"] for i in cl] == ["m", "x"] and cl[0]["subetapas"] == []


# ------------------------------------------------------------- comentários

def test_removed_comment_comes_back(client, admin_token):
    card = _create_card(client, admin_token, comentarios=[{"id": "c1", "texto": "oi", "data": "hoje"}])
    _put(client, admin_token, card["id"], comentarios=[])
    log = _ultimo(client, admin_token, "comentario_removido", card["id"])
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    assert [c["id"] for c in _get_card(client, admin_token, card["id"])["comentarios"]] == ["c1"]


# ------------------------------------------------------------- fusão

def test_merge_undo_restores_both_cards(client, admin_token):
    origem = _create_card(client, admin_token, titulo="Origem fusao", checklist=[_etapa("o1", "da origem")])
    destino = _create_card(client, admin_token, titulo="Destino fusao", descricao="desc original")
    r = client.post(f"/cards/{origem['id']}/merge", json={"destino_id": destino["id"], "confirmacao": "CONFIRMO"},
                    headers=auth(admin_token))
    assert r.status_code == 200, r.text
    log = _ultimo(client, admin_token, "card_fundido", destino["id"])
    assert _desfazer(client, admin_token, log["id"]).status_code == 200

    volta = _get_card(client, admin_token, origem["id"])
    assert volta and [i["id"] for i in volta["checklist"]] == ["o1"]
    d = _get_card(client, admin_token, destino["id"])
    assert d["descricao"] == "desc original" and d["checklist"] == []


def test_merge_undo_blocked_after_destination_changed(client, admin_token):
    origem = _create_card(client, admin_token, titulo="Origem 2")
    destino = _create_card(client, admin_token, titulo="Destino 2")
    client.post(f"/cards/{origem['id']}/merge", json={"destino_id": destino["id"], "confirmacao": "CONFIRMO"},
                headers=auth(admin_token))
    log = _ultimo(client, admin_token, "card_fundido", destino["id"])
    _put(client, admin_token, destino["id"], prazo="2031-01-01")
    assert _desfazer(client, admin_token, log["id"]).status_code == 409
    assert _get_card(client, admin_token, origem["id"]) is None


# ------------------------------------------------------------- notas

def test_note_owner_recovers_from_own_trash(client, admin_token):
    dono = create_user(client, admin_token, "rev_dono_nota")
    outro = create_user(client, admin_token, "rev_outro_nota")
    nota = client.post("/notes", json={"titulo": "Segredo", "conteudo": "conteudo pessoal"}, headers=auth(dono["token"])).json()
    assert client.delete(f"/notes/{nota['id']}", headers=auth(dono["token"])).status_code == 200

    # No log aparece o título, nunca o conteúdo.
    log = next(l for l in _logs(client, admin_token, acao="nota_excluida") if l["card_titulo"] == "Segredo")
    assert "conteudo pessoal" not in str(log)

    lixeira = client.get("/lixeira?tipo=nota", headers=auth(dono["token"])).json()
    item = next(i for i in lixeira if i["titulo"] == "Segredo")
    assert client.get("/lixeira?tipo=nota", headers=auth(outro["token"])).json() == []
    assert client.post(f"/lixeira/{item['id']}/recuperar", headers=auth(outro["token"])).status_code == 404

    assert client.post(f"/lixeira/{item['id']}/recuperar", headers=auth(dono["token"])).status_code == 200
    notas = client.get("/notes", headers=auth(dono["token"])).json()
    assert any(n["id"] == nota["id"] and n["conteudo"] == "conteudo pessoal" for n in notas)
    log = next(l for l in _logs(client, admin_token, acao="nota_excluida") if l["id"] == log["id"])
    assert log["revertido_por"] == "rev_dono_nota"


# ------------------------------------------------------------- usuários e cargos

def test_deleted_user_and_role_come_back(client, admin_token):
    pessoa = create_user(client, admin_token, "rev_pessoa")
    cargo = client.post("/roles", json={"nome": "Cargo rev", "permissoes": {"editar_card": True}}, headers=auth(admin_token)).json()
    client.put(f"/users/{pessoa['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))

    assert client.delete(f"/roles/{cargo['id']}", headers=auth(admin_token)).status_code == 200
    assert client.delete(f"/users/{pessoa['id']}", headers=auth(admin_token)).status_code == 200

    # Usuário volta primeiro (sem o cargo, que ainda está na lixeira), depois o cargo volta pra ele.
    assert _desfazer(client, admin_token, _ultimo(client, admin_token, "usuario_excluido")["id"]).status_code == 200
    assert _desfazer(client, admin_token, _ultimo(client, admin_token, "cargo_excluido")["id"]).status_code == 200
    users = client.get("/users", headers=auth(admin_token)).json()
    volta = next(u for u in users if u["id"] == pessoa["id"])
    assert any(r["id"] == cargo["id"] for r in volta["roles"])
    # Sessão de antes da exclusão não volta a valer.
    assert client.get("/cards", headers=auth(pessoa["token"])).status_code == 401


def test_role_change_undo(client, admin_token):
    cargo = client.post("/roles", json={"nome": "Cargo muda", "permissoes": {}}, headers=auth(admin_token)).json()
    client.put(f"/roles/{cargo['id']}", json={"nome": "Cargo mudou", "permissoes": {"editar_card": True}}, headers=auth(admin_token))
    log = _ultimo(client, admin_token, "cargo_alterado")
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    roles = client.get("/roles", headers=auth(admin_token)).json()
    r = next(x for x in roles if x["id"] == cargo["id"])
    assert r["nome"] == "Cargo muda" and not r["permissoes"].get("editar_card")


# ------------------------------------------------------------- sugestões

def test_accepted_suggestion_undo_reverts_field(client, admin_token):
    card = _create_card(client, admin_token, titulo="Titulo velho")
    sug = client.post(f"/cards/{card['id']}/suggestions", json={
        "texto": "trocar", "campo_alvo": "titulo", "valor_proposto": "Titulo novo", "identificacao": "x"},
        headers=auth(admin_token)).json()
    client.patch(f"/cards/{card['id']}/suggestions/{sug['id']}", json={"status": "aceita", "prazo_entrega": "2030-01-01"},
                 headers=auth(admin_token))
    assert _get_card(client, admin_token, card["id"])["titulo"] == "Titulo novo"

    log = _ultimo(client, admin_token, "sugestao_aceita", card["id"])
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    assert _get_card(client, admin_token, card["id"])["titulo"] == "Titulo velho"
    sugs = client.get(f"/cards/{card['id']}/suggestions", headers=auth(admin_token)).json()
    assert sugs[0]["status"] == "pendente"


# ------------------------------------------------------------- permissões, prazo e purga

def test_undo_requires_permission(client, admin_token):
    leitor = create_user(client, admin_token, "rev_so_le")
    cargo = client.post("/roles", json={"nome": "So le log", "permissoes": {"ver_log_auditoria": True}},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{leitor['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))
    card = _create_card(client, admin_token, titulo="Perm")
    _put(client, admin_token, card["id"], titulo="Perm 2")

    log = _ultimo(client, leitor["token"], "titulo_alterado", card["id"])
    assert log["pode_desfazer"] is False
    assert _desfazer(client, leitor["token"], log["id"]).status_code == 403


def test_after_30_days_nothing_can_be_undone_and_trash_is_purged(client, admin_token):
    card = _create_card(client, admin_token, titulo="Velho")
    client.post(f"/cards/{card['id']}/attachments", files={"file": ("v.txt", io.BytesIO(b"x"), "text/plain")},
                headers=auth(admin_token))
    db = SessionLocal()
    try:
        nome_arquivo = db.query(AttachmentDB).filter(AttachmentDB.card_id == card["id"]).first().nome_arquivo
    finally:
        db.close()
    client.delete(f"/cards/{card['id']}", headers=auth(admin_token))
    log = _ultimo(client, admin_token, "card_excluido", card["id"])
    assert os.path.isfile(caminho_do_anexo(nome_arquivo))

    velho = (datetime.now() - timedelta(days=31)).isoformat()
    db = SessionLocal()
    try:
        db.query(AuditLogDB).filter(AuditLogDB.id == log["id"]).update({AuditLogDB.data: velho})
        db.query(LixeiraDB).filter(LixeiraDB.alvo_id == card["id"]).update({LixeiraDB.excluido_em: velho})
        db.commit()
        assert purgar_lixeira(db) >= 1
        assert db.query(LixeiraDB).filter(LixeiraDB.alvo_id == card["id"]).first() is None
        assert db.query(TimeEntryDB).filter(TimeEntryDB.card_id == card["id"]).first() is None
    finally:
        db.close()
    assert not os.path.isfile(caminho_do_anexo(nome_arquivo))

    log = next(l for l in _logs(client, admin_token, card["id"]) if l["id"] == log["id"])
    assert log["pode_desfazer"] is False and "30 dias" in log["motivo_indisponivel"]
    assert _desfazer(client, admin_token, log["id"]).status_code == 409


def test_column_change_undo(client, admin_token):
    col = {"id": "col-rev", "titulo": "Coluna rev", "cor": "#111111", "ordem": 99}
    assert client.post("/columns", json=col, headers=auth(admin_token)).status_code == 200
    client.put("/columns/col-rev", json={**col, "titulo": "Coluna renomeada"}, headers=auth(admin_token))
    log = _ultimo(client, admin_token, "coluna_alterada")
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    cols = client.get("/columns", headers=auth(admin_token)).json()
    assert next(c for c in cols if c["id"] == "col-rev")["titulo"] == "Coluna rev"


# ------------------------------------------------------------- regressões da revisão

def test_change_and_back_to_same_value_still_blocks_undo(client, admin_token):
    """Valor igual não basta: alguém mudou e voltou — desfazer apagaria essa decisão."""
    card = _create_card(client, admin_token, titulo="Vai e volta")
    _put(client, admin_token, card["id"], prioridade="Alta")
    primeira = _ultimo(client, admin_token, "prioridade_alterada", card["id"])
    _put(client, admin_token, card["id"], prioridade="Baixa")
    _put(client, admin_token, card["id"], prioridade="Alta")
    assert _desfazer(client, admin_token, primeira["id"]).status_code == 409
    assert _get_card(client, admin_token, card["id"])["prioridade"] == "Alta"


def test_undo_dedent_never_drops_an_observation(client, admin_token):
    card = _create_card(client, admin_token, checklist=[_etapa("p1", "Pai", [{"id": "s1", "texto": "Sub", "concluido": False}])])
    _put(client, admin_token, card["id"], checklist=[_etapa("p1", "Pai"), _etapa("s1", "Sub")])
    log = _ultimo(client, admin_token, "etapa_desindentada", card["id"])
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    next(i for i in cl if i["id"] == "s1")["notas"] = "observacao importante"
    _put(client, admin_token, card["id"], checklist=cl)

    assert _desfazer(client, admin_token, log["id"]).status_code == 409
    cl = _get_card(client, admin_token, card["id"])["checklist"]
    assert next(i for i in cl if i["id"] == "s1")["notas"] == "observacao importante"


def test_undo_card_creation_blocked_by_tracked_time(client, admin_token):
    card = _create_card(client, admin_token, titulo="Com cronometro")
    client.post(f"/cards/{card['id']}/tempo/iniciar", json={"item_id": None}, headers=auth(admin_token))
    log = _ultimo(client, admin_token, "card_criado", card["id"])
    assert _desfazer(client, admin_token, log["id"]).status_code == 409
    assert client.get("/tempo/atual", headers=auth(admin_token)).json()["card_id"] == card["id"]
    client.post("/tempo/parar", headers=auth(admin_token))


def test_logs_brought_by_a_merge_cannot_be_undone_on_the_destination(client, admin_token):
    origem = _create_card(client, admin_token, titulo="Origem log")
    destino = _create_card(client, admin_token, titulo="Destino log")
    _put(client, admin_token, origem["id"], prioridade="Alta")
    da_origem = _ultimo(client, admin_token, "prioridade_alterada", origem["id"])
    _put(client, admin_token, destino["id"], prioridade="Alta")
    client.post(f"/cards/{origem['id']}/merge", json={"destino_id": destino["id"], "confirmacao": "CONFIRMO"},
                headers=auth(admin_token))

    log = next(l for l in _logs(client, admin_token, destino["id"]) if l["id"] == da_origem["id"])
    assert log["pode_desfazer"] is False and "fusão" in log["motivo_indisponivel"]
    assert _desfazer(client, admin_token, da_origem["id"]).status_code == 409
    assert _get_card(client, admin_token, destino["id"])["prioridade"] == "Alta"


def test_undo_restore_blocked_if_note_was_edited(client, admin_token):
    dono = create_user(client, admin_token, "rev_nota_editada")
    nota = client.post("/notes", json={"titulo": "Ed", "conteudo": "v1"}, headers=auth(dono["token"])).json()
    client.delete(f"/notes/{nota['id']}", headers=auth(dono["token"]))
    item = client.get("/lixeira?tipo=nota", headers=auth(dono["token"])).json()[0]
    client.post(f"/lixeira/{item['id']}/recuperar", headers=auth(dono["token"]))
    client.put(f"/notes/{nota['id']}", json={"titulo": "Ed", "conteudo": "v2 depois de recuperar"}, headers=auth(dono["token"]))

    restaurada = next(l for l in _logs(client, admin_token, acao="nota_restaurada") if l["card_titulo"] == "Ed")
    assert _desfazer(client, admin_token, restaurada["id"]).status_code == 409
    assert any(n["id"] == nota["id"] for n in client.get("/notes", headers=auth(dono["token"])).json())


def test_admin_undo_needs_the_admin_permission_too(client, admin_token):
    so_restaura = create_user(client, admin_token, "rev_so_restaura")
    cargo = client.post("/roles", json={"nome": "So restaura", "permissoes": {
        "ver_log_auditoria": True, "restaurar_alteracoes": True}}, headers=auth(admin_token)).json()
    client.put(f"/users/{so_restaura['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))
    alvo = client.post("/roles", json={"nome": "Cargo alvo", "permissoes": {}}, headers=auth(admin_token)).json()
    client.put(f"/roles/{alvo['id']}", json={"nome": "Cargo alvo", "permissoes": {"excluir_card": True}}, headers=auth(admin_token))

    log = _ultimo(client, so_restaura["token"], "cargo_alterado")
    assert log["pode_desfazer"] is False
    r = _desfazer(client, so_restaura["token"], log["id"])
    assert r.status_code == 409 and "Criar, editar e atribuir cargos" in r.json()["detail"]
