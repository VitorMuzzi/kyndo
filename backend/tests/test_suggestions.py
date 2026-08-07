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


def _create_suggestion(client, token, card_id, **overrides):
    payload = {"texto": "Sugestão de teste", "identificacao": "Fulano da Silva", **overrides}
    r = client.post(f"/cards/{card_id}/suggestions", json=payload, headers=auth(token))
    return r


def _list_suggestions(client, token, card_id):
    r = client.get(f"/cards/{card_id}/suggestions", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _decide(client, token, card_id, suggestion_id, status, **overrides):
    body = {"status": status}
    if status == "aceita":
        body["prazo_entrega"] = overrides.pop("prazo_entrega", "2026-01-01")
    elif status == "rejeitada":
        body["motivo_recusa"] = overrides.pop("motivo_recusa", "Não se aplica")
    body.update(overrides)
    return client.patch(f"/cards/{card_id}/suggestions/{suggestion_id}", json=body, headers=auth(token))


def _audit_log(client, token, card_id=None):
    url = "/audit-log" + (f"?card_id={card_id}" if card_id else "")
    r = client.get(url, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_create_suggestion_as_common_user(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    r = _create_suggestion(client, maria["token"], card["id"], texto="Podíamos mudar o prazo", identificacao="Zé")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pendente"
    assert r.json()["autor"] == maria["nome"]
    assert r.json()["identificacao"] == "Zé"

    sugestoes = _list_suggestions(client, maria["token"], card["id"])
    assert len(sugestoes) == 1
    assert sugestoes[0]["status"] == "pendente"


def test_create_suggestion_requires_identificacao(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")

    r_missing = client.post(
        f"/cards/{card['id']}/suggestions", json={"texto": "Sem identificação"}, headers=auth(maria["token"]),
    )
    assert r_missing.status_code == 422

    r_blank = client.post(
        f"/cards/{card['id']}/suggestions", json={"texto": "Identificação em branco", "identificacao": "   "},
        headers=auth(maria["token"]),
    )
    assert r_blank.status_code == 400


def test_decide_requires_admin(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(client, maria["token"], card["id"]).json()

    r = _decide(client, maria["token"], card["id"], sug["id"], "aceita")
    assert r.status_code == 403

    r2 = _decide(client, admin_token, card["id"], sug["id"], "aceita")
    assert r2.status_code == 200


def test_accept_suggestion_applies_structured_field(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(
        client, maria["token"], card["id"],
        texto="Isso é urgente", campo_alvo="prioridade", valor_proposto="Alta",
    ).json()

    r = _decide(client, admin_token, card["id"], sug["id"], "aceita")
    assert r.status_code == 200

    updated = _get_card(client, admin_token, card["id"])
    assert updated["prioridade"] == "Alta"

    decided = _list_suggestions(client, admin_token, card["id"])[0]
    assert decided["status"] == "aceita"
    assert decided["decidido_por"] == "admin"

    logs = _audit_log(client, admin_token, card["id"])
    assert any(l["acao"] == "prioridade_alterada" and l["valor_novo"] == "Alta" for l in logs)
    assert any(l["acao"] == "sugestao_aceita" for l in logs)


def test_accept_suggestion_targeting_etapa(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    step = {"id": "sug-step-1", "texto": "Texto original", "concluido": False, "criador": "admin"}
    card = _put_card(client, admin_token, card, checklist=[step])

    sug = _create_suggestion(
        client, maria["token"], card["id"],
        texto="Trocar o texto da etapa", campo_alvo="etapa:sug-step-1", valor_proposto="Texto novo",
    ).json()
    r = _decide(client, admin_token, card["id"], sug["id"], "aceita")
    assert r.status_code == 200

    updated = _get_card(client, admin_token, card["id"])
    item = next(i for i in updated["checklist"] if i["id"] == "sug-step-1")
    assert item["texto"] == "Texto novo"


def test_reject_pure_idea_suggestion_does_not_touch_card(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(client, maria["token"], card["id"], texto="Só uma ideia solta").json()

    r = _decide(client, admin_token, card["id"], sug["id"], "rejeitada")
    assert r.status_code == 200

    decided = _list_suggestions(client, admin_token, card["id"])[0]
    assert decided["status"] == "rejeitada"

    logs = _audit_log(client, admin_token, card["id"])
    assert any(l["acao"] == "sugestao_rejeitada" for l in logs)
    assert not any(l["acao"] in ("titulo_alterado", "descricao_alterada", "prioridade_alterada", "prazo_alterado", "github_url_alterado") for l in logs)


def test_create_suggestion_badges_others_not_author(client, admin_token, maria, joao):
    card = _create_card(client, admin_token, "admin")
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))

    _create_suggestion(client, maria["token"], card["id"])

    assert _get_card(client, maria["token"], card["id"])["nao_visto"] is False
    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is True


def test_accept_suggestion_with_deleted_etapa_target(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    step = {"id": "sug-step-del", "texto": "Etapa que vai sumir", "concluido": False, "criador": "admin"}
    card = _put_card(client, admin_token, card, checklist=[step])

    sug = _create_suggestion(
        client, maria["token"], card["id"],
        texto="Trocar texto", campo_alvo="etapa:sug-step-del", valor_proposto="Novo texto",
    ).json()

    # the etapa is deleted before the suggestion gets decided
    _put_card(client, admin_token, card, checklist=[])

    before = _get_card(client, admin_token, card["id"])["alteracoes_nao_vistas"]
    r = _decide(client, admin_token, card["id"], sug["id"], "aceita")
    assert r.status_code == 200

    logs = _audit_log(client, admin_token, card["id"])
    assert any(l["acao"] == "sugestao_aceita_sem_aplicar" for l in logs)


def test_decision_can_be_changed_afterwards(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(client, maria["token"], card["id"]).json()

    r1 = _decide(client, admin_token, card["id"], sug["id"], "aceita")
    assert r1.status_code == 200
    r2 = _decide(client, admin_token, card["id"], sug["id"], "rejeitada", motivo_recusa="Mudei de ideia")
    assert r2.status_code == 200

    decided = _list_suggestions(client, admin_token, card["id"])[0]
    assert decided["status"] == "rejeitada"
    assert decided["motivo_recusa"] == "Mudei de ideia"
    assert decided["prazo_entrega"] is None


def test_reverting_accepted_field_change_restores_old_value(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(
        client, maria["token"], card["id"],
        texto="Isso é urgente", campo_alvo="prioridade", valor_proposto="Alta",
    ).json()

    r1 = _decide(client, admin_token, card["id"], sug["id"], "aceita")
    assert r1.status_code == 200
    assert _get_card(client, admin_token, card["id"])["prioridade"] == "Alta"

    r2 = _decide(client, admin_token, card["id"], sug["id"], "rejeitada", motivo_recusa="Não era o caso")
    assert r2.status_code == 200
    assert _get_card(client, admin_token, card["id"])["prioridade"] == "Normal"


def test_delete_suggestion_reverts_applied_field_and_requires_permission(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(
        client, maria["token"], card["id"],
        texto="Isso é urgente", campo_alvo="prioridade", valor_proposto="Alta",
    ).json()
    _decide(client, admin_token, card["id"], sug["id"], "aceita")

    r_forbidden = client.delete(f"/cards/{card['id']}/suggestions/{sug['id']}", headers=auth(maria["token"]))
    assert r_forbidden.status_code == 403

    r = client.delete(f"/cards/{card['id']}/suggestions/{sug['id']}", headers=auth(admin_token))
    assert r.status_code == 200
    assert _get_card(client, admin_token, card["id"])["prioridade"] == "Normal"
    assert _list_suggestions(client, admin_token, card["id"]) == []


def test_invalid_prioridade_value_rejected(client, maria):
    card_owner_token = maria["token"]
    r = client.post("/cards", json={"titulo": "X", "status": "col-1", "autor": maria["nome"]}, headers=auth(card_owner_token))
    card = r.json()
    r2 = _create_suggestion(client, maria["token"], card["id"], campo_alvo="prioridade", valor_proposto="Muito Urgente")
    assert r2.status_code == 400


def test_status_field_not_allowed_as_suggestion_target(client, maria):
    r = client.post("/cards", json={"titulo": "X", "status": "col-1", "autor": maria["nome"]}, headers=auth(maria["token"]))
    card = r.json()
    r2 = _create_suggestion(client, maria["token"], card["id"], campo_alvo="status", valor_proposto="col-2")
    assert r2.status_code == 400


def test_accept_without_prazo_entrega_rejected(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(client, maria["token"], card["id"]).json()
    r = client.patch(
        f"/cards/{card['id']}/suggestions/{sug['id']}", json={"status": "aceita"}, headers=auth(admin_token),
    )
    assert r.status_code == 400


def test_reject_without_motivo_recusa_rejected(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(client, maria["token"], card["id"]).json()
    r = client.patch(
        f"/cards/{card['id']}/suggestions/{sug['id']}", json={"status": "rejeitada"}, headers=auth(admin_token),
    )
    assert r.status_code == 400


def test_decision_fields_are_persisted(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = _create_suggestion(client, maria["token"], card["id"]).json()
    r = _decide(client, admin_token, card["id"], sug["id"], "aceita", prazo_entrega="2026-03-10")
    assert r.status_code == 200

    decided = _list_suggestions(client, admin_token, card["id"])[0]
    assert decided["prazo_entrega"] == "2026-03-10"
    assert decided["motivo_recusa"] is None
