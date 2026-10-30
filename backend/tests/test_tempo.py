from database import SessionLocal
from models import TimeEntryDB
from tests.conftest import auth, create_user


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card cronometrado", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _iniciar(client, token, card_id, item_id=None):
    return client.post(f"/cards/{card_id}/tempo/iniciar", json={"item_id": item_id}, headers=auth(token))


def _atual(client, token):
    r = client.get("/tempo/atual", headers=auth(token))
    assert r.status_code == 200
    return r.json()


def _tempo(client, token, card_id):
    r = client.get(f"/cards/{card_id}/tempo", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _recuar_inicio(entry_id, segundos):
    """Empurra o início pro passado pra ter duração mensurável sem sleep."""
    from datetime import datetime, timedelta
    db = SessionLocal()
    try:
        e = db.query(TimeEntryDB).filter(TimeEntryDB.id == entry_id).first()
        e.inicio = (datetime.fromisoformat(e.inicio) - timedelta(seconds=segundos)).isoformat()
        db.commit()
    finally:
        db.close()


def test_start_and_stop_timer(client, admin_token):
    pessoa = create_user(client, admin_token, "crono_basico")
    card = _create_card(client, pessoa["token"], pessoa["nome"])
    r = _iniciar(client, pessoa["token"], card["id"])
    assert r.status_code == 200, r.text
    atual = _atual(client, pessoa["token"])
    assert atual["card_id"] == card["id"]
    assert atual["card_titulo"] == "Card cronometrado"

    _recuar_inicio(atual["id"], 90)
    assert client.post("/tempo/parar", headers=auth(pessoa["token"])).status_code == 200
    assert _atual(client, pessoa["token"]) is None

    tempo = _tempo(client, pessoa["token"], card["id"])
    assert 90 <= tempo["total_segundos"] < 100
    assert tempo["meu_total_segundos"] == tempo["total_segundos"]
    assert len(tempo["registros"]) == 1 and tempo["registros"][0]["fim"] is not None


def test_starting_another_timer_stops_the_previous_one(client, admin_token):
    pessoa = create_user(client, admin_token, "crono_troca")
    a = _create_card(client, pessoa["token"], pessoa["nome"], titulo="A")
    b = _create_card(client, pessoa["token"], pessoa["nome"], titulo="B")
    _iniciar(client, pessoa["token"], a["id"])
    _iniciar(client, pessoa["token"], b["id"])

    assert _atual(client, pessoa["token"])["card_id"] == b["id"]
    db = SessionLocal()
    try:
        rodando = db.query(TimeEntryDB).filter(TimeEntryDB.user_id == pessoa["id"], TimeEntryDB.fim == None).all()  # noqa: E711
        assert [e.card_id for e in rodando] == [b["id"]]
    finally:
        db.close()


def test_timer_on_a_step_counts_per_step(client, admin_token):
    pessoa = create_user(client, admin_token, "crono_etapa")
    card = _create_card(client, admin_token, "admin", checklist=[
        {"id": "e-1", "texto": "Etapa um", "concluido": False, "subetapas": [
            {"id": "s-1", "texto": "Sub", "concluido": False}]},
    ])
    atual = _iniciar(client, pessoa["token"], card["id"], item_id="s-1").json()
    assert atual["item_id"] == "s-1"
    assert atual["etapa_texto"] == "Sub"
    _recuar_inicio(atual["id"], 60)
    client.post("/tempo/parar", headers=auth(pessoa["token"]))

    assert _tempo(client, pessoa["token"], card["id"])["por_etapa"]["s-1"] >= 60


def test_timer_accepts_step_not_saved_yet(client, admin_token):
    # A etapa acabou de ser criada na tela e só chega no "Salvar Tudo".
    pessoa = create_user(client, admin_token, "crono_etapa_nova")
    card = _create_card(client, admin_token, "admin")
    atual = _iniciar(client, pessoa["token"], card["id"], item_id="nova-1").json()
    assert atual["item_id"] == "nova-1"
    assert atual["etapa_texto"] is None

    payload = {"titulo": card["titulo"], "status": card["status"], "autor": card["autor"],
               "checklist": [{"id": "nova-1", "texto": "Etapa nova", "concluido": False}]}
    assert client.put(f"/cards/{card['id']}", json=payload, headers=auth(admin_token)).status_code == 200
    assert _atual(client, pessoa["token"])["etapa_texto"] == "Etapa nova"


def test_everyone_sees_time_per_person_but_entries_need_permission(client, admin_token):
    ana = create_user(client, admin_token, "crono_ana")
    bia = create_user(client, admin_token, "crono_bia")
    card = _create_card(client, admin_token, "admin")
    for p in (ana, bia):
        atual = _iniciar(client, p["token"], card["id"]).json()
        _recuar_inicio(atual["id"], 30)
        client.post("/tempo/parar", headers=auth(p["token"]))

    visao_ana = _tempo(client, ana["token"], card["id"])
    assert visao_ana["pode_ver_equipe"] is False
    # Quanto cada um trabalhou é visível a todos; quando, só os próprios.
    assert {p["usuario"] for p in visao_ana["por_pessoa"]} == {"crono_ana", "crono_bia"}
    assert {r["usuario"] for r in visao_ana["registros"]} == {"crono_ana"}
    # O total do card continua sendo de todo mundo.
    assert visao_ana["total_segundos"] >= 60

    visao_admin = _tempo(client, admin_token, card["id"])
    assert visao_admin["pode_ver_equipe"] is True
    assert {r["usuario"] for r in visao_admin["registros"]} == {"crono_ana", "crono_bia"}


def test_timer_respects_column_visibility(client, admin_token):
    restrito = create_user(client, admin_token, "crono_restrito")
    cargo = client.post("/roles", json={"nome": "So col-1 crono", "permissoes": {},
                                        "colunas_restritas": True, "colunas_visiveis": ["col-1"]},
                        headers=auth(admin_token)).json()
    client.put(f"/users/{restrito['id']}/roles", json={"role_ids": [cargo["id"]]}, headers=auth(admin_token))
    escondido = _create_card(client, admin_token, "admin", status="col-2")

    assert _iniciar(client, restrito["token"], escondido["id"]).status_code == 404
    assert client.get(f"/cards/{escondido['id']}/tempo", headers=auth(restrito["token"])).status_code == 404


def test_only_own_entry_can_be_deleted(client, admin_token):
    dono = create_user(client, admin_token, "crono_dono")
    outro = create_user(client, admin_token, "crono_outro")
    card = _create_card(client, admin_token, "admin")
    entry_id = _iniciar(client, dono["token"], card["id"]).json()["id"]

    assert client.delete(f"/tempo/{entry_id}", headers=auth(outro["token"])).status_code == 403
    assert client.delete(f"/tempo/{entry_id}", headers=auth(dono["token"])).status_code == 200
    assert _atual(client, dono["token"]) is None


def test_finished_entry_can_be_linked_to_a_step_later(client, admin_token):
    dono = create_user(client, admin_token, "crono_vincula")
    outro = create_user(client, admin_token, "crono_vincula_outro")
    card = _create_card(client, admin_token, "admin", checklist=[
        {"id": "v-1", "texto": "Etapa", "concluido": False, "subetapas": [
            {"id": "v-1a", "texto": "Sub", "concluido": False}]},
    ])
    entry_id = _iniciar(client, dono["token"], card["id"]).json()["id"]
    _recuar_inicio(entry_id, 120)
    client.post("/tempo/parar", headers=auth(dono["token"]))
    assert _tempo(client, dono["token"], card["id"])["por_etapa"] == {}

    url = f"/tempo/{entry_id}"
    assert client.put(url, json={"item_id": "v-1a"}, headers=auth(outro["token"])).status_code == 403
    assert client.put(url, json={"item_id": "v-1a"}, headers=auth(dono["token"])).status_code == 200
    tempo = _tempo(client, dono["token"], card["id"])
    assert tempo["por_etapa"]["v-1a"] >= 120
    assert tempo["registros"][0]["item_id"] == "v-1a"

    # Voltar para o card inteiro.
    assert client.put(url, json={"item_id": None}, headers=auth(dono["token"])).status_code == 200
    assert _tempo(client, dono["token"], card["id"])["por_etapa"] == {}


def test_deleting_card_removes_its_time_entries(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    _iniciar(client, admin_token, card["id"])
    assert client.delete(f"/cards/{card['id']}", headers=auth(admin_token)).status_code == 200
    assert _atual(client, admin_token) is None


def test_merge_moves_time_entries_to_destination(client, admin_token):
    origem = _create_card(client, admin_token, "admin", titulo="Origem crono")
    destino = _create_card(client, admin_token, "admin", titulo="Destino crono")
    entry_id = _iniciar(client, admin_token, origem["id"]).json()["id"]
    client.post("/tempo/parar", headers=auth(admin_token))

    r = client.post(f"/cards/{origem['id']}/merge", json={"destino_id": destino["id"], "confirmacao": "CONFIRMO"},
                    headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["resumo"]["registros_tempo"] == 1
    assert [x["id"] for x in _tempo(client, admin_token, destino["id"])["registros"]] == [entry_id]


def test_superadmin_gets_permissions_added_later(client):
    r = client.post("/login", json={"nome": "admin", "senha": "admin"})
    assert "ver_tempo_equipe" in r.json()["permissions"]
