import io

from tests.conftest import auth


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card teste", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _get_card(client, token, card_id):
    r = client.get("/cards", headers=auth(token))
    assert r.status_code == 200
    return next((c for c in r.json() if c["id"] == card_id), None)


def _merge(client, token, origem_id, destino_id, confirmacao="CONFIRMO"):
    return client.post(
        f"/cards/{origem_id}/merge",
        json={"destino_id": destino_id, "confirmacao": confirmacao},
        headers=auth(token),
    )


def _etapa(iid, texto, subetapas=None):
    item = {"id": iid, "texto": texto, "concluido": False, "criador": "admin"}
    if subetapas is not None:
        item["subetapas"] = subetapas
    return item


# --- portões de acesso -------------------------------------------------------

def test_merge_requires_admin(client, admin_token, maria):
    origem = _create_card(client, admin_token, "admin")
    destino = _create_card(client, admin_token, "admin")
    r = _merge(client, maria["token"], origem["id"], destino["id"])
    assert r.status_code == 403
    # nada aconteceu
    assert _get_card(client, admin_token, origem["id"]) is not None


def test_merge_requires_exact_confirmation_word(client, admin_token):
    origem = _create_card(client, admin_token, "admin")
    destino = _create_card(client, admin_token, "admin")

    for palavra in ["", "confirma", "SIM", "CONFIRMAR", "CONFIRM"]:
        r = _merge(client, admin_token, origem["id"], destino["id"], confirmacao=palavra)
        assert r.status_code == 400, f"aceitou {palavra!r}"

    assert _get_card(client, admin_token, origem["id"]) is not None


def test_confirmation_tolerates_case_and_whitespace(client, admin_token):
    origem = _create_card(client, admin_token, "admin")
    destino = _create_card(client, admin_token, "admin")
    r = _merge(client, admin_token, origem["id"], destino["id"], confirmacao="  confirmo \n")
    assert r.status_code == 200, r.text


