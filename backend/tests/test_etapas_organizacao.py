"""Auditoria da reorganização do checklist: indentar, desindentar, trocar de
pai e reordenar não podem virar "excluída + criada" no log, e nada disso conta
como alteração de conteúdo (não acende o aviso de não-visto)."""
from tests.conftest import auth


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card etapas", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _get_card(client, token, card_id):
    r = client.get("/cards", headers=auth(token))
    return next((c for c in r.json() if c["id"] == card_id), None)


def _put(client, token, card, **overrides):
    payload = {
        "titulo": card["titulo"], "status": card["status"], "autor": card["autor"],
        "descricao": card.get("descricao") or "", "prioridade": card.get("prioridade") or "Normal",
        "checklist": card.get("checklist") or [], "comentarios": card.get("comentarios") or [],
        "responsaveis": card.get("responsaveis") or [], "ordem": card.get("ordem") or 0,
        **overrides,
    }
    r = client.put(f"/cards/{card['id']}", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return _get_card(client, token, card["id"])


def _log(client, token, card_id):
    r = client.get(f"/audit-log?card_id={card_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _ids_do_log(client, token, card_id):
    """Marca o log antes da ação, pra depois olhar SÓ o que ela gerou — sem
    isso as entradas da montagem do cenário (etapa_criada etc.) entram na
    conta e o teste passa/falha por motivo errado."""
    return {l["id"] for l in _log(client, token, card_id)}


def _acoes_novas(client, token, card_id, ids_antes):
    return [l["acao"] for l in _log(client, token, card_id) if l["id"] not in ids_antes]


def _acoes(logs):
    return [l["acao"] for l in logs]


def _etapa(iid, texto, subetapas=None, **extra):
    return {"id": iid, "texto": texto, "concluido": False, "criador": "admin",
            "subetapas": subetapas or [], **extra}


def _sub(sid, texto):
    return {"id": sid, "texto": texto, "concluido": False, "criador": "admin"}


# --- indentar / desindentar --------------------------------------------------

def test_indentar_nao_registra_exclusao(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("e-1", "Levantar requisitos"),
        _etapa("e-2", "Implementar"),
    ])

    antes = _ids_do_log(client, admin_token, card["id"])
    # e-2 vira sub-etapa de e-1
    card = _put(client, admin_token, card, checklist=[
        _etapa("e-1", "Levantar requisitos", subetapas=[_sub("e-2", "Implementar")]),
    ])

    acoes = _acoes_novas(client, admin_token, card["id"], antes)
    assert "etapa_indentada" in acoes
    assert "etapa_excluida" not in acoes, "indentar foi registrado como exclusao"
    assert "subetapa_criada" not in acoes, "indentar foi registrado como criacao"


def test_desindentar_nao_registra_criacao(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("d-1", "Pai", subetapas=[_sub("d-2", "Filha")]),
    ])

    antes = _ids_do_log(client, admin_token, card["id"])
    # d-2 sai de baixo de d-1 e vira etapa
    card = _put(client, admin_token, card, checklist=[
        _etapa("d-1", "Pai"),
        _etapa("d-2", "Filha"),
    ])

    acoes = _acoes_novas(client, admin_token, card["id"], antes)
    assert "etapa_desindentada" in acoes
    assert "etapa_criada" not in acoes, "desindentar foi registrado como criacao"
    assert "subetapa_excluida" not in acoes, "desindentar foi registrado como exclusao"


def test_indentar_com_filhas_registra_movimentacao_das_filhas(client, admin_token):
    """Só há 2 níveis: indentar uma etapa que tem filhas achata as filhas como
    irmãs dela. Elas mudam de pai, e isso tem que aparecer como movimentação."""
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("f-1", "Alvo"),
        _etapa("f-2", "Movida", subetapas=[_sub("f-3", "Filha da movida")]),
    ])

    antes = _ids_do_log(client, admin_token, card["id"])
    card = _put(client, admin_token, card, checklist=[
        _etapa("f-1", "Alvo", subetapas=[_sub("f-2", "Movida"), _sub("f-3", "Filha da movida")]),
    ])

    acoes = _acoes_novas(client, admin_token, card["id"], antes)
    assert "etapa_indentada" in acoes
    assert "subetapa_movida" in acoes
    assert "etapa_excluida" not in acoes
    assert "subetapa_criada" not in acoes


