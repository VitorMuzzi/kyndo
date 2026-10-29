"""Renomear usuário, trocar a própria senha e "esqueci a senha"."""
from tests.conftest import auth, create_user, login
from tests.test_reversao import _create_card, _desfazer, _etapa, _get_card, _put, _ultimo


def _cargo_para(client, admin_token, pessoa, nome_cargo, permissoes):
    r = client.post("/roles", json={"nome": nome_cargo, "permissoes": permissoes}, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    r = client.put(f"/users/{pessoa['id']}/roles", json={"role_ids": [r.json()["id"]]}, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    return login(client, pessoa["nome"], "senha123")


def _renomear(client, token, user_id, nome):
    return client.put(f"/users/{user_id}", json={"nome": nome}, headers=auth(token))


# ------------------------------------------------------------------ renomear

def test_rename_carries_name_everywhere_and_can_be_undone(client, admin_token):
    pessoa = _cargo_para(client, admin_token, create_user(client, admin_token, "nome_velho"),
                         "Mexe em etapas", {"gerenciar_etapas": True, "concluir_etapas": True})
    card = _create_card(client, pessoa["token"], titulo="Card do nome velho", autor="nome_velho",
                        responsaveis=["nome_velho"])
    _put(client, pessoa["token"], card["id"],
         checklist=[_etapa("e1", "Etapa", concluido=True)],
         comentarios=[{"id": "c1", "texto": "oi", "autor": "x"}])

    r = _renomear(client, admin_token, pessoa["id"], "  nome_novo  ")
    assert r.status_code == 200, r.text
    assert r.json()["nome"] == "nome_novo"

    c = _get_card(client, admin_token, card["id"])
    assert c["autor"] == "nome_novo"
    assert c["responsaveis"] == ["nome_novo"]
    assert c["checklist"][0]["criador"] == "nome_novo"
    assert c["checklist"][0]["concluidoPor"] == "nome_novo"
    assert c["comentarios"][0]["autor"] == "nome_novo"
    # O token segue valendo (é pelo id) e o login passa a ser pelo nome novo.
    me = client.get("/me/permissions", headers=auth(pessoa["token"])).json()
    assert me["nome"] == "nome_novo"
    login(client, "nome_novo", "senha123")
    assert client.post("/login", json={"nome": "nome_velho", "senha": "senha123"}).status_code == 401

    log = _ultimo(client, admin_token, "usuario_renomeado")
    assert (log["valor_antigo"], log["valor_novo"]) == ("nome_velho", "nome_novo")
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    assert _get_card(client, admin_token, card["id"])["autor"] == "nome_velho"
    login(client, "nome_velho", "senha123")


def test_rename_validation(client, admin_token):
    pessoa = create_user(client, admin_token, "valida_nome")
    create_user(client, admin_token, "nome_ocupado")
    assert _renomear(client, admin_token, pessoa["id"], "   ").status_code == 400
    assert _renomear(client, admin_token, pessoa["id"], "nome_ocupado").status_code == 400
    assert _renomear(client, admin_token, pessoa["id"], "x" * 41).status_code == 400

    admin_id = next(u["id"] for u in client.get("/users", headers=auth(admin_token)).json() if u["nome"] == "admin")
    assert _renomear(client, admin_token, admin_id, "chefe").status_code == 400

    # Nome de alguém na lixeira voltaria em conflito ao recuperar.
    excluido = create_user(client, admin_token, "na_lixeira_nome")
    client.delete(f"/users/{excluido['id']}", headers=auth(admin_token))
    assert _renomear(client, admin_token, pessoa["id"], "na_lixeira_nome").status_code == 400


def test_rename_needs_permission_and_superadmin_is_protected(client, admin_token, maria):
    alvo = create_user(client, admin_token, "alvo_de_renome")
    assert _renomear(client, maria["token"], alvo["id"], "hackeado").status_code == 403

    gestor = _cargo_para(client, admin_token, create_user(client, admin_token, "gestor_renomeia"),
                         "Renomeia usuarios", {"gerenciar_usuarios": True})
    assert _renomear(client, gestor["token"], alvo["id"], "alvo_renomeado").status_code == 200

    chefe = create_user(client, admin_token, "chefe_super")
    roles = client.get("/roles", headers=auth(admin_token)).json()
    sup = next(r["id"] for r in roles if r["nome"] == "Superadmin")
    client.put(f"/users/{chefe['id']}/roles", json={"role_ids": [sup]}, headers=auth(admin_token))
    assert _renomear(client, gestor["token"], chefe["id"], "rebaixado").status_code == 403


# ------------------------------------------------------------- própria senha

def test_own_password_change_requires_current_password(client, admin_token):
    pessoa = create_user(client, admin_token, "pede_senha_atual")
    # Primeira troca (senha temporária do cadastro) não pede a atual.
    r = client.put(f"/users/{pessoa['id']}/password", json={"nova_senha": "primeira"}, headers=auth(pessoa["token"]))
    assert r.status_code == 200
    token = r.json()["token"]

    url = f"/users/{pessoa['id']}/password"
    assert client.put(url, json={"nova_senha": "segunda"}, headers=auth(token)).status_code == 400
    assert client.put(url, json={"nova_senha": "segunda", "senha_atual": "errada"}, headers=auth(token)).status_code == 400
    assert client.put(url, json={"nova_senha": "abc", "senha_atual": "primeira"}, headers=auth(token)).status_code == 400
    r = client.put(url, json={"nova_senha": "segunda", "senha_atual": "primeira"}, headers=auth(token))
    assert r.status_code == 200
    login(client, "pede_senha_atual", "segunda")


# ----------------------------------------------------------- esqueci a senha

def test_forgot_password_request_flow(client, admin_token, maria):
    pessoa = create_user(client, admin_token, "esqueceu_senha")
    r1 = client.post("/esqueci-senha", json={"nome": "esqueceu_senha"})
    r2 = client.post("/esqueci-senha", json={"nome": "ninguem_com_esse_nome"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()  # não revela quem existe
    client.post("/esqueci-senha", json={"nome": "esqueceu_senha"})  # repetido não duplica

    pedidos = [p for p in client.get("/pedidos-senha", headers=auth(admin_token)).json() if p["nome"] == "esqueceu_senha"]
    assert len(pedidos) == 1
    assert client.get("/me/permissions", headers=auth(admin_token)).json()["pedidos_senha"] >= 1
    assert client.get("/pedidos-senha", headers=auth(maria["token"])).status_code == 403
    assert client.get("/me/permissions", headers=auth(maria["token"])).json()["pedidos_senha"] == 0

    # O admin define uma senha temporária: o pedido some e a troca fica na auditoria.
    r = client.put(f"/users/{pessoa['id']}/password", json={"nova_senha": "temp1234"}, headers=auth(admin_token))
    assert r.status_code == 200
    assert not [p for p in client.get("/pedidos-senha", headers=auth(admin_token)).json() if p["nome"] == "esqueceu_senha"]
    assert login(client, "esqueceu_senha", "temp1234")["senha_temporaria"] is True
    assert _ultimo(client, admin_token, "senha_redefinida")["card_titulo"] == "esqueceu_senha"


def test_forgot_password_request_cleared_by_login_or_dismiss(client, admin_token):
    create_user(client, admin_token, "lembrou_senha")
    client.post("/esqueci-senha", json={"nome": "lembrou_senha"})
    login(client, "lembrou_senha", "senha123")
    assert not [p for p in client.get("/pedidos-senha", headers=auth(admin_token)).json() if p["nome"] == "lembrou_senha"]

    create_user(client, admin_token, "pedido_descartado")
    client.post("/esqueci-senha", json={"nome": "pedido_descartado"})
    pedido = next(p for p in client.get("/pedidos-senha", headers=auth(admin_token)).json() if p["nome"] == "pedido_descartado")
    assert client.delete(f"/pedidos-senha/{pedido['id']}", headers=auth(admin_token)).status_code == 200
    assert client.delete(f"/pedidos-senha/{pedido['id']}", headers=auth(admin_token)).status_code == 404
