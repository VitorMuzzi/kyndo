from tests.conftest import auth


def _create_note(client, token, **overrides):
    payload = {"titulo": "Minha Nota", "conteudo": "segredo", **overrides}
    r = client.post("/notes", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _note_ids(client, token):
    r = client.get("/notes", headers=auth(token))
    assert r.status_code == 200
    return {n["id"] for n in r.json()}


def test_unshared_note_is_invisible_to_others(client, maria, joao):
    note = _create_note(client, maria["token"])
    assert note["id"] in _note_ids(client, maria["token"])
    assert note["id"] not in _note_ids(client, joao["token"])


def test_unshared_note_cannot_be_updated_by_others(client, maria, joao):
    note = _create_note(client, maria["token"])
    r = client.put(
        f"/notes/{note['id']}",
        json={"titulo": "invadida", "conteudo": "x"},
        headers=auth(joao["token"]),
    )
    assert r.status_code == 403


def test_share_ver_allows_read_but_not_edit(client, maria, joao):
    note = _create_note(
        client, maria["token"],
        compartilhado_com=[{"user_id": joao["id"], "nivel": "ver"}],
    )
    assert note["id"] in _note_ids(client, joao["token"])
    r = client.put(
        f"/notes/{note['id']}",
        json={"titulo": "editada", "conteudo": "x"},
        headers=auth(joao["token"]),
    )
    assert r.status_code == 403


def test_share_editar_allows_edit_but_not_resharing(client, maria, joao):
    share = [{"user_id": joao["id"], "nivel": "editar"}]
    note = _create_note(client, maria["token"], compartilhado_com=share)

    r = client.put(
        f"/notes/{note['id']}",
        json={"titulo": "editada por joao", "conteudo": "novo", "compartilhado_com": share},
        headers=auth(joao["token"]),
    )
    assert r.status_code == 200

    r = client.put(
        f"/notes/{note['id']}",
        json={"titulo": "x", "conteudo": "x", "publico": True, "compartilhado_com": share},
        headers=auth(joao["token"]),
    )
    assert r.status_code == 403

    r = client.put(
        f"/notes/{note['id']}",
        json={"titulo": "x", "conteudo": "x",
              "compartilhado_com": [{"user_id": joao["id"], "nivel": "editar"},
                                    {"user_id": maria["id"], "nivel": "ver"}]},
        headers=auth(joao["token"]),
    )
    assert r.status_code == 403


def test_only_owner_can_delete(client, maria, joao):
    note = _create_note(
        client, maria["token"],
        compartilhado_com=[{"user_id": joao["id"], "nivel": "editar"}],
    )
    r = client.delete(f"/notes/{note['id']}", headers=auth(joao["token"]))
    assert r.status_code == 403
    r = client.delete(f"/notes/{note['id']}", headers=auth(maria["token"]))
    assert r.status_code == 200


def test_public_note_visible_via_linked_card_responsavel(client, maria, joao):
    r = client.post(
        "/cards",
        json={"titulo": "Tarefa", "status": "col-1", "autor": maria["nome"],
              "responsaveis": [maria["nome"], joao["nome"]]},
        headers=auth(maria["token"]),
    )
    assert r.status_code == 200, r.text
    card = r.json()

    note = _create_note(client, maria["token"], publico=True, card_id=card["id"])
    assert note["id"] in _note_ids(client, joao["token"])
