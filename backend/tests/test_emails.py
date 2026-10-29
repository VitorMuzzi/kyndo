"""E-mail: redefinição de senha por link, cadastro de e-mail, avisos e resumo de prazos.
Nada sai de verdade — a fixture `caixa` liga o envio e guarda as mensagens."""
import re
from datetime import date, timedelta

import pytest

import email_envio
import notificacoes
from database import SessionLocal
from tests.conftest import auth, create_user, login
from tests.test_reversao import _create_card, _desfazer, _put, _ultimo


@pytest.fixture
def caixa(monkeypatch):
    enviados = []
    monkeypatch.setenv("SMTP_USER", "kyndo@empresa.teste")
    monkeypatch.setenv("SMTP_PASSWORD", "senha-de-app")
    monkeypatch.setenv("KYNDO_URL", "http://kyndo.teste:5176/")
    monkeypatch.setattr(email_envio, "_despachar", enviados.append)
    return enviados


def _para(caixa, email):
    return [m for m in caixa if m["To"] == email]


def _texto(msg):
    return msg.get_body(preferencelist=("plain",)).get_content()


def _com_email(client, admin_token, nome, email):
    r = client.post("/users", json={"nome": nome, "senha": "senha123", "email": email}, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    return login(client, nome, "senha123")


def _modos(client, admin_token, **modos):
    r = client.put("/config/emails", json={"modos": modos}, headers=auth(admin_token))
    assert r.status_code == 200, r.text


# --------------------------------------------------------- esqueci a senha

def test_forgot_password_sends_single_use_link(client, admin_token, caixa):
    _com_email(client, admin_token, "link_por_email", "Link.Por@Email.Teste")
    # Pelo e-mail (sem diferenciar maiúsculas) também acha a pessoa.
    assert client.post("/esqueci-senha", json={"nome": "link.por@email.teste"}).status_code == 200
    client.post("/esqueci-senha", json={"nome": "link_por_email"})  # segundo clique não manda outro
    msgs = _para(caixa, "link.por@email.teste")
    assert len(msgs) == 1
    assert msgs[0]["From"].endswith("<kyndo@empresa.teste>")
    token = re.search(r"http://kyndo\.teste:5176/\?redefinir=(\S+)", _texto(msgs[0])).group(1)
    # Sem pedido pro administrador: o e-mail resolve.
    assert not [p for p in client.get("/pedidos-senha", headers=auth(admin_token)).json() if p["nome"] == "link_por_email"]

    assert client.post("/redefinir-senha", json={"token": token, "nova_senha": "ab"}).status_code == 400
    r = client.post("/redefinir-senha", json={"token": token, "nova_senha": "pelo-link"})
    assert r.status_code == 200, r.text
    assert login(client, "link_por_email", "pelo-link")["senha_temporaria"] is False
    assert client.post("/redefinir-senha", json={"token": token, "nova_senha": "de-novo"}).status_code == 400
    assert any("foi alterada" in m["Subject"] for m in _para(caixa, "link.por@email.teste"))


def test_forgot_password_without_email_falls_back_to_admin(client, admin_token, caixa):
    create_user(client, admin_token, "sem_email_cadastrado")
    client.post("/esqueci-senha", json={"nome": "sem_email_cadastrado"})
    assert not caixa
    assert [p for p in client.get("/pedidos-senha", headers=auth(admin_token)).json() if p["nome"] == "sem_email_cadastrado"]


def test_forgot_password_without_smtp_falls_back_to_admin(client, admin_token):
    _com_email(client, admin_token, "smtp_desligado", "smtp.desligado@email.teste")
    client.post("/esqueci-senha", json={"nome": "smtp_desligado"})
    assert [p for p in client.get("/pedidos-senha", headers=auth(admin_token)).json() if p["nome"] == "smtp_desligado"]


def test_bad_or_expired_token_is_rejected(client):
    assert client.post("/redefinir-senha", json={"token": "inventado", "nova_senha": "qualquer"}).status_code == 400


# ------------------------------------------------------------- cadastro

def test_email_change_rules_and_undo(client, admin_token, maria, caixa):
    pessoa = _com_email(client, admin_token, "troca_email", "antigo@email.teste")
    url = f"/users/{pessoa['id']}/email"
    # A própria pessoa precisa da senha atual.
    assert client.put(url, json={"email": "novo@email.teste"}, headers=auth(pessoa["token"])).status_code == 400
    assert client.put(url, json={"email": "nao-e-email", "senha_atual": "senha123"}, headers=auth(pessoa["token"])).status_code == 400
    assert client.put(url, json={"email": "novo@email.teste", "senha_atual": "senha123"}, headers=auth(pessoa["token"])).status_code == 200
    assert _para(caixa, "antigo@email.teste") and _para(caixa, "novo@email.teste")
    # Outra pessoa só com trocar_senha_outros; e-mail repetido não entra.
    assert client.put(url, json={"email": "da-maria@email.teste"}, headers=auth(maria["token"])).status_code == 403
    outro = _com_email(client, admin_token, "dono_do_email", "ocupado@email.teste")
    assert client.put(url, json={"email": "ocupado@email.teste"}, headers=auth(admin_token)).status_code == 400
    assert outro  # só pra deixar claro de quem é o e-mail ocupado

    # Fica na auditoria e dá pra desfazer.
    log = _ultimo(client, admin_token, "email_alterado")
    assert (log["valor_antigo"], log["valor_novo"]) == ("antigo@email.teste", "novo@email.teste")
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    usuarios = client.get("/users", headers=auth(admin_token)).json()
    assert next(u["email"] for u in usuarios if u["id"] == pessoa["id"]) == "antigo@email.teste"
    # Quem não administra usuários não vê e-mail de ninguém.
    assert all("email" not in u for u in client.get("/users", headers=auth(maria["token"])).json())


# ----------------------------------------------------------------- avisos

def _prefs(client, token, entrega=None, **avisos):
    r = client.put("/me/preferencias", json={"avisos": avisos, "entrega": entrega}, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_new_responsible_gets_email_unless_opted_out(client, admin_token, caixa):
    resp = _com_email(client, admin_token, "vira_responsavel", "responsavel@email.teste")
    card = _create_card(client, admin_token, titulo="Card com aviso")
    _put(client, admin_token, card["id"], responsaveis=["vira_responsavel"])
    msgs = _para(caixa, "responsavel@email.teste")
    assert len(msgs) == 1 and "Card com aviso" in msgs[0]["Subject"]
    assert f"/?card={card['id']}" in _texto(msgs[0])

    # Desligou nas preferências: não recebe mais.
    _prefs(client, resp["token"], responsavel="nenhum")
    _put(client, admin_token, card["id"], responsaveis=["admin"])
    _put(client, admin_token, card["id"], responsaveis=["vira_responsavel"])
    assert len(_para(caixa, "responsavel@email.teste")) == 1

    # Obrigatório passa por cima da preferência; desligado bloqueia todo mundo.
    _modos(client, admin_token, responsavel="obrigatorio")
    _put(client, admin_token, card["id"], responsaveis=["admin"])
    _put(client, admin_token, card["id"], responsaveis=["vira_responsavel"])
    assert len(_para(caixa, "responsavel@email.teste")) == 2
    conta = client.get("/me/conta", headers=auth(resp["token"])).json()
    pref = next(p for p in conta["preferencias"] if p["tipo"] == "responsavel")
    assert (pref["modo"], pref["alcance"]) == ("obrigatorio", "meus")

    _modos(client, admin_token, responsavel="desligado")
    _put(client, admin_token, card["id"], responsaveis=["admin"])
    _put(client, admin_token, card["id"], responsaveis=["vira_responsavel"])
    assert len(_para(caixa, "responsavel@email.teste")) == 2
    _modos(client, admin_token, responsavel="opcional")


def test_follow_and_reach_decide_who_hears_about_a_card(client, admin_token, caixa):
    gestor = _com_email(client, admin_token, "gestor_acompanha", "gestor@email.teste")
    card = _create_card(client, admin_token, titulo="Card do gestor", prioridade="Baixa")
    # Padrão de prioridade é "não receber".
    _put(client, admin_token, card["id"], prioridade="Normal")
    assert not _para(caixa, "gestor@email.teste")

    # "Meus e os que sigo": só depois de seguir.
    _prefs(client, gestor["token"], prioridade="seguidos", prazo_alterado="seguidos")
    _put(client, admin_token, card["id"], prioridade="Alta")
    assert not _para(caixa, "gestor@email.teste")
    r = client.put(f"/cards/{card['id']}/seguir", json={"seguir": True}, headers=auth(gestor["token"]))
    assert r.json() == {"seguindo": True}
    assert next(c for c in client.get("/cards", headers=auth(gestor["token"])).json() if c["id"] == card["id"])["seguindo"]

    # Duas mudanças no mesmo salvamento: um e-mail só, com as duas.
    _put(client, admin_token, card["id"], prioridade="Urgente", prazo="2026-12-31")
    msgs = _para(caixa, "gestor@email.teste")
    assert len(msgs) == 1
    assert "Prioridade: Alta → Urgente" in _texto(msgs[0]) and "31/12/2026" in _texto(msgs[0])

    # Deixou de seguir, mas pediu "todos que vejo": continua recebendo.
    client.put(f"/cards/{card['id']}/seguir", json={"seguir": False}, headers=auth(gestor["token"]))
    _prefs(client, gestor["token"], prioridade="todos")
    _put(client, admin_token, card["id"], prioridade="Baixa")
    assert len(_para(caixa, "gestor@email.teste")) == 2


def test_done_and_new_card_events(client, admin_token, caixa):
    gestor = _com_email(client, admin_token, "gestor_concluidos", "concluidos@email.teste")
    _prefs(client, gestor["token"], concluido="todos", card_criado="todos")
    card = _create_card(client, admin_token, titulo="Card que vai acabar")
    assert "criou o card" in _texto(_para(caixa, "concluidos@email.teste")[0])
    _put(client, admin_token, card["id"], status="col-4")  # coluna CONCLUÍDO (auto_concluido)
    assert "Card concluído" in _texto(_para(caixa, "concluidos@email.teste")[-1])


def test_daily_delivery_queues_and_sends_one_digest(client, admin_token, caixa):
    pessoa = _com_email(client, admin_token, "prefere_resumo", "resumo@email.teste")
    _prefs(client, pessoa["token"], entrega="resumo", prioridade="todos")
    card = _create_card(client, admin_token, titulo="Card no resumo", prioridade="Baixa")
    _put(client, admin_token, card["id"], prioridade="Alta")
    _put(client, admin_token, card["id"], prioridade="Urgente")
    assert not _para(caixa, "resumo@email.teste")
    db = SessionLocal()
    try:
        notificacoes.enviar_fila_de_avisos(db)
    finally:
        db.close()
    msgs = _para(caixa, "resumo@email.teste")
    assert len(msgs) == 1
    assert "Baixa → Alta" in _texto(msgs[0]) and "Alta → Urgente" in _texto(msgs[0])


def test_suggestion_author_hears_the_decision(client, admin_token, caixa):
    autora = _com_email(client, admin_token, "autora_sugestao", "autora@email.teste")
    card = _create_card(client, admin_token, titulo="Card com sugestao decidida", status="col-1")
    sug = client.post(f"/cards/{card['id']}/suggestions", json={"texto": "Trocar fornecedor", "identificacao": "Autora"},
                      headers=auth(autora["token"])).json()
    r = client.patch(f"/cards/{card['id']}/suggestions/{sug['id']}", json={"status": "rejeitada", "motivo_recusa": "Sem verba"},
                   headers=auth(admin_token))
    assert r.status_code == 200, r.text
    msgs = _para(caixa, "autora@email.teste")
    assert len(msgs) == 1 and "Sem verba" in _texto(msgs[0])


def test_weekly_team_summary_for_managers(client, admin_token, caixa):
    gestor = _com_email(client, admin_token, "gestor_semanal", "semanal@email.teste")
    cargo = client.post("/roles", json={"nome": "Gestao semanal", "permissoes": {"acessar_gestao": True}},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{gestor['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))
    gestor = login(client, "gestor_semanal", "senha123")
    tipos = {p["tipo"] for p in client.get("/me/conta", headers=auth(gestor["token"])).json()["preferencias"]}
    assert "resumo_semanal" in tipos
    _prefs(client, gestor["token"], resumo_semanal="meus")
    db = SessionLocal()
    try:
        notificacoes.enviar_resumo_semanal(db)
    finally:
        db.close()
    msgs = _para(caixa, "semanal@email.teste")
    assert len(msgs) == 1 and "Horas registradas" in _texto(msgs[0])


def test_comment_and_suggestion_notify(client, admin_token, caixa):
    _com_email(client, admin_token, "recebe_comentario", "comentario@email.teste")
    decisor = _com_email(client, admin_token, "decide_sugestao", "decisor@email.teste")
    cargo = client.post("/roles", json={"nome": "Decide sugestoes email", "permissoes": {"decidir_sugestoes": True}},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{decisor['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))

    card = _create_card(client, admin_token, titulo="Card comentado")
    _put(client, admin_token, card["id"], responsaveis=["recebe_comentario"])
    caixa.clear()
    _put(client, admin_token, card["id"], comentarios=[{"id": "c-email", "texto": "Olha isso aqui", "autor": "admin"}])
    msgs = _para(caixa, "comentario@email.teste")
    assert len(msgs) == 1 and "Olha isso aqui" in _texto(msgs[0])

    r = client.post(f"/cards/{card['id']}/suggestions", json={"texto": "Mudar a cor", "identificacao": "Fulano"},
                    headers=auth(admin_token))
    assert r.status_code == 200, r.text
    msgs = _para(caixa, "decisor@email.teste")
    assert len(msgs) == 1 and "Mudar a cor" in _texto(msgs[0])


def test_daily_deadline_digest(client, admin_token, caixa):
    _com_email(client, admin_token, "tem_prazo", "prazo@email.teste")
    ontem = (date.today() - timedelta(days=1)).isoformat()
    longe = (date.today() + timedelta(days=30)).isoformat()
    _create_card(client, admin_token, titulo="Venceu ontem", prazo=ontem, responsaveis=["tem_prazo"])
    _create_card(client, admin_token, titulo="Ainda longe", prazo=longe, responsaveis=["tem_prazo"])
    caixa.clear()
    db = SessionLocal()
    try:
        notificacoes.enviar_resumo_de_prazos(db)
    finally:
        db.close()
    msgs = _para(caixa, "prazo@email.teste")
    assert len(msgs) == 1
    assert "Venceu ontem" in _texto(msgs[0]) and "Ainda longe" not in _texto(msgs[0])


# --------------------------------------------------------- configuração

def test_email_config_needs_permission_and_can_be_undone(client, admin_token, maria):
    assert client.get("/config/emails", headers=auth(maria["token"])).status_code == 403
    assert client.put("/config/emails", json={"modos": {"prazo": "desligado"}}, headers=auth(maria["token"])).status_code == 403
    assert client.put("/config/emails", json={"modos": {"prazo": "talvez"}}, headers=auth(admin_token)).status_code == 400

    _modos(client, admin_token, prazo="obrigatorio")
    log = _ultimo(client, admin_token, "config_emails_alterada")
    assert _desfazer(client, admin_token, log["id"]).status_code == 200
    tipos = client.get("/config/emails", headers=auth(admin_token)).json()["tipos"]
    assert next(t["modo"] for t in tipos if t["tipo"] == "prazo") == "opcional"


def test_test_email_reports_missing_config(client, admin_token):
    r = client.post("/config/emails/teste", headers=auth(admin_token))
    assert r.status_code == 400


def _envelhecer_card(card_id, dias):
    """Empurra toda a atividade registrada do card `dias` dias pro passado."""
    from datetime import datetime
    from models import AuditLogDB
    db = SessionLocal()
    try:
        for log in db.query(AuditLogDB).filter(AuditLogDB.card_id == card_id).all():
            log.data = (datetime.fromisoformat(log.data) - timedelta(days=dias)).isoformat()
        db.commit()
    finally:
        db.close()


def _rodar_parados():
    db = SessionLocal()
    try:
        return notificacoes.enviar_cards_parados(db)
    finally:
        db.close()


def _parados(caixa, email):
    return [m for m in _para(caixa, email) if "parado" in m["Subject"] and "Card esquecido" in _texto(m)]


def test_stale_card_warns_responsibles_and_interested_managers(client, admin_token, caixa):
    resp = _com_email(client, admin_token, "resp_parado", "resp.parado@email.teste")
    gestor = _com_email(client, admin_token, "gestor_parado", "gestor.parado@email.teste")
    _com_email(client, admin_token, "alheio_parado", "alheio.parado@email.teste")
    card = _create_card(client, admin_token, titulo="Card esquecido")
    _put(client, admin_token, card["id"], responsaveis=["resp_parado"])

    # Mexido há pouco: ninguém é avisado.
    _rodar_parados()
    assert not _parados(caixa, "resp.parado@email.teste")

    # Gestor pediu "todos que vejo"; o responsável fica no padrão ("meus").
    _prefs(client, gestor["token"], parado="todos")
    _envelhecer_card(card["id"], 4)
    _rodar_parados()
    for email in ("resp.parado@email.teste", "gestor.parado@email.teste"):
        assert len(_parados(caixa, email)) == 1, email
    assert "responsável: resp_parado" in _texto(_parados(caixa, "gestor.parado@email.teste")[0])
    assert not _para(caixa, "alheio.parado@email.teste")

    # A mesma parada não é avisada duas vezes...
    _rodar_parados()
    assert len(_parados(caixa, "resp.parado@email.teste")) == 1

    # ...mas se alguém mexer e o card parar de novo, avisa de novo.
    _put(client, admin_token, card["id"], prioridade="Alta")
    _rodar_parados()
    assert len(_parados(caixa, "resp.parado@email.teste")) == 1
    _envelhecer_card(card["id"], 4)
    _rodar_parados()
    assert len(_parados(caixa, "resp.parado@email.teste")) == 2


def test_timer_left_running_for_12_hours_warns_its_owner_once(client, admin_token, caixa):
    from datetime import datetime
    from models import TimeEntryDB
    pessoa = _com_email(client, admin_token, "esquece_crono", "esquece.crono@email.teste")
    card = _create_card(client, admin_token, titulo="Card do cronometro esquecido")
    assert client.post(f"/cards/{card['id']}/tempo/iniciar", json={}, headers=auth(pessoa["token"])).status_code == 200

    def rodar():
        db = SessionLocal()
        try:
            notificacoes.avisar_cronometros_longos(db)
        finally:
            db.close()

    def recuar(horas):
        db = SessionLocal()
        try:
            e = db.query(TimeEntryDB).filter(TimeEntryDB.user_id == pessoa["id"], TimeEntryDB.fim == None).first()  # noqa: E711
            e.inicio = (datetime.now() - timedelta(hours=horas)).isoformat()
            db.commit()
        finally:
            db.close()

    recuar(11)
    rodar()
    assert not _para(caixa, "esquece.crono@email.teste")
    recuar(13)
    rodar()
    rodar()
    msgs = _para(caixa, "esquece.crono@email.teste")
    assert len(msgs) == 1 and "Card do cronometro esquecido" in _texto(msgs[0])
    client.post("/tempo/parar", headers=auth(pessoa["token"]))
