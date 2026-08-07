import uuid

from tests.conftest import auth, create_user, login


def _fresh_user(client, admin_token):
    """A dedicated user per test — these tests reassign cargos in ways that
    would otherwise leak into other test files if done on the shared
    session-scoped maria/joao fixtures (role assignment is a full replace,
    and there's no teardown to restore a fixture user's cargos afterward)."""
    nome = f"visuser{uuid.uuid4().hex[:8]}"
    return create_user(client, admin_token, nome)


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card teste", "status": "col-1", "autor": autor, **overrides}
    return client.post("/cards", json=payload, headers=auth(token))


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
    return client.put(f"/cards/{card['id']}", json=payload, headers=auth(token))


def _create_role(client, token, nome, permissoes=None, colunas_restritas=False, colunas_visiveis=None):
    body = {
        "nome": nome, "cor": "#123456", "permissoes": permissoes or {},
        "colunas_restritas": colunas_restritas, "colunas_visiveis": colunas_visiveis or [],
    }
    r = client.post("/roles", json=body, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _set_user_roles(client, token, user_id, role_ids):
    return client.put(f"/users/{user_id}/roles", json={"role_ids": role_ids}, headers=auth(token))


def test_role_restricted_to_one_column_only_sees_that_column(client, admin_token):
    card_col1 = _create_card(client, admin_token, "admin", status="col-1").json()
    card_col2 = _create_card(client, admin_token, "admin", status="col-2").json()

    user = _fresh_user(client, admin_token)
    role = _create_role(client, admin_token, f"SoCol2-{uuid.uuid4().hex[:6]}", colunas_restritas=True, colunas_visiveis=["col-2"])
    assert _set_user_roles(client, admin_token, user["id"], [role["id"]]).status_code == 200

    utoken = login(client, user["nome"], "senha123")["token"]

    cols = client.get("/columns", headers=auth(utoken)).json()
    assert {c["id"] for c in cols} == {"col-2"}

    cards = client.get("/cards", headers=auth(utoken)).json()
    card_ids = {c["id"] for c in cards}
    assert card_col2["id"] in card_ids
    assert card_col1["id"] not in card_ids


def test_create_card_outside_visible_columns_is_404_even_if_public(client, admin_token):
    user = _fresh_user(client, admin_token)
    role = _create_role(client, admin_token, f"SoCol2b-{uuid.uuid4().hex[:6]}", colunas_restritas=True, colunas_visiveis=["col-2"])
    assert _set_user_roles(client, admin_token, user["id"], [role["id"]]).status_code == 200
    utoken = login(client, user["nome"], "senha123")["token"]

    # col-1 is publica=True (seed data) — still 404 because it's outside the visible set
    r = _create_card(client, utoken, user["nome"], status="col-1")
    assert r.status_code == 404


def test_write_endpoints_404_on_card_outside_visible_columns(client, admin_token):
    card = _create_card(client, admin_token, "admin", status="col-1").json()

    user = _fresh_user(client, admin_token)
    role = _create_role(client, admin_token, f"SoCol2c-{uuid.uuid4().hex[:6]}", colunas_restritas=True, colunas_visiveis=["col-2"])
    assert _set_user_roles(client, admin_token, user["id"], [role["id"]]).status_code == 200
    utoken = login(client, user["nome"], "senha123")["token"]

    assert _put_card(client, utoken, card, titulo="tentativa").status_code == 404
    assert client.delete(f"/cards/{card['id']}", headers=auth(utoken)).status_code == 404
    assert client.post(f"/cards/{card['id']}/seen", headers=auth(utoken)).status_code == 404
    assert client.get(f"/cards/{card['id']}/suggestions", headers=auth(utoken)).status_code == 404
    assert client.post(f"/cards/{card['id']}/suggestions", json={"texto": "x", "identificacao": "Fulano"}, headers=auth(utoken)).status_code == 404


def test_gerenciar_colunas_bypasses_visibility_restriction(client, admin_token):
    user = _fresh_user(client, admin_token)
    role = _create_role(
        client, admin_token, f"AdminColRestrito-{uuid.uuid4().hex[:6]}",
        permissoes={"gerenciar_colunas": True},
        colunas_restritas=True, colunas_visiveis=["col-2"],
    )
    assert _set_user_roles(client, admin_token, user["id"], [role["id"]]).status_code == 200
    utoken = login(client, user["nome"], "senha123")["token"]

    cols = client.get("/columns", headers=auth(utoken)).json()
    all_cols = client.get("/columns", headers=auth(admin_token)).json()
    assert {c["id"] for c in cols} == {c["id"] for c in all_cols}


def test_clearing_restriction_restores_full_visibility(client, admin_token):
    user = _fresh_user(client, admin_token)
    role = _create_role(client, admin_token, f"TemporarioRestrito-{uuid.uuid4().hex[:6]}", colunas_restritas=True, colunas_visiveis=["col-2"])
    assert _set_user_roles(client, admin_token, user["id"], [role["id"]]).status_code == 200
    utoken = login(client, user["nome"], "senha123")["token"]
    cols = client.get("/columns", headers=auth(utoken)).json()
    assert {c["id"] for c in cols} == {"col-2"}

    r = client.put(f"/roles/{role['id']}", json={"colunas_restritas": False}, headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["colunas_visiveis"] is None

    utoken2 = login(client, user["nome"], "senha123")["token"]
    cols_after = client.get("/columns", headers=auth(utoken2)).json()
    all_cols = client.get("/columns", headers=auth(admin_token)).json()
    assert {c["id"] for c in cols_after} == {c["id"] for c in all_cols}
