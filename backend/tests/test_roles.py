from tests.conftest import auth, create_user, login


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card teste", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    return r


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
    return client.put(f"/cards/{card['id']}", json=payload, headers=auth(token))


def _audit_log(client, token, card_id=None):
    url = "/audit-log" + (f"?card_id={card_id}" if card_id else "")
    return client.get(url, headers=auth(token))


def _roles_by_name(client, token):
    r = client.get("/roles", headers=auth(token))
    assert r.status_code == 200, r.text
    return {ro["nome"]: ro for ro in r.json()}


def _create_role(client, token, nome, permissoes):
    r = client.post("/roles", json={"nome": nome, "cor": "#123456", "permissoes": permissoes}, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _set_user_roles(client, token, user_id, role_ids):
    return client.put(f"/users/{user_id}/roles", json={"role_ids": role_ids}, headers=auth(token))


def _user_id(client, token, nome):
    r = client.get("/users", headers=auth(token))
    assert r.status_code == 200
    return next(u["id"] for u in r.json() if u["nome"] == nome)


def _user_roles(client, token, user_id):
    r = client.get("/users", headers=auth(token))
    return next(u["roles"] for u in r.json() if u["id"] == user_id)


def test_seed_roles_exist_and_admin_has_superadmin(client, admin_token):
    roles = _roles_by_name(client, admin_token)
    assert {"Superadmin", "Admin", "Usuário"} <= set(roles.keys())
    assert roles["Superadmin"]["protegido"] is True

    admin_id = _user_id(client, admin_token, "admin")
    r = client.get("/users", headers=auth(admin_token))
    admin_user = next(u for u in r.json() if u["id"] == admin_id)
    assert any(ro["nome"] == "Superadmin" for ro in admin_user["roles"])


def test_multiple_roles_union_permissions(client, admin_token, joao):
    role_a = _create_role(client, admin_token, "SoSugestoes", {"decidir_sugestoes": True})
    role_b = _create_role(client, admin_token, "SoAuditoria", {"ver_log_auditoria": True})

    joao_id = _user_id(client, admin_token, joao["nome"])
    r = _set_user_roles(client, admin_token, joao_id, [role_a["id"], role_b["id"]])
    assert r.status_code == 200, r.text

    joao_login = login(client, joao["nome"], "senha123")
    assert "decidir_sugestoes" in joao_login["permissions"]
    assert "ver_log_auditoria" in joao_login["permissions"]

    r = client.get("/audit-log", headers=auth(joao_login["token"]))
    assert r.status_code == 200


def test_protected_role_cannot_be_edited_or_deleted(client, admin_token):
    roles = _roles_by_name(client, admin_token)
    sid = roles["Superadmin"]["id"]
    r = client.put(f"/roles/{sid}", json={"nome": "Hackeado"}, headers=auth(admin_token))
    assert r.status_code == 400
    r2 = client.delete(f"/roles/{sid}", headers=auth(admin_token))
    assert r2.status_code == 400


def test_anti_lockout_cannot_remove_last_superadmin(client, admin_token):
    admin_id = _user_id(client, admin_token, "admin")
    r = _set_user_roles(client, admin_token, admin_id, [])
    assert r.status_code == 400


def test_anti_escalation_requires_being_superadmin(client, admin_token, joao, maria):
    roles = _roles_by_name(client, admin_token)
    manage_role = _create_role(client, admin_token, "GerenciaCargos", {"gerenciar_cargos": True})
    joao_id = _user_id(client, admin_token, joao["nome"])
    r = _set_user_roles(client, admin_token, joao_id, [manage_role["id"]])
    assert r.status_code == 200

    joao_login = login(client, joao["nome"], "senha123")
    assert "gerenciar_cargos" in joao_login["permissions"]

    maria_id = _user_id(client, admin_token, maria["nome"])
    r2 = _set_user_roles(client, joao_login["token"], maria_id, [roles["Superadmin"]["id"]])
    # Barrado já pela regra de concessão (403): o Superadmin tem permissões que joão não tem.
    assert r2.status_code == 403
    assert not any(r["nome"] == "Superadmin" for r in _user_roles(client, admin_token, maria_id))


def test_require_permission_blocks_without_role(client, admin_token, maria):
    r = client.post("/columns", json={"id": "col-test-x", "titulo": "X", "cor": "#fff", "ordem": 99}, headers=auth(maria["token"]))
    assert r.status_code == 403

    r2 = client.delete("/users/algum-id-qualquer", headers=auth(maria["token"]))
    assert r2.status_code == 403


def test_field_level_gate_silently_reverts_unauthorized_field(client, admin_token, maria):
    r = _create_card(client, admin_token, "admin")
    card = r.json()

    put_r = _put_card(client, maria["token"], card, prioridade="Urgente", comentarios=[{"id": "c1", "autor": maria["nome"], "texto": "oi", "data": "01/01"}])
    assert put_r.status_code == 200

    updated = _get_card(client, admin_token, card["id"])
    assert updated["prioridade"] == "Normal"
    assert len(updated["comentarios"]) == 1

    logs = _audit_log(client, admin_token, card["id"]).json()
    assert not any(l["acao"] == "prioridade_alterada" for l in logs)


def test_concluir_etapas_without_gerenciar_etapas(client, admin_token, joao):
    role = _create_role(client, admin_token, "SoConcluiEtapas", {"concluir_etapas": True})
    joao_id = _user_id(client, admin_token, joao["nome"])
    assert _set_user_roles(client, admin_token, joao_id, [role["id"]]).status_code == 200
    joao_login = login(client, joao["nome"], "senha123")

    r = _create_card(client, admin_token, "admin")
    card = r.json()
    step = {"id": "role-step-1", "texto": "Texto original", "concluido": False, "criador": "admin"}
    assert _put_card(client, admin_token, card, checklist=[step]).status_code == 200
    card = _get_card(client, admin_token, card["id"])

    put_r = _put_card(
        client, joao_login["token"], card,
        checklist=[{**step, "texto": "Texto hackeado", "concluido": True, "concluidoPor": joao["nome"]}],
    )
    assert put_r.status_code == 200

    updated = _get_card(client, admin_token, card["id"])
    item = next(i for i in updated["checklist"] if i["id"] == "role-step-1")
    assert item["concluido"] is True
    assert item["texto"] == "Texto original"


def test_author_exceptions_preserved_for_plain_user(client, admin_token, maria):
    r = _create_card(client, maria["token"], maria["nome"], status="col-1")
    assert r.status_code == 200
    card = r.json()

    edit_r = _put_card(client, maria["token"], card, titulo="Editado pela autora")
    assert edit_r.status_code == 200
    updated = _get_card(client, admin_token, card["id"])
    assert updated["titulo"] == "Editado pela autora"

    del_r = client.delete(f"/cards/{card['id']}", headers=auth(maria["token"]))
    assert del_r.status_code == 200


def test_create_card_requires_permission_in_private_column(client, admin_token, maria):
    r = _create_card(client, maria["token"], maria["nome"], status="col-2")
    assert r.status_code == 403

    r2 = _create_card(client, maria["token"], maria["nome"], status="col-1")
    assert r2.status_code == 200


def test_ver_etapas_backfill_defaults_legacy_roles_true_but_preserves_explicit_false(client, admin_token):
    from database import SessionLocal
    from models import RoleDB
    from migrations import _backfill_ver_etapas_permission

    db = SessionLocal()
    try:
        db.add(RoleDB(
            id="role-legacy-sem-ver-etapas", nome="LegadoSemVerEtapas", cor="#000000",
            protegido=False, permissoes={"decidir_sugestoes": True}, ordem=99,
        ))
        db.commit()
    finally:
        db.close()

    _backfill_ver_etapas_permission()
    roles = _roles_by_name(client, admin_token)
    assert roles["LegadoSemVerEtapas"]["permissoes"]["ver_etapas"] is True

    db2 = SessionLocal()
    try:
        role = db2.query(RoleDB).filter(RoleDB.id == "role-legacy-sem-ver-etapas").first()
        role.permissoes = {**role.permissoes, "ver_etapas": False}
        db2.commit()
    finally:
        db2.close()

    _backfill_ver_etapas_permission()  # must not clobber an explicit False
    roles2 = _roles_by_name(client, admin_token)
    assert roles2["LegadoSemVerEtapas"]["permissoes"]["ver_etapas"] is False


# ------------------------------------------------------------- sem auto-promoção

def _gestor_de_cargos(client, admin_token, nome, extras=None):
    """Alguém com gerenciar_cargos (e o que mais vier em extras), sem ser Superadmin."""
    pessoa = create_user(client, admin_token, nome)
    cargo = _create_role(client, admin_token, f"Cargos de {nome}", {"gerenciar_cargos": True, **(extras or {})})
    _set_user_roles(client, admin_token, pessoa["id"], [cargo["id"]])
    return login(client, nome, "senha123"), cargo


def test_cannot_edit_own_role_or_own_roles(client, admin_token):
    eu, meu_cargo = _gestor_de_cargos(client, admin_token, "auto_promocao")
    r = client.put(f"/roles/{meu_cargo['id']}", json={"permissoes": {"gerenciar_cargos": True, "excluir_usuarios": True}},
                   headers=auth(eu["token"]))
    assert r.status_code == 403
    assert client.delete(f"/roles/{meu_cargo['id']}", headers=auth(eu["token"])).status_code == 403

    outro = _create_role(client, admin_token, "Cargo fraco", {})
    assert _set_user_roles(client, eu["token"], eu["id"], [meu_cargo["id"], outro["id"]]).status_code == 403
    assert [r["id"] for r in _user_roles(client, admin_token, eu["id"])] == [meu_cargo["id"]]


def test_can_only_grant_what_you_have(client, admin_token):
    eu, _ = _gestor_de_cargos(client, admin_token, "concede_o_que_tem", {"editar_card": True})
    h = auth(eu["token"])

    assert client.post("/roles", json={"nome": "Forte demais", "permissoes": {"excluir_usuarios": True}}, headers=h).status_code == 403
    ok = client.post("/roles", json={"nome": "Repassa editar", "permissoes": {"editar_card": True}}, headers=h)
    assert ok.status_code == 200

    # Cargo de outra pessoa com permissão que eu não tenho: não mexo nela.
    forte = _create_role(client, admin_token, "Forte alheio", {"excluir_usuarios": True})
    r = client.put(f"/roles/{forte['id']}", json={"permissoes": {}}, headers=h)
    assert r.status_code == 403
    assert client.delete(f"/roles/{forte['id']}", headers=h).status_code == 403
    # ...mas o que eu tenho eu posso ligar nele, desde que não toque no resto.
    r = client.put(f"/roles/{forte['id']}", json={"permissoes": {"excluir_usuarios": True, "editar_card": True}}, headers=h)
    assert r.status_code == 200

    alguem = create_user(client, admin_token, "recebe_cargo")
    assert _set_user_roles(client, eu["token"], alguem["id"], [forte["id"]]).status_code == 403
    assert _set_user_roles(client, eu["token"], alguem["id"], [ok.json()["id"]]).status_code == 200


def test_column_restricted_manager_cannot_widen_columns(client, admin_token):
    eu, _ = _gestor_de_cargos(client, admin_token, "so_col1_cargos")
    # Restringe quem gerencia à col-1 pelo cargo dele.
    cargo = next(r for r in client.get("/roles", headers=auth(admin_token)).json() if r["nome"] == "Cargos de so_col1_cargos")
    client.put(f"/roles/{cargo['id']}", json={"colunas_restritas": True, "colunas_visiveis": ["col-1"]}, headers=auth(admin_token))
    h = auth(eu["token"])
    assert client.post("/roles", json={"nome": "Ve tudo", "permissoes": {}}, headers=h).status_code == 403
    assert client.post("/roles", json={"nome": "Ve col2", "permissoes": {}, "colunas_restritas": True,
                                       "colunas_visiveis": ["col-2"]}, headers=h).status_code == 403
    assert client.post("/roles", json={"nome": "Ve col1", "permissoes": {}, "colunas_restritas": True,
                                       "colunas_visiveis": ["col-1"]}, headers=h).status_code == 200


def test_superadmin_is_exempt(client, admin_token):
    roles = _roles_by_name(client, admin_token)
    admin_id = _user_id(client, admin_token, "admin")
    # Superadmin edita qualquer cargo, inclusive concedendo tudo.
    forte = _create_role(client, admin_token, "Tudo liberado", {k: True for k in ("excluir_usuarios", "restaurar_alteracoes")})
    assert forte["permissoes"]["excluir_usuarios"] is True
    atuais = [r["id"] for r in _user_roles(client, admin_token, admin_id)]
    assert _set_user_roles(client, admin_token, admin_id, atuais + [forte["id"]]).status_code == 200
    assert _set_user_roles(client, admin_token, admin_id, [roles["Superadmin"]["id"]]).status_code == 200
