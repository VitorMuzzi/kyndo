from datetime import date, datetime, timedelta

from database import SessionLocal
from models import TimeEntryDB
from tests.conftest import auth, create_user


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card do relatorio", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _registrar(user_id, card_id, inicio, fim):
    db = SessionLocal()
    try:
        db.add(TimeEntryDB(id=f"te-rel-{inicio.timestamp()}", card_id=card_id, user_id=user_id, usuario="x",
                           inicio=inicio.isoformat(), fim=fim.isoformat()))
        db.commit()
    finally:
        db.close()


def test_day_activity_counts_only_the_part_inside_the_day(client, admin_token):
    pessoa = create_user(client, admin_token, "relata_dia")
    card = _create_card(client, pessoa["token"], pessoa["nome"])
    hoje = date.today()
    meia_noite = datetime.combine(hoje, datetime.min.time())
    # 23h de ontem até 1h de hoje: uma hora em cada dia.
    _registrar(pessoa["id"], card["id"], meia_noite - timedelta(hours=1), meia_noite + timedelta(hours=1))

    r = client.get(f"/relatorios/dia/{hoje.isoformat()}", headers=auth(pessoa["token"]))
    assert r.status_code == 200, r.text
    ativ = r.json()["atividade"]
    assert ativ["total_segundos"] == 3600
    item = ativ["cards"][0]
    assert item["titulo"] == "Card do relatorio" and item["existe"]
    assert item["etapas"] == [{"texto": None, "segundos": 3600}]
    assert any(a["acao"] == "card_criado" for a in item["acoes"])

    ontem = client.get(f"/relatorios/dia/{(hoje - timedelta(days=1)).isoformat()}", headers=auth(pessoa["token"])).json()
    assert ontem["atividade"]["total_segundos"] == 3600
    assert not ontem["atividade"]["cards"][0]["acoes"]


def test_report_is_saved_per_day_and_private(client, admin_token):
    pessoa = create_user(client, admin_token, "relata_salva")
    outra = create_user(client, admin_token, "relata_outra")
    dia = "2026-10-20"
    r = client.put(f"/relatorios/dia/{dia}", json={"conteudo": "Fechei o modulo de compras."}, headers=auth(pessoa["token"]))
    assert r.status_code == 200, r.text
    assert client.get(f"/relatorios/dia/{dia}", headers=auth(pessoa["token"])).json()["conteudo"] == "Fechei o modulo de compras."
    assert [x["data"] for x in client.get("/relatorios", headers=auth(pessoa["token"])).json()] == [dia]

    # Cada um só vê o próprio.
    assert client.get(f"/relatorios/dia/{dia}", headers=auth(outra["token"])).json()["conteudo"] == ""
    assert client.get("/relatorios", headers=auth(outra["token"])).json() == []

    # Apagar todo o texto tira o dia da lista.
    client.put(f"/relatorios/dia/{dia}", json={"conteudo": "  "}, headers=auth(pessoa["token"]))
    assert client.get("/relatorios", headers=auth(pessoa["token"])).json() == []

    assert client.get("/relatorios/dia/ontem", headers=auth(pessoa["token"])).status_code == 400


