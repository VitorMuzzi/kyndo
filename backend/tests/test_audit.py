from database import SessionLocal
from models import CardDB
from tests.conftest import auth


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card teste", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _get_card(client, token, card_id):
    r = client.get("/cards", headers=auth(token))
    assert r.status_code == 200
    return next(c for c in r.json() if c["id"] == card_id)


def _put_card(client, token, card, **overrides):
    payload = {
        "titulo": card["titulo"], "descricao": card.get("descricao") or "",
        "status": card["status"], "prioridade": card.get("prioridade") or "Normal",
        "autor": card["autor"], "prazo": card.get("prazo") or "",
        "checklist": card.get("checklist") or [], "comentarios": card.get("comentarios") or [],
        "responsaveis": card.get("responsaveis") or [], "github_url": card.get("github_url") or "",
        "ordem": card.get("ordem", 0),
    }
    payload.update(overrides)
    r = client.put(f"/cards/{card['id']}", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return {**payload, "id": card["id"]}


def _audit_log(client, token, card_id=None):
    url = "/audit-log" + (f"?card_id={card_id}" if card_id else "")
    r = client.get(url, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_title_edit_logs_and_badges(client, admin_token, maria, joao):
    card = _create_card(client, maria["token"], maria["nome"])
    _put_card(client, maria["token"], card, titulo="Novo Título")

    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is True
    logs = _audit_log(client, admin_token, card["id"])
    assert any(
        l["acao"] == "titulo_alterado" and l["valor_antigo"] == "Card teste" and l["valor_novo"] == "Novo Título"
        for l in logs
    )


def test_delete_etapa_does_not_badge_but_logs(client, admin_token, maria, joao):
    # Checklist edits require the gerenciar_etapas permission (RBAC), which
    # plain users like maria don't hold — perform these as admin_token
    # (Superadmin, has every permission) so the test isolates audit/badge
    # behavior instead of also exercising the permission gate.
    card = _create_card(client, maria["token"], maria["nome"])
    step = {"id": "sub-del-1", "texto": "Etapa 1", "concluido": False, "criador": maria["nome"]}
    card = _put_card(client, admin_token, card, checklist=[step])
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))

    card = _put_card(client, admin_token, card, checklist=[])

    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is False
    logs = _audit_log(client, admin_token, card["id"])
    assert any(l["acao"] == "etapa_excluida" for l in logs)


def test_delete_etapa_plus_title_edit_still_badges(client, admin_token, maria, joao):
    card = _create_card(client, maria["token"], maria["nome"])
    step = {"id": "sub-del-2", "texto": "Etapa X", "concluido": False, "criador": maria["nome"]}
    card = _put_card(client, maria["token"], card, checklist=[step])
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))

    _put_card(client, maria["token"], card, checklist=[], titulo="Outro Título")

    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is True


def test_noop_save_does_not_badge_or_log(client, admin_token, maria, joao):
    card = _create_card(client, maria["token"], maria["nome"])
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))
    logs_before = _audit_log(client, admin_token, card["id"])

    _put_card(client, maria["token"], card)

    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is False
    logs_after = _audit_log(client, admin_token, card["id"])
    assert len(logs_after) == len(logs_before)


def test_prazo_none_to_empty_does_not_spurious_log(client, admin_token, maria):
    card = _create_card(client, maria["token"], maria["nome"])
    db = SessionLocal()
    try:
        db_card = db.query(CardDB).filter(CardDB.id == card["id"]).first()
        db_card.prazo = None
        db_card.github_url = None
        db.commit()
    finally:
        db.close()

    logs_before = _audit_log(client, admin_token, card["id"])
    _put_card(client, maria["token"], card, prazo="", github_url="")
    logs_after = _audit_log(client, admin_token, card["id"])
    assert len(logs_after) == len(logs_before)


def test_audit_log_requires_superadmin(client, admin_token, maria):
    assert client.get("/audit-log", headers=auth(maria["token"])).status_code == 403
    assert client.get("/audit-log", headers=auth(admin_token)).status_code == 200


def test_item_seen_clears_badge_and_editor_never_sees_own(client, admin_token, maria, joao):
    # Same RBAC note as above: the checklist edit needs gerenciar_etapas, so it's
    # done as admin_token here — the "editor never sees their own badge" check
    # below is therefore about admin_token, not maria.
    card = _create_card(client, maria["token"], maria["nome"])
    step = {"id": "sub-notas-1", "texto": "Etapa com nota", "concluido": False, "criador": maria["nome"], "notas": "observação importante"}
    card = _put_card(client, admin_token, card, checklist=[step])

    joao_view = _get_card(client, joao["token"], card["id"])
    joao_item = next(i for i in joao_view["checklist"] if i["id"] == "sub-notas-1")
    assert joao_item["notas_nao_vista"] is True

    r = client.post(f"/cards/{card['id']}/items/sub-notas-1/seen", headers=auth(joao["token"]))
    assert r.status_code == 200

    joao_view2 = _get_card(client, joao["token"], card["id"])
    joao_item2 = next(i for i in joao_view2["checklist"] if i["id"] == "sub-notas-1")
    assert joao_item2["notas_nao_vista"] is False

    admin_view = _get_card(client, admin_token, card["id"])
    admin_item = next(i for i in admin_view["checklist"] if i["id"] == "sub-notas-1")
    assert admin_item["notas_nao_vista"] is False
