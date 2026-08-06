from tests.conftest import auth, login


def test_login_success(client):
    data = login(client, "admin", "admin")
    assert data["nome"] == "admin"
    assert data["role"] == "superadmin"
    assert data["token"]


def test_login_wrong_password(client):
    r = client.post("/login", json={"nome": "admin", "senha": "errada"})
    assert r.status_code == 401


def test_login_rate_limit(client):
    for _ in range(10):
        client.post("/login", json={"nome": "naoexiste", "senha": "x"})
    r = client.post("/login", json={"nome": "naoexiste", "senha": "x"})
    assert r.status_code == 429


def test_protected_route_without_token(client):
    r = client.get("/cards")
    assert r.status_code == 401


def test_protected_route_with_invalid_token(client):
    r = client.get("/cards", headers=auth("token-invalido"))
    assert r.status_code == 401


def test_users_list_does_not_expose_password_hash(client, admin_token):
    r = client.get("/users", headers=auth(admin_token))
    assert r.status_code == 200
    for u in r.json():
        assert "senha" not in u


def test_create_user_requires_admin(client, maria):
    r = client.post(
        "/users",
        json={"nome": "intruso", "senha": "x", "role": "usuario"},
        headers=auth(maria["token"]),
    )
    assert r.status_code == 403


def test_delete_user_requires_superadmin(client, admin_token, maria, joao):
    r = client.delete(f"/users/{joao['id']}", headers=auth(maria["token"]))
    assert r.status_code == 403


def test_user_cannot_change_others_password(client, maria, joao):
    r = client.put(
        f"/users/{joao['id']}/password",
        json={"nova_senha": "hackeada"},
        headers=auth(maria["token"]),
    )
    assert r.status_code == 403


def test_user_can_change_own_password(client, admin_token):
    from tests.conftest import create_user

    user = create_user(client, admin_token, "troca_senha", senha="antiga1")
    r = client.put(
        f"/users/{user['id']}/password",
        json={"nova_senha": "nova123"},
        headers=auth(user["token"]),
    )
    assert r.status_code == 200
    login(client, "troca_senha", "nova123")


def test_column_create_requires_admin(client, maria):
    r = client.post(
        "/columns",
        json={"id": "col-x", "titulo": "X", "cor": "#fff", "ordem": 9},
        headers=auth(maria["token"]),
    )
    assert r.status_code == 403