def test_send_report_to_a_manager_by_email(client, admin_token, monkeypatch):
    import email_envio
    from tests.test_emails import _com_email
    enviados = []
    monkeypatch.setenv("SMTP_USER", "kyndo@email.teste")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    monkeypatch.setattr(email_envio, "_despachar", enviados.append)

    autor = _com_email(client, admin_token, "relata_envia", "autor.relatorio@email.teste")
    gestor = _com_email(client, admin_token, "gestor_relatorio", "gestor.relatorio@email.teste")
    comum = create_user(client, admin_token, "relata_comum")
    cargo = client.post("/roles", json={"nome": "Gestao relatorio", "permissoes": {"acessar_gestao": True}},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{gestor['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))

    nomes = {d["nome"] for d in client.get("/relatorios/destinatarios", headers=auth(autor["token"])).json()}
    assert "gestor_relatorio" in nomes and "relata_comum" not in nomes

    dia = "2026-10-21"
    url = f"/relatorios/dia/{dia}/enviar"
    # Sem texto não envia; para quem não é gestor também não.
    assert client.post(url, json={"para": [gestor["id"]]}, headers=auth(autor["token"])).status_code == 400
    client.put(f"/relatorios/dia/{dia}", json={"conteudo": "Linha 1\nLinha 2"}, headers=auth(autor["token"]))
    assert client.post(url, json={"para": [comum["id"]]}, headers=auth(autor["token"])).status_code == 400

    r = client.post(url, json={"para": [gestor["id"]]}, headers=auth(autor["token"]))
    assert r.status_code == 200, r.text
    msg = next(m for m in enviados if m["To"] == "gestor.relatorio@email.teste")
    assert "relata_envia" in msg["Subject"] and "21/10/2026" in msg["Subject"]
    assert msg["Reply-To"] == "autor.relatorio@email.teste"
    assert "Linha 1\nLinha 2" in msg.get_body(("plain",)).get_content()
    envio = r.json()["envios"][0]
    assert envio["para_nome"] == "gestor_relatorio" and envio["igual_ao_atual"]

    # Editar depois não muda o que foi enviado, mas a tela sabe que mudou.
    client.put(f"/relatorios/dia/{dia}", json={"conteudo": "Linha 1 editada"}, headers=auth(autor["token"]))
    assert client.get(f"/relatorios/dia/{dia}", headers=auth(autor["token"])).json()["envios"][0]["igual_ao_atual"] is False


def test_report_templates_are_personal(client, admin_token):
    dono = create_user(client, admin_token, "modelo_dono")
    outro = create_user(client, admin_token, "modelo_outro")
    r = client.post("/relatorios/modelos", json={"nome": "  Diario   padrao ", "conteudo": "Feito:\n{resumo}"},
                    headers=auth(dono["token"]))
    assert r.status_code == 200, r.text
    modelo = r.json()
    assert modelo["nome"] == "Diario padrao"
    assert client.post("/relatorios/modelos", json={"nome": "Vazio", "conteudo": " "}, headers=auth(dono["token"])).status_code == 400

    assert client.get("/relatorios/modelos", headers=auth(outro["token"])).json() == []
    url = f"/relatorios/modelos/{modelo['id']}"
    assert client.put(url, json={"nome": "X", "conteudo": "y"}, headers=auth(outro["token"])).status_code == 404
    assert client.delete(url, headers=auth(outro["token"])).status_code == 404

    r = client.put(url, json={"nome": "Semanal", "conteudo": "Semana de {data}"}, headers=auth(dono["token"]))
    assert r.json()["nome"] == "Semanal"
    assert [m["nome"] for m in client.get("/relatorios/modelos", headers=auth(dono["token"])).json()] == ["Semanal"]
    assert client.delete(url, headers=auth(dono["token"])).status_code == 200
    assert client.get("/relatorios/modelos", headers=auth(dono["token"])).json() == []


def _gestor_com_cargo(client, admin_token, nome, email=None):
    from tests.test_emails import _com_email
    pessoa = _com_email(client, admin_token, nome, email) if email else create_user(client, admin_token, nome)
    cargo = client.post("/roles", json={"nome": f"Gestao {nome}", "permissoes": {"acessar_gestao": True}},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{pessoa['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))
    return pessoa


def _processar(agora):
    import relatorios_envio
    db = SessionLocal()
    try:
        relatorios_envio.processar_agendados(db, agora)
    finally:
        db.close()


def test_manager_reads_and_replies_inside_kyndo(client, admin_token):
    autor = create_user(client, admin_token, "conversa_autor")
    gestor = _gestor_com_cargo(client, admin_token, "conversa_gestor")  # sem e-mail: só no Kyndo
    dia = "2026-10-22"
    client.put(f"/relatorios/dia/{dia}", json={"conteudo": "Terminei a vistoria."}, headers=auth(autor["token"]))
    r = client.post(f"/relatorios/dia/{dia}/enviar", json={"para": [gestor["id"]]}, headers=auth(autor["token"]))
    assert r.status_code == 200, r.text

    def pendentes(token):
        return client.get("/me/permissions", headers=auth(token)).json()["relatorios_nao_lidos"]

    assert pendentes(gestor["token"]) == 1
    caixa = client.get("/relatorios/recebidos", headers=auth(gestor["token"])).json()
    assert caixa[0]["autor_nome"] == "conversa_autor" and not caixa[0]["lido"]
    detalhe = client.get(f"/relatorios/recebidos/{autor['id']}/{dia}", headers=auth(gestor["token"])).json()
    assert detalhe["conteudo"] == "Terminei a vistoria." and detalhe["mensagens"] == []
    assert pendentes(gestor["token"]) == 0

    corpo = {"autor_id": autor["id"], "data": dia, "gestor_id": gestor["id"], "texto": "Ótimo, manda as fotos."}
    assert client.post("/relatorios/conversa", json=corpo, headers=auth(gestor["token"])).status_code == 200
    assert pendentes(autor["token"]) == 1
    meu = client.get(f"/relatorios/dia/{dia}", headers=auth(autor["token"])).json()
    conversa = meu["conversas"][0]
    assert conversa["gestor_nome"] == "conversa_gestor" and conversa["lido_em"] and conversa["nao_lidas"] == 1
    assert conversa["mensagens"][0]["texto"] == "Ótimo, manda as fotos."
    assert pendentes(autor["token"]) == 0

    corpo["texto"] = "Enviadas."
    assert client.post("/relatorios/conversa", json=corpo, headers=auth(autor["token"])).status_code == 200
    intruso = create_user(client, admin_token, "conversa_intruso")
    assert client.post("/relatorios/conversa", json=corpo, headers=auth(intruso["token"])).status_code == 403
    assert client.get(f"/relatorios/recebidos/{autor['id']}/{dia}", headers=auth(intruso["token"])).status_code == 404


def test_scheduled_and_automatic_sends(client, admin_token):
    autor = create_user(client, admin_token, "agenda_autor")
    gestor = _gestor_com_cargo(client, admin_token, "agenda_gestor")
    hoje = date.today().isoformat()
    futuro = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    url = f"/relatorios/dia/{hoje}/agendamento"
    assert client.put(url, json={"para": [gestor["id"]], "enviar_em": "2020-01-01T10:00"}, headers=auth(autor["token"])).status_code == 400
    r = client.put(url, json={"para": [gestor["id"]], "enviar_em": futuro}, headers=auth(autor["token"]))
    assert r.json()["agendamento"]["status"] == "pendente"

    # Chegou a hora sem texto: não envia, avisa na tela.
    _processar(datetime.now() + timedelta(hours=3))
    dia = client.get(f"/relatorios/dia/{hoje}", headers=auth(autor["token"])).json()
    assert dia["agendamento"]["status"] == "vazio" and dia["envios"] == []

    # Com texto: envia e o agendamento some.
    client.put(url, json={"para": [gestor["id"]], "enviar_em": futuro}, headers=auth(autor["token"]))
    client.put(f"/relatorios/dia/{hoje}", json={"conteudo": "Dia de campo."}, headers=auth(autor["token"]))
    _processar(datetime.now() + timedelta(hours=3))
    dia = client.get(f"/relatorios/dia/{hoje}", headers=auth(autor["token"])).json()
    assert dia["agendamento"] is None and dia["envios"][0]["origem"] == "agendado"

    # Automático: todo dia, depois da hora; não repete o mesmo texto nem envia duas vezes no dia.
    cfg = {"ativo": True, "dias": list(range(7)), "hora": "00:00", "para": [gestor["id"]], "sem_texto": "nada"}
    r = client.put("/relatorios/automatico", json=cfg, headers=auth(autor["token"]))
    assert r.status_code == 200 and r.json()["para_nomes"] == ["agenda_gestor"]
    import relatorios_envio  # noqa: F401
    from models import RelatorioAutomaticoDB
    db = SessionLocal()
    try:
        db.query(RelatorioAutomaticoDB).filter(RelatorioAutomaticoDB.user_id == autor["id"]).update({"ultimo_envio": None})
        db.commit()
    finally:
        db.close()
    _processar(datetime.now())
    dia = client.get(f"/relatorios/dia/{hoje}", headers=auth(autor["token"])).json()
    assert len(dia["envios"]) == 1  # mesmo texto já enviado pelo agendamento: não repete

    client.put(f"/relatorios/dia/{hoje}", json={"conteudo": "Dia de campo, com fotos."}, headers=auth(autor["token"]))
    _processar(datetime.now())
    assert len(client.get(f"/relatorios/dia/{hoje}", headers=auth(autor["token"])).json()["envios"]) == 1  # já rodou hoje
    assert client.put("/relatorios/automatico", json={**cfg, "dias": []}, headers=auth(autor["token"])).status_code == 400
