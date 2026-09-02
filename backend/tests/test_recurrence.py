from datetime import datetime, timedelta

from tests.conftest import auth


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card recorrente teste", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


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
        "recorrente": card.get("recorrente", False), "recorrencia_dias": card.get("recorrencia_dias"),
    }
    payload.update(overrides)
    r = client.put(f"/cards/{card['id']}", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return _get_card(client, token, card["id"])


def _audit_log(client, token, card_id):
    r = client.get(f"/audit-log?card_id={card_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _force_due(card_id):
    """Backdates a card's next-reset date directly in the DB so the lazy
    on-GET recurrence check treats it as due, without waiting real time."""
    from database import SessionLocal
    from models import CardDB

    db = SessionLocal()
    try:
        db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
        db_card.recorrencia_proximo_reset = (datetime.now() - timedelta(days=1)).isoformat()
        db.commit()
    finally:
        db.close()


def test_creating_card_with_recurrence_arms_it(client, admin_token):
    before = datetime.now()
    card = _create_card(client, admin_token, "admin", recorrente=True, recorrencia_dias=7)
    assert card["recorrente"] is True
    assert card["recorrencia_dias"] == 7
    assert card["recorrencia_coluna_reset"] == "col-1"
    assert datetime.fromisoformat(card["recorrencia_proximo_reset"]) > before + timedelta(days=6)


def test_creating_card_without_recurrence_leaves_fields_empty(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    assert card["recorrente"] is False
    assert card["recorrencia_coluna_reset"] is None
    assert card["recorrencia_proximo_reset"] is None


def test_enabling_recurrence_requires_gerenciar_etapas(client, admin_token, maria):
    card = _create_card(client, maria["token"], maria["nome"])

    blocked = _put_card(client, maria["token"], card, recorrente=True, recorrencia_dias=7)
    assert blocked["recorrente"] is False

    allowed = _put_card(client, admin_token, card, recorrente=True, recorrencia_dias=7)
    assert allowed["recorrente"] is True
    assert allowed["recorrencia_coluna_reset"] == "col-1"


def test_disabling_recurrence_clears_reset_fields(client, admin_token):
    card = _create_card(client, admin_token, "admin", recorrente=True, recorrencia_dias=3)
    updated = _put_card(client, admin_token, card, recorrente=False, recorrencia_dias=None)
    assert updated["recorrente"] is False
    assert updated["recorrencia_coluna_reset"] is None
    assert updated["recorrencia_proximo_reset"] is None


def test_due_recurrence_resets_checklist_and_returns_to_original_column(client, admin_token):
    step = {"id": "rec-step-1", "texto": "Regar as plantas", "concluido": True, "concluidoPor": "admin"}
    card = _create_card(client, admin_token, "admin", checklist=[step])
    card = _put_card(client, admin_token, card, recorrente=True, recorrencia_dias=1)

    # move it forward like the auto_andamento/auto_concluido logic would, then let it come due
    card = _put_card(client, admin_token, card, status="col-4")
    _force_due(card["id"])

    reopened = _get_card(client, admin_token, card["id"])
    assert reopened["status"] == "col-1"
    item = next(i for i in reopened["checklist"] if i["id"] == "rec-step-1")
    assert item["concluido"] is False
    assert item["concluidoPor"] is None
    assert datetime.fromisoformat(reopened["recorrencia_proximo_reset"]) > datetime.now()

    logs = _audit_log(client, admin_token, card["id"])
    assert any(l["acao"] == "tarefa_recorrente_reiniciada" for l in logs)
