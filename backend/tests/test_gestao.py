from datetime import date, datetime, timedelta

from database import SessionLocal
from models import TimeEntryDB
from tests.conftest import auth, create_user


def _create_card(client, token, **overrides):
    payload = {"titulo": "Card da gestao", "status": "col-1", "autor": "admin", **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _registro(card_id, user, inicio, fim):
    """Grava um intervalo direto no banco — dá pra testar dias passados sem sleep."""
    db = SessionLocal()
    try:
        e = TimeEntryDB(id=f"tempo-teste-{datetime.now().timestamp()}-{user['id'][:6]}-{inicio.isoformat()}",
                        card_id=card_id, user_id=user["id"], usuario=user["nome"],
                        inicio=inicio.isoformat(), fim=fim.isoformat() if fim else None)
        db.add(e)
        db.commit()
        return e.id
    finally:
        db.close()


def _gestor(client, admin_token, nome, **cargo_extra):
    pessoa = create_user(client, admin_token, nome)
    cargo = client.post("/roles", json={"nome": f"Gestor {nome}", "permissoes": {"acessar_gestao": True}, **cargo_extra},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{pessoa['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))
    return pessoa


def test_gestao_requires_permission(client, admin_token):
    comum = create_user(client, admin_token, "gestao_sem_cargo")
    assert client.get("/gestao/visao-geral", headers=auth(comum["token"])).status_code == 403
    assert client.get(f"/gestao/funcionario/{comum['id']}", headers=auth(comum["token"])).status_code == 403

    gestor = _gestor(client, admin_token, "gestao_gestor")
    assert client.get("/gestao/visao-geral", headers=auth(gestor["token"])).status_code == 200


def test_hours_are_clipped_to_the_period(client, admin_token):
    gestor = _gestor(client, admin_token, "gestao_gestor_corte")
    func = create_user(client, admin_token, "gestao_func_corte")
    card = _create_card(client, admin_token, titulo="Virada de dia")
    ontem = date.today() - timedelta(days=1)
    meia_noite = datetime.combine(date.today(), datetime.min.time())
    # 23h de ontem até 1h de hoje: uma hora em cada dia.
    _registro(card["id"], func, meia_noite - timedelta(hours=1), meia_noite + timedelta(hours=1))

    def horas(inicio, fim):
        r = client.get(f"/gestao/visao-geral?inicio={inicio}&fim={fim}", headers=auth(gestor["token"]))
        assert r.status_code == 200, r.text
        linha = next(f for f in r.json()["funcionarios"] if f["user_id"] == func["id"])
        return linha["segundos"]

    assert horas(ontem.isoformat(), ontem.isoformat()) == 3600
    assert horas(ontem.isoformat(), date.today().isoformat()) == 7200

    ficha = client.get(f"/gestao/funcionario/{func['id']}?inicio={ontem}&fim={date.today()}",
                       headers=auth(gestor["token"])).json()
    assert ficha["total_segundos"] == 7200
    assert [d["segundos"] for d in ficha["por_dia"]] == [3600, 3600]
    assert ficha["por_card"][0]["card_id"] == card["id"]


def test_employee_without_hours_still_listed(client, admin_token):
    gestor = _gestor(client, admin_token, "gestao_gestor_zero")
    parado = create_user(client, admin_token, "gestao_func_parado")
    dados = client.get("/gestao/visao-geral", headers=auth(gestor["token"])).json()
    linha = next(f for f in dados["funcionarios"] if f["user_id"] == parado["id"])
    assert linha["segundos"] == 0 and linha["rodando"] is False


def test_running_timers_show_up(client, admin_token):
    gestor = _gestor(client, admin_token, "gestao_gestor_agora")
    func = create_user(client, admin_token, "gestao_func_agora")
    card = _create_card(client, admin_token, titulo="Rodando agora")
    client.post(f"/cards/{card['id']}/tempo/iniciar", json={"item_id": None}, headers=auth(func["token"]))

    dados = client.get("/gestao/visao-geral", headers=auth(gestor["token"])).json()
    assert any(r["user_id"] == func["id"] and r["card_id"] == card["id"] for r in dados["trabalhando_agora"])
    assert next(f for f in dados["funcionarios"] if f["user_id"] == func["id"])["rodando"] is True

    ficha = client.get(f"/gestao/funcionario/{func['id']}", headers=auth(gestor["token"])).json()
    assert ficha["rodando"]["card_id"] == card["id"]
    client.post("/tempo/parar", headers=auth(func["token"]))


def test_card_progress_and_overdue(client, admin_token):
    gestor = _gestor(client, admin_token, "gestao_gestor_andamento")
    card = _create_card(client, admin_token, titulo="Andamento", prazo="2000-01-01", responsaveis=["gestao_gestor_andamento"],
                        checklist=[
                            {"id": "e1", "texto": "pronta", "concluido": True},
                            {"id": "e2", "texto": "meio", "concluido": False, "subetapas": [
                                {"id": "s1", "texto": "a", "concluido": True}, {"id": "s2", "texto": "b", "concluido": False}]},
                        ])
    dados = client.get("/gestao/visao-geral", headers=auth(gestor["token"])).json()
    linha = next(c for c in dados["cards"] if c["id"] == card["id"])
    assert linha["progresso"] == 75
    assert linha["atrasado"] is True

    ficha = client.get(f"/gestao/funcionario/{gestor['id']}", headers=auth(gestor["token"])).json()
    assert any(c["id"] == card["id"] for c in ficha["cards_responsavel"])


def test_gestao_respects_column_visibility(client, admin_token):
    gestor = _gestor(client, admin_token, "gestao_gestor_restrito", colunas_restritas=True, colunas_visiveis=["col-1"])
    func = create_user(client, admin_token, "gestao_func_escondido")
    escondido = _create_card(client, admin_token, titulo="Fora da vista", status="col-2")
    agora = datetime.now()
    _registro(escondido["id"], func, agora - timedelta(minutes=30), agora - timedelta(minutes=10))

    dados = client.get("/gestao/visao-geral", headers=auth(gestor["token"])).json()
    assert all(c["id"] != escondido["id"] for c in dados["cards"])
    assert next(f for f in dados["funcionarios"] if f["user_id"] == func["id"])["segundos"] == 0


def test_invalid_period_is_rejected(client, admin_token):
    gestor = _gestor(client, admin_token, "gestao_gestor_datas")
    h = auth(gestor["token"])
    assert client.get("/gestao/visao-geral?inicio=ontem", headers=h).status_code == 400
    assert client.get("/gestao/visao-geral?inicio=2026-02-10&fim=2026-02-01", headers=h).status_code == 400
    assert client.get("/gestao/visao-geral?inicio=2020-01-01&fim=2026-01-01", headers=h).status_code == 400


def test_permissions_refresh_without_new_login(client, admin_token):
    """Cargo dado depois do login vale na hora: a tela consulta /me/permissions."""
    pessoa = create_user(client, admin_token, "gestao_sem_relogin")
    antes = client.get("/me/permissions", headers=auth(pessoa["token"])).json()["permissions"]
    assert "acessar_gestao" not in antes

    cargo = client.post("/roles", json={"nome": "Gestor relogin", "permissoes": {"acessar_gestao": True}},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{pessoa['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))
    depois = client.get("/me/permissions", headers=auth(pessoa["token"])).json()["permissions"]
    assert "acessar_gestao" in depois


def test_new_permissions_are_in_the_catalog(client, admin_token):
    chaves = {p["key"] for p in client.get("/permissions", headers=auth(admin_token)).json()}
    assert {"ver_tempo_equipe", "acessar_gestao", "restaurar_alteracoes"} <= chaves
