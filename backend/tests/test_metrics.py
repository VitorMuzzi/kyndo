import uuid

from tests.conftest import auth, login


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card metricas", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


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
    r = client.put(f"/cards/{card['id']}", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return {**payload, "id": card["id"]}


def _metrics(client, token):
    r = client.get("/metrics", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_metrics_counts_cards_by_column_and_priority(client, admin_token):
    before = _metrics(client, admin_token)
    base_col1 = next(c["total"] for c in before["cards_por_coluna"] if c["coluna_id"] == "col-1")

    _create_card(client, admin_token, "admin", prioridade="Urgente")

    after = _metrics(client, admin_token)
    col1 = next(c["total"] for c in after["cards_por_coluna"] if c["coluna_id"] == "col-1")
    assert col1 == base_col1 + 1
    assert after["cards_por_prioridade"]["Urgente"] >= 1


def test_metrics_flags_overdue_cards_but_not_completed_ones(client, admin_token):
    atrasado = _create_card(client, admin_token, "admin", prazo="2000-01-01")
    concluido_atrasado = _create_card(client, admin_token, "admin", prazo="2000-01-01")
    _put_card(client, admin_token, concluido_atrasado, status="col-4")  # col-4 = CONCLUÍDO (auto_concluido)

    metrics = _metrics(client, admin_token)
    atrasado_ids = {a["id"] for a in metrics["cards_atrasados"]}
    assert atrasado["id"] in atrasado_ids
    assert concluido_atrasado["id"] not in atrasado_ids


def test_metrics_completion_time_and_responsavel_breakdown(client, admin_token):
    card = _create_card(client, admin_token, "admin", responsaveis=["admin"])
    _put_card(client, admin_token, card, status="col-4", responsaveis=["admin"])

    metrics = _metrics(client, admin_token)
    assert metrics["tempo_medio_conclusao_dias"] is not None
    assert metrics["tempo_medio_conclusao_dias"] >= 0

    admin_row = next(r for r in metrics["cards_por_responsavel"] if r["nome"] == "admin")
    assert admin_row["total"] >= 1


def test_metrics_suggestion_stats_by_decisor(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    sug = client.post(f"/cards/{card['id']}/suggestions", json={"texto": "sugestao", "identificacao": "Maria"}, headers=auth(maria["token"])).json()
    r = client.patch(
        f"/cards/{card['id']}/suggestions/{sug['id']}", json={"status": "aceita", "prazo_entrega": "2026-01-01"}, headers=auth(admin_token),
    )
    assert r.status_code == 200

    metrics = _metrics(client, admin_token)
    assert metrics["sugestoes"]["aceita"] >= 1
    admin_decisor = next(d for d in metrics["sugestoes_por_decisor"] if d["usuario"] == "admin")
    assert admin_decisor["aceitas"] >= 1


def test_metrics_respects_column_visibility(client, admin_token, joao):
    _create_card(client, admin_token, "admin", status="col-1")

    role = client.post(
        "/roles",
        json={"nome": f"SoCol2metrics-{uuid.uuid4().hex[:6]}", "cor": "#123456", "permissoes": {}, "colunas_restritas": True, "colunas_visiveis": ["col-2"]},
        headers=auth(admin_token),
    ).json()
    joao_id = next(u["id"] for u in client.get("/users", headers=auth(admin_token)).json() if u["nome"] == joao["nome"])
    assert client.put(f"/users/{joao_id}/roles", json={"role_ids": [role["id"]]}, headers=auth(admin_token)).status_code == 200
    joao_token = login(client, joao["nome"], "senha123")["token"]

    metrics = _metrics(client, joao_token)
    assert all(c["coluna_id"] == "col-2" for c in metrics["cards_por_coluna"])
