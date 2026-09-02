from tests.conftest import auth


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card com anexo", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _upload(client, token, card_id, filename="teste.txt", content=b"conteudo do arquivo", content_type="text/plain"):
    return client.post(
        f"/cards/{card_id}/attachments",
        files={"file": (filename, content, content_type)},
        headers=auth(token),
    )


def test_upload_and_list_attachment(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    r = _upload(client, maria["token"], card["id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["nome_original"] == "teste.txt"
    assert body["tamanho"] == len(b"conteudo do arquivo")
    assert body["enviado_por"] == maria["nome"]

    r2 = client.get(f"/cards/{card['id']}/attachments", headers=auth(maria["token"]))
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_download_attachment_returns_original_content(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    conteudo = b"hello kyndo attachment"
    anexo = _upload(client, maria["token"], card["id"], content=conteudo).json()

    r = client.get(f"/attachments/{anexo['id']}/download", headers=auth(maria["token"]))
    assert r.status_code == 200
    assert r.content == conteudo


def test_delete_requires_uploader_or_editar_card(client, admin_token, maria, joao):
    card = _create_card(client, admin_token, "admin")
    anexo = _upload(client, maria["token"], card["id"]).json()

    # joao is neither the uploader nor has editar_card
    r_forbidden = client.delete(f"/attachments/{anexo['id']}", headers=auth(joao["token"]))
    assert r_forbidden.status_code == 403

    # maria uploaded it, so she can delete her own
    r_ok = client.delete(f"/attachments/{anexo['id']}", headers=auth(maria["token"]))
    assert r_ok.status_code == 200

    r_list = client.get(f"/cards/{card['id']}/attachments", headers=auth(admin_token))
    assert r_list.json() == []


def test_admin_with_editar_card_can_delete_others_attachment(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    anexo = _upload(client, maria["token"], card["id"]).json()

    r = client.delete(f"/attachments/{anexo['id']}", headers=auth(admin_token))
    assert r.status_code == 200


def test_upload_rejects_file_over_size_limit(client, admin_token, monkeypatch):
    import routers.attachments as attachments_module
    monkeypatch.setattr(attachments_module, "MAX_UPLOAD_BYTES", 10)

    card = _create_card(client, admin_token, "admin")
    r = _upload(client, admin_token, card["id"], content=b"x" * 11)
    assert r.status_code == 413

    r_list = client.get(f"/cards/{card['id']}/attachments", headers=auth(admin_token))
    assert r_list.json() == []


def test_attachment_endpoints_404_on_card_outside_visible_columns(client, admin_token, maria):
    import uuid

    from tests.conftest import login

    card = _create_card(client, admin_token, "admin", status="col-1")
    anexo = _upload(client, admin_token, card["id"]).json()

    r_role = client.post(
        "/roles",
        json={"nome": f"SoCol2attach-{uuid.uuid4().hex[:6]}", "cor": "#123456", "permissoes": {}, "colunas_restritas": True, "colunas_visiveis": ["col-2"]},
        headers=auth(admin_token),
    )
    assert r_role.status_code == 200, r_role.text
    role = r_role.json()

    nome_novo = f"restrito-{uuid.uuid4().hex[:6]}"
    r_user = client.post("/users", json={"nome": nome_novo, "senha": "senha123"}, headers=auth(admin_token))
    assert r_user.status_code == 200, r_user.text
    user_id = next(u["id"] for u in client.get("/users", headers=auth(admin_token)).json() if u["nome"] == nome_novo)
    r_set = client.put(f"/users/{user_id}/roles", json={"role_ids": [role["id"]]}, headers=auth(admin_token))
    assert r_set.status_code == 200, r_set.text
    utoken = login(client, nome_novo, "senha123")["token"]

    assert client.get(f"/cards/{card['id']}/attachments", headers=auth(utoken)).status_code == 404
    assert _upload(client, utoken, card["id"]).status_code == 404
    assert client.get(f"/attachments/{anexo['id']}/download", headers=auth(utoken)).status_code == 404
    assert client.delete(f"/attachments/{anexo['id']}", headers=auth(utoken)).status_code == 404