def test_trocar_subetapa_de_pai(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("p-1", "Pai A", subetapas=[_sub("p-3", "Anda")]),
        _etapa("p-2", "Pai B"),
    ])

    antes = _ids_do_log(client, admin_token, card["id"])
    card = _put(client, admin_token, card, checklist=[
        _etapa("p-1", "Pai A"),
        _etapa("p-2", "Pai B", subetapas=[_sub("p-3", "Anda")]),
    ])

    novas = [l for l in _log(client, admin_token, card["id"]) if l["id"] not in antes]
    movidas = [l for l in novas if l["acao"] == "subetapa_movida"]
    assert len(movidas) == 1
    assert "Pai A" in movidas[0]["detalhe"] and "Pai B" in movidas[0]["detalhe"]
    acoes = [l["acao"] for l in novas]
    assert "subetapa_excluida" not in acoes
    assert "subetapa_criada" not in acoes


# --- reordenar ---------------------------------------------------------------

def test_reordenar_registra_uma_entrada_so(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("r-1", "Primeira"), _etapa("r-2", "Segunda"), _etapa("r-3", "Terceira"),
    ])

    antes = _ids_do_log(client, admin_token, card["id"])
    card = _put(client, admin_token, card, checklist=[
        _etapa("r-3", "Terceira"), _etapa("r-1", "Primeira"), _etapa("r-2", "Segunda"),
    ])

    acoes = _acoes_novas(client, admin_token, card["id"], antes)
    assert acoes.count("etapas_reordenadas") == 1
    assert "etapa_criada" not in acoes
    assert "etapa_excluida" not in acoes


def test_reordenar_nao_acende_aviso_de_nao_visto(client, admin_token, joao):
    """Reorganizar não é mudança de conteúdo — segue a mesma regra que já vale
    pra exclusão de etapa: é logado, mas não gera badge pros outros."""
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("n-1", "Um"), _etapa("n-2", "Dois"),
    ])
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))
    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is False

    _put(client, admin_token, card, checklist=[_etapa("n-2", "Dois"), _etapa("n-1", "Um")])

    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is False


def test_indentar_nao_acende_aviso_de_nao_visto(client, admin_token, joao):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("i-1", "Um"), _etapa("i-2", "Dois"),
    ])
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))

    _put(client, admin_token, card, checklist=[
        _etapa("i-1", "Um", subetapas=[_sub("i-2", "Dois")]),
    ])

    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is False


# --- o que continua funcionando como antes ----------------------------------

def test_exclusao_de_verdade_continua_sendo_exclusao(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("x-1", "Fica"), _etapa("x-2", "Some"),
    ])

    antes = _ids_do_log(client, admin_token, card["id"])
    card = _put(client, admin_token, card, checklist=[_etapa("x-1", "Fica")])

    acoes = _acoes_novas(client, admin_token, card["id"], antes)
    assert "etapa_excluida" in acoes
    assert "etapa_indentada" not in acoes


def test_criacao_de_verdade_continua_sendo_criacao(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[_etapa("c-1", "Uma")])
    antes = _ids_do_log(client, admin_token, card["id"])
    card = _put(client, admin_token, card, checklist=[
        _etapa("c-1", "Uma"), _etapa("c-2", "Nova de verdade"),
    ])

    acoes = _acoes_novas(client, admin_token, card["id"], antes)
    assert "etapa_criada" in acoes
    assert "etapas_reordenadas" not in acoes


def test_editar_texto_junto_com_reordenar_ainda_conta_como_conteudo(client, admin_token, joao):
    card = _create_card(client, admin_token, "admin")
    card = _put(client, admin_token, card, checklist=[
        _etapa("m-1", "Um"), _etapa("m-2", "Dois"),
    ])
    client.post(f"/cards/{card['id']}/seen", headers=auth(joao["token"]))

    antes = _ids_do_log(client, admin_token, card["id"])
    # reordena E renomeia: o rename é conteúdo, então o badge tem que acender
    _put(client, admin_token, card, checklist=[
        _etapa("m-2", "Dois editado"), _etapa("m-1", "Um"),
    ])

    assert _get_card(client, joao["token"], card["id"])["nao_visto"] is True
    acoes = _acoes_novas(client, admin_token, card["id"], antes)
    assert "etapa_editada" in acoes
    assert "etapas_reordenadas" in acoes