def test_cannot_merge_card_into_itself(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    r = _merge(client, admin_token, card["id"], card["id"])
    assert r.status_code == 400
    assert _get_card(client, admin_token, card["id"]) is not None


def test_merge_with_unknown_destination_is_404(client, admin_token):
    origem = _create_card(client, admin_token, "admin")
    r = _merge(client, admin_token, origem["id"], "card-nao-existe")
    assert r.status_code == 404
    assert _get_card(client, admin_token, origem["id"]) is not None


# --- conteúdo do próprio card ------------------------------------------------

def test_source_card_disappears_and_content_moves(client, admin_token):
    origem = _create_card(
        client, admin_token, "admin",
        titulo="Origem", descricao="descricao da origem",
        checklist=[_etapa("sub-o1", "etapa da origem")],
        comentarios=[{"id": "msg-o1", "autor": "admin", "texto": "comentario origem", "data": "01/01"}],
        responsaveis=["admin", "maria"],
    )
    destino = _create_card(
        client, admin_token, "admin",
        titulo="Destino", descricao="descricao do destino",
        checklist=[_etapa("sub-d1", "etapa do destino")],
        comentarios=[{"id": "msg-d1", "autor": "admin", "texto": "comentario destino", "data": "01/01"}],
        responsaveis=["admin"],
    )

    r = _merge(client, admin_token, origem["id"], destino["id"])
    assert r.status_code == 200, r.text

    assert _get_card(client, admin_token, origem["id"]) is None

    d = _get_card(client, admin_token, destino["id"])
    textos = [i["texto"] for i in d["checklist"]]
    assert textos == ["etapa do destino", "etapa da origem"]
    assert [c["texto"] for c in d["comentarios"]] == ["comentario destino", "comentario origem"]
    assert sorted(d["responsaveis"]) == ["admin", "maria"]
    assert "descricao do destino" in d["descricao"]
    assert "descricao da origem" in d["descricao"]
    assert "Origem" in d["descricao"]  # bloco de proveniência cita o título


def test_source_subetapas_survive_at_same_level(client, admin_token):
    origem = _create_card(
        client, admin_token, "admin",
        checklist=[_etapa("sub-x", "pai da origem", subetapas=[
            {"id": "sub-x-1", "texto": "filha", "concluido": False},
        ])],
    )
    destino = _create_card(client, admin_token, "admin", checklist=[_etapa("sub-y", "etapa destino")])

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    d = _get_card(client, admin_token, destino["id"])
    assert [i["texto"] for i in d["checklist"]] == ["etapa destino", "pai da origem"]
    pai = d["checklist"][1]
    assert [s["texto"] for s in pai["subetapas"]] == ["filha"]


def test_colliding_checklist_ids_are_reidentified(client, admin_token):
    # Dois cards com a mesma id de etapa: sem remapear, ItemSeenDB
    # (chave card_id+item_id) fundiria o "lido" de etapas diferentes.
    origem = _create_card(client, admin_token, "admin", checklist=[_etapa("sub-igual", "etapa origem")])
    destino = _create_card(client, admin_token, "admin", checklist=[_etapa("sub-igual", "etapa destino")])

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    d = _get_card(client, admin_token, destino["id"])
    ids = [i["id"] for i in d["checklist"]]
    assert len(ids) == 2
    assert len(set(ids)) == 2, f"ids colidiram: {ids}"
    assert [i["texto"] for i in d["checklist"]] == ["etapa destino", "etapa origem"]


def test_colliding_comment_ids_are_reidentified(client, admin_token):
    c = {"id": "msg-igual", "autor": "admin", "texto": "x", "data": "01/01"}
    origem = _create_card(client, admin_token, "admin", comentarios=[{**c, "texto": "da origem"}])
    destino = _create_card(client, admin_token, "admin", comentarios=[{**c, "texto": "do destino"}])

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    d = _get_card(client, admin_token, destino["id"])
    ids = [x["id"] for x in d["comentarios"]]
    assert len(set(ids)) == 2, f"ids colidiram: {ids}"


# --- campos de vaga única ----------------------------------------------------

def test_empty_destination_fields_inherit_from_source(client, admin_token):
    origem = _create_card(client, admin_token, "admin", prazo="2026-12-01",
                          github_url="https://github.com/a/b")
    destino = _create_card(client, admin_token, "admin", prazo="", github_url="")

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    d = _get_card(client, admin_token, destino["id"])
    assert d["prazo"] == "2026-12-01"
    assert d["github_url"] == "https://github.com/a/b"


def test_filled_destination_fields_win_and_source_value_is_recorded(client, admin_token):
    origem = _create_card(client, admin_token, "admin", prazo="2026-12-01",
                          github_url="https://github.com/origem/repo", prioridade="Urgente")
    destino = _create_card(client, admin_token, "admin", prazo="2026-11-01",
                           github_url="https://github.com/destino/repo", prioridade="Normal")

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    d = _get_card(client, admin_token, destino["id"])
    assert d["prazo"] == "2026-11-01"
    assert d["github_url"] == "https://github.com/destino/repo"
    assert d["prioridade"] == "Normal"
    # nada se perde: o valor descartado fica registrado na descrição
    assert "2026-12-01" in d["descricao"]
    assert "https://github.com/origem/repo" in d["descricao"]
    assert "Urgente" in d["descricao"]


def test_recurrence_transfers_only_into_a_non_recurring_destination(client, admin_token):
    origem = _create_card(client, admin_token, "admin", recorrente=True, recorrencia_dias=7)
    destino = _create_card(client, admin_token, "admin")

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    d = _get_card(client, admin_token, destino["id"])
    assert d["recorrente"] is True
    assert d["recorrencia_dias"] == 7


def test_recurrence_conflict_is_recorded_not_silently_dropped(client, admin_token):
    origem = _create_card(client, admin_token, "admin", recorrente=True, recorrencia_dias=3)
    destino = _create_card(client, admin_token, "admin", recorrente=True, recorrencia_dias=30)

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    d = _get_card(client, admin_token, destino["id"])
    assert d["recorrencia_dias"] == 30  # destino manda
    assert "3 dia(s)" in d["descricao"]


# --- itens vinculados --------------------------------------------------------

def test_attachments_notes_drawings_and_suggestions_follow_the_merge(client, admin_token, maria):
    origem = _create_card(client, admin_token, "admin")
    destino = _create_card(client, admin_token, "admin")

    up = client.post(
        f"/cards/{origem['id']}/attachments",
        files={"file": ("nota.txt", io.BytesIO(b"conteudo"), "text/plain")},
        headers=auth(admin_token),
    )
    assert up.status_code == 200, up.text

    nota = client.post("/notes", json={"titulo": "Anotacao", "conteudo": "texto",
                                       "card_id": origem["id"]}, headers=auth(admin_token))
    assert nota.status_code == 200, nota.text

    mapa = client.post("/notes", json={"titulo": "Mapa mental", "tipo": "canvas",
                                       "canvas_data": {"nodes": []}, "card_id": origem["id"]},
                       headers=auth(admin_token))
    assert mapa.status_code == 200, mapa.text

    desenho = client.post("/drawings", json={"titulo": "Desenho", "data": "x",
                                             "card_id": origem["id"]}, headers=auth(admin_token))
    assert desenho.status_code == 200, desenho.text

    sug = client.post(f"/cards/{origem['id']}/suggestions",
                      json={"texto": "sugestao", "identificacao": "maria"},
                      headers=auth(maria["token"]))
    assert sug.status_code == 200, sug.text

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    anexos = client.get(f"/cards/{destino['id']}/attachments", headers=auth(admin_token)).json()
    assert [a["nome_original"] for a in anexos] == ["nota.txt"]

    notas = client.get(f"/notes?card_id={destino['id']}", headers=auth(admin_token)).json()
    assert sorted(n["titulo"] for n in notas) == ["Anotacao", "Mapa mental"]

    desenhos = client.get(f"/drawings?card_id={destino['id']}", headers=auth(admin_token)).json()
    assert [d["titulo"] for d in desenhos] == ["Desenho"]

    sugestoes = client.get(f"/cards/{destino['id']}/suggestions", headers=auth(admin_token)).json()
    assert [s["texto"] for s in sugestoes] == ["sugestao"]


def test_merge_response_reports_what_moved(client, admin_token):
    origem = _create_card(client, admin_token, "admin", checklist=[_etapa("sub-r1", "a")])
    destino = _create_card(client, admin_token, "admin")

    r = _merge(client, admin_token, origem["id"], destino["id"])
    assert r.status_code == 200
    body = r.json()
    assert body["destino_id"] == destino["id"]
    assert body["resumo"]["etapas"] == 1
    assert set(body["resumo"]) == {
        "etapas", "comentarios", "anexos", "sugestoes", "notas", "desenhos", "eventos_log",
    }


# --- badge e auditoria -------------------------------------------------------

def test_merge_badges_others_but_not_the_admin_who_merged(client, admin_token, joao):
    origem = _create_card(client, admin_token, "admin")
    destino = _create_card(client, admin_token, "admin")
    client.post(f"/cards/{destino['id']}/seen", headers=auth(joao["token"]))

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    assert _get_card(client, admin_token, destino["id"])["nao_visto"] is False
    assert _get_card(client, joao["token"], destino["id"])["nao_visto"] is True


def test_merge_is_logged_and_source_history_follows_the_survivor(client, admin_token):
    origem = _create_card(client, admin_token, "admin", titulo="Vai sumir")
    destino = _create_card(client, admin_token, "admin", titulo="Sobrevivente")

    assert _merge(client, admin_token, origem["id"], destino["id"]).status_code == 200

    log = client.get(f"/audit-log?card_id={destino['id']}", headers=auth(admin_token))
    assert log.status_code == 200, log.text
    entradas = log.json()

    fusao = [e for e in entradas if e["acao"] == "card_fundido"]
    assert len(fusao) == 1
    assert fusao[0]["valor_antigo"] == "Vai sumir"
    assert fusao[0]["valor_novo"] == "Sobrevivente"

    # a criação da origem passou a viver no histórico do sobrevivente,
    # mas mantendo o título que o card tinha na época
    criacoes = [e for e in entradas if e["acao"] == "card_criado"]
    assert {e["card_titulo"] for e in criacoes} == {"Vai sumir", "Sobrevivente"}
