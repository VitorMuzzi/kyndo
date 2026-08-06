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


def test_new_card_has_no_badge_until_edited(client, maria, joao):
    # The badge counts unseen EDITS — a brand-new card with zero edits shows no badge.
    card = _create_card(client, maria["token"], maria["nome"])
    assert _get_card(client, maria["token"], card["id"])["nao_visto"] is False
    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is False


def test_edit_notifies_others_and_seen_clears_badge(client, maria, joao):
    card = _create_card(client, maria["token"], maria["nome"])
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))

    r = client.put(
        f"/cards/{card['id']}",
        json={"titulo": "Editado", "status": "col-1", "autor": maria["nome"]},
        headers=auth(maria["token"]),
    )
    assert r.status_code == 200

    assert _get_card(client, maria["token"], card["id"])["nao_visto"] is False
    joao_view = _get_card(client, joao["token"], card["id"])
    assert joao_view["nao_visto"] is True
    assert joao_view["alteracoes_nao_vistas"] == 1

    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))
    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is False


def test_reorder_requires_admin(client, maria):
    r = client.put(
        "/cards/reorder",
        json=[{"id": "card-qualquer", "ordem": 0}],
        headers=auth(maria["token"]),
    )
    assert r.status_code == 403
