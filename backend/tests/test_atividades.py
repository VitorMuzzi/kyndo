from datetime import date, datetime, timedelta

from tests.conftest import auth, create_user


def _criar(client, token, **corpo):
    return client.post("/atividades", json=corpo, headers=auth(token))


def _hora(delta_horas):
    return (datetime.now() + timedelta(hours=delta_horas)).strftime("%Y-%m-%dT%H:%M")


def test_activity_timer_shares_the_single_running_timer(client, admin_token):
    pessoa = create_user(client, admin_token, "atv_crono")
    r = _criar(client, pessoa["token"], titulo="  Saida   de campo ", modo="agora")
    assert r.status_code == 200, r.text
    atv = r.json()["atividade"]
    assert atv["titulo"] == "Saida de campo" and atv["em_andamento"] and atv["minha"]
    atual = client.get("/tempo/atual", headers=auth(pessoa["token"])).json()
    assert atual["atividade_id"] == atv["id"] and atual["atividade_titulo"] == "Saida de campo"

    # Ligar o cronômetro num card desliga o da atividade.
    card = client.post("/cards", json={"titulo": "Card atv", "status": "col-1", "autor": "atv_crono"},
                       headers=auth(pessoa["token"])).json()
    client.post(f"/cards/{card['id']}/tempo/iniciar", json={}, headers=auth(pessoa["token"]))
    hoje = date.today().isoformat()
    lista = client.get(f"/atividades?inicio={hoje}&fim={hoje}", headers=auth(pessoa["token"])).json()
    assert not next(a for a in lista if a["id"] == atv["id"])["em_andamento"]
    client.post("/tempo/parar", headers=auth(pessoa["token"]))


def test_manual_and_scheduled_activities_and_ownership(client, admin_token):
    dona = create_user(client, admin_token, "atv_dona")
    outra = create_user(client, admin_token, "atv_outra")

    # Lançar depois: só o que já passou, fim depois do início, até 24h.
    assert _criar(client, dona["token"], titulo="Visita", modo="lancar", inicio=_hora(-1), fim=_hora(-3)).status_code == 400
    assert _criar(client, dona["token"], titulo="Visita", modo="lancar", inicio=_hora(1), fim=_hora(2)).status_code == 400
    assert _criar(client, dona["token"], titulo="Visita", modo="lancar", inicio=_hora(-30), fim=_hora(-1)).status_code == 400
    r = _criar(client, dona["token"], titulo="Visita ao cliente", modo="lancar", inicio=_hora(-3), fim=_hora(-1))
    assert r.status_code == 200, r.text
    visita = r.json()["atividade"]
    assert 7100 <= visita["total_segundos"] <= 7200 and r.json()["cronometro"] is None

    # Agendar no futuro: aparece na janela, sem tempo.
    r = _criar(client, dona["token"], titulo="Campo terca", modo="agendar", inicio=_hora(24), fim=_hora(32))
    agendada = r.json()["atividade"]
    assert agendada["agendada_inicio"] and agendada["total_segundos"] == 0
    amanha = (date.today() + timedelta(days=2)).isoformat()
    vistas = client.get(f"/atividades?inicio={date.today().isoformat()}&fim={amanha}", headers=auth(outra["token"])).json()
    ids = {a["id"]: a for a in vistas}
    assert agendada["id"] in ids and not ids[agendada["id"]]["minha"]

    # Só a dona mexe.
    url = f"/atividades/{agendada['id']}"
    assert client.delete(url, headers=auth(outra["token"])).status_code == 403
    assert client.post(f"{url}/iniciar", headers=auth(outra["token"])).status_code == 403
    r = client.post(f"{url}/registros", json={"inicio": _hora(-2), "fim": _hora(-1)}, headers=auth(dona["token"]))
    assert r.status_code == 200 and len(r.json()["registros"]) == 1
    r = client.put(url, json={"titulo": "Campo quarta", "agendada_inicio": None, "agendada_fim": None}, headers=auth(dona["token"]))
    assert r.json()["titulo"] == "Campo quarta" and r.json()["agendada_inicio"] is None
    assert client.delete(url, headers=auth(dona["token"])).status_code == 200


def test_activity_time_counts_in_reports_and_management(client, admin_token):
    pessoa = create_user(client, admin_token, "atv_conta")
    # Ontem, 10h às 12h: sempre no passado e dentro de um dia só.
    inicio = datetime.combine(date.today() - timedelta(days=1), datetime.min.time()) + timedelta(hours=10)
    fim = inicio + timedelta(hours=2)
    r = _criar(client, pessoa["token"], titulo="Treinamento", modo="lancar",
               inicio=inicio.strftime("%Y-%m-%dT%H:%M"), fim=fim.strftime("%Y-%m-%dT%H:%M"))
    assert r.status_code == 200, r.text
    dia = inicio.date().isoformat()

    ativ = client.get(f"/relatorios/dia/{dia}", headers=auth(pessoa["token"])).json()["atividade"]
    assert ativ["atividades"][0]["titulo"] == "Treinamento"
    assert ativ["total_segundos"] == 7200 and ativ["cards"] == []

    geral = client.get(f"/gestao/visao-geral?inicio={dia}&fim={dia}", headers=auth(admin_token)).json()
    assert next(f for f in geral["funcionarios"] if f["nome"] == "atv_conta")["segundos"] == 7200
    ficha = client.get(f"/gestao/funcionario/{pessoa['id']}?inicio={dia}&fim={dia}", headers=auth(admin_token)).json()
    assert ficha["total_segundos"] == 7200
    assert ficha["por_atividade"][0]["titulo"] == "Treinamento"
    assert ficha["registros"][0]["card_id"] is None and ficha["registros"][0]["card_titulo"] == "Treinamento"
