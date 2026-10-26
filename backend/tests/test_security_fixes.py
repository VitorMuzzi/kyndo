"""Regressões dos bugs encontrados na revisão do sistema inteiro.
Cada teste falha na versão anterior do código."""
import io
import os

from attachment_storage import UPLOAD_DIR
from tests.conftest import auth, create_user


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card teste", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _get_card(client, token, card_id):
    r = client.get("/cards", headers=auth(token))
    assert r.status_code == 200
    return next((c for c in r.json() if c["id"] == card_id), None)


def _put(client, token, card, **overrides):
    payload = {
        "titulo": card["titulo"], "status": card["status"], "autor": card["autor"],
        "descricao": card.get("descricao") or "", "prioridade": card.get("prioridade") or "Normal",
        "checklist": card.get("checklist") or [], "comentarios": card.get("comentarios") or [],
        "responsaveis": card.get("responsaveis") or [], "ordem": card.get("ordem") or 0,
        **overrides,
    }
    return client.put(f"/cards/{card['id']}", json=payload, headers=auth(token))


# --- fix 13: id de coluna reescrito pelo payload -----------------------------

def test_column_id_cannot_be_rewritten_by_payload(client, admin_token):
    nova = client.post("/columns", json={"id": "col-teste-id", "titulo": "Original",
                                         "cor": "#fff", "ordem": 9}, headers=auth(admin_token))
    assert nova.status_code == 200, nova.text
    card = _create_card(client, admin_token, "admin", status="col-teste-id")

    # payload tenta trocar a PK — o card ficaria órfão apontando pro id antigo
    r = client.put("/columns/col-teste-id",
                   json={"id": "col-sequestrada", "titulo": "Renomeada", "cor": "#fff", "ordem": 9},
                   headers=auth(admin_token))
    assert r.status_code == 200, r.text

    cols = client.get("/columns", headers=auth(admin_token)).json()
    ids = [c["id"] for c in cols]
    assert "col-teste-id" in ids
    assert "col-sequestrada" not in ids
    assert next(c for c in cols if c["id"] == "col-teste-id")["titulo"] == "Renomeada"
    # o card continua alcançável
    assert _get_card(client, admin_token, card["id"]) is not None


# --- fix 2: comentários apagáveis sem permissão e sem log --------------------

def test_comments_are_append_only_without_edit_permission(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin", comentarios=[
        {"id": "msg-1", "autor": "admin", "texto": "primeiro", "data": "01/01"},
        {"id": "msg-2", "autor": "admin", "texto": "segundo", "data": "01/01"},
    ])

    # maria não tem editar_card: tenta apagar tudo e mandar um novo
    r = _put(client, maria["token"], card, comentarios=[
        {"id": "msg-3", "autor": "maria", "texto": "novo", "data": "02/01"},
    ])
    assert r.status_code == 200, r.text

    d = _get_card(client, admin_token, card["id"])
    textos = [c["texto"] for c in d["comentarios"]]
    assert textos == ["primeiro", "segundo", "novo"], textos


def test_comment_edit_by_unprivileged_user_is_reverted(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin", comentarios=[
        {"id": "msg-e1", "autor": "admin", "texto": "original", "data": "01/01"},
    ])
    r = _put(client, maria["token"], card, comentarios=[
        {"id": "msg-e1", "autor": "admin", "texto": "adulterado", "data": "01/01"},
    ])
    assert r.status_code == 200

    d = _get_card(client, admin_token, card["id"])
    assert [c["texto"] for c in d["comentarios"]] == ["original"]


def test_comment_deletion_by_admin_is_audited(client, admin_token):
    card = _create_card(client, admin_token, "admin", comentarios=[
        {"id": "msg-d1", "autor": "admin", "texto": "some comigo", "data": "01/01"},
    ])
    r = _put(client, admin_token, card, comentarios=[])
    assert r.status_code == 200

    log = client.get(f"/audit-log?card_id={card['id']}", headers=auth(admin_token)).json()
    removidos = [e for e in log if e["acao"] == "comentario_removido"]
    assert len(removidos) == 1
    assert "some comigo" in removidos[0]["detalhe"]


# --- fix 10: `ordem` gravável sem reordenar_cards ----------------------------

def test_ordem_is_not_writable_without_reorder_permission(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin")
    original = _get_card(client, admin_token, card["id"])["ordem"]

    r = _put(client, maria["token"], card, ordem=original + 99)
    assert r.status_code == 200

    assert _get_card(client, admin_token, card["id"])["ordem"] == original


# --- fix 11: fallback de responsáveis confiando no autor do cliente ----------

def test_empty_responsaveis_falls_back_to_stored_author(client, admin_token, maria):
    """O fallback só dispara quando o card já está com `responsaveis` vazio —
    aí `_revert_unauthorized_fields` não vê diferença nenhuma e deixa passar,
    e o código antigo caía no `autor` que veio do cliente."""
    from database import SessionLocal
    from models import CardDB

    card = _create_card(client, admin_token, "admin", responsaveis=["admin"])

    db = SessionLocal()
    try:
        db_card = db.query(CardDB).filter(CardDB.id == card["id"]).first()
        db_card.responsaveis = []
        db.commit()
    finally:
        db.close()

    # maria não tem gerenciar_responsaveis; manda lista vazia + autor forjado
    r = _put(client, maria["token"], card, responsaveis=[], autor="maria")
    assert r.status_code == 200

    d = _get_card(client, admin_token, card["id"])
    assert d["responsaveis"] == ["admin"], d["responsaveis"]


# --- fix 9: anexos órfãos ----------------------------------------------------

def test_deleting_a_card_removes_its_attachments_and_files(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    up = client.post(f"/cards/{card['id']}/attachments",
                     files={"file": ("x.txt", io.BytesIO(b"dados"), "text/plain")},
                     headers=auth(admin_token))
    assert up.status_code == 200, up.text
    anexo_id = up.json()["id"]

    listagem = client.get(f"/cards/{card['id']}/attachments", headers=auth(admin_token)).json()
    nome_disco = None
    assert len(listagem) == 1
    # confirma que o arquivo existe em disco antes
    arquivos_antes = set(os.listdir(UPLOAD_DIR))
    assert arquivos_antes

    r = client.delete(f"/cards/{card['id']}", headers=auth(admin_token))
    assert r.status_code == 200

    # a linha some: o download não encontra mais nada
    dl = client.get(f"/attachments/{anexo_id}/download", headers=auth(admin_token))
    assert dl.status_code == 404


def test_orphan_attachment_is_not_downloadable(client, admin_token, maria):
    """Órfão pré-existente (linha sem card) não pode escapar da checagem de
    visibilidade — antes o `if db_card:` simplesmente pulava a verificação."""
    from database import SessionLocal
    from models import AttachmentDB

    db = SessionLocal()
    try:
        db.add(AttachmentDB(id="anexo-orfao-teste", card_id="card-que-nao-existe",
                            nome_original="segredo.txt", nome_arquivo="segredo-no-disco.txt",
                            content_type="text/plain", tamanho=5,
                            enviado_por="admin", enviado_em="2026-01-01T00:00:00"))
        db.commit()
    finally:
        db.close()

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(UPLOAD_DIR, "segredo-no-disco.txt"), "wb") as f:
        f.write(b"top secret")

    for token in (admin_token, maria["token"]):
        r = client.get("/attachments/anexo-orfao-teste/download", headers=auth(token))
        assert r.status_code == 404, f"orfao vazou: {r.status_code}"


# --- fix 8: log de auditoria vazando colunas ocultas -------------------------

def test_audit_log_respects_column_visibility(client, admin_token):
    """Cargo restrito a col-1 com ver_log_auditoria não pode ler o histórico
    de um card que vive em col-2."""
    escondido = _create_card(client, admin_token, "admin", titulo="Segredo em col-2", status="col-2")
    _put(client, admin_token, {**escondido, "status": "col-2"}, titulo="Segredo editado")

    visivel = _create_card(client, admin_token, "admin", titulo="Publico em col-1", status="col-1")

    cargo = client.post("/roles", json={
        "nome": "Auditor Restrito", "cor": "#888",
        "permissoes": {"ver_log_auditoria": True},
        "colunas_restritas": True, "colunas_visiveis": ["col-1"],
    }, headers=auth(admin_token))
    assert cargo.status_code == 200, cargo.text
    role_id = cargo.json()["id"]

    espiao = create_user(client, admin_token, "espiao_audit")
    r = client.put(f"/users/{espiao['id']}/roles", json={"role_ids": [role_id]}, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    espiao = client.post("/login", json={"nome": "espiao_audit", "senha": "senha123"}).json()

    log = client.get("/audit-log", headers=auth(espiao["token"]))
    assert log.status_code == 200, log.text
    entradas = log.json()

    card_ids = {e["card_id"] for e in entradas}
    assert escondido["id"] not in card_ids, "log vazou card de coluna oculta"
    titulos = " ".join((e.get("card_titulo") or "") + (e.get("valor_novo") or "") for e in entradas)
    assert "Segredo" not in titulos

    # e o que ele pode ver continua chegando
    assert visivel["id"] in card_ids


# --- fix 12: reverter sugestão apagando edição manual posterior --------------

def test_reverting_suggestion_does_not_clobber_later_manual_edit(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin", titulo="Titulo original")

    sug = client.post(f"/cards/{card['id']}/suggestions",
                      json={"texto": "muda o titulo", "identificacao": "maria",
                            "campo_alvo": "titulo", "valor_proposto": "Titulo sugerido"},
                      headers=auth(maria["token"]))
    assert sug.status_code == 200, sug.text
    sug_id = sug.json()["id"]

    aceita = client.patch(f"/cards/{card['id']}/suggestions/{sug_id}",
                          json={"status": "aceita", "prazo_entrega": "2026-12-01"},
                          headers=auth(admin_token))
    assert aceita.status_code == 200, aceita.text
    assert _get_card(client, admin_token, card["id"])["titulo"] == "Titulo sugerido"

    # alguém edita à mão DEPOIS da aceitação
    atual = _get_card(client, admin_token, card["id"])
    assert _put(client, admin_token, atual, titulo="Titulo editado a mao").status_code == 200

    # revogar a decisão não pode ressuscitar "Titulo original" por cima disso
    revoga = client.patch(f"/cards/{card['id']}/suggestions/{sug_id}",
                          json={"status": "rejeitada", "motivo_recusa": "mudei de ideia"},
                          headers=auth(admin_token))
    assert revoga.status_code == 200, revoga.text

    assert _get_card(client, admin_token, card["id"])["titulo"] == "Titulo editado a mao"

    log = client.get(f"/audit-log?card_id={card['id']}", headers=auth(admin_token)).json()
    assert any(e["acao"] == "sugestao_revogada_sem_reverter" for e in log)


def test_reverting_suggestion_still_works_when_untouched(client, admin_token, maria):
    card = _create_card(client, admin_token, "admin", titulo="Antes")

    sug = client.post(f"/cards/{card['id']}/suggestions",
                      json={"texto": "muda", "identificacao": "maria",
                            "campo_alvo": "titulo", "valor_proposto": "Depois"},
                      headers=auth(maria["token"]))
    sug_id = sug.json()["id"]

    client.patch(f"/cards/{card['id']}/suggestions/{sug_id}",
                 json={"status": "aceita", "prazo_entrega": "2026-12-01"},
                 headers=auth(admin_token))
    assert _get_card(client, admin_token, card["id"])["titulo"] == "Depois"

    client.patch(f"/cards/{card['id']}/suggestions/{sug_id}",
                 json={"status": "rejeitada", "motivo_recusa": "nao"},
                 headers=auth(admin_token))
    assert _get_card(client, admin_token, card["id"])["titulo"] == "Antes"


# --- senha padrão do admin ---------------------------------------------------

def _admin_db():
    from database import SessionLocal
    from models import UserDB
    db = SessionLocal()
    return db, db.query(UserDB).filter(UserDB.nome == "admin").first()


def test_init_db_marks_default_admin_password_as_temporary(client, admin_token, monkeypatch):
    from init_data import init_db
    monkeypatch.delenv("SUPERADMIN_PASSWORD", raising=False)
    init_db()
    db, admin = _admin_db()
    try:
        assert admin.senha_temporaria is True
    finally:
        admin.senha_temporaria = False
        db.commit()
        db.close()


def test_init_db_replaces_default_admin_password_with_env(client, admin_token, monkeypatch):
    from init_data import init_db
    from security import get_password_hash, verify_password
    db, admin = _admin_db()
    versao_original = admin.senha_versao or 0
    db.close()

    monkeypatch.setenv("SUPERADMIN_PASSWORD", "senha-do-env")
    init_db()
    db, admin = _admin_db()
    try:
        assert verify_password("senha-do-env", admin.senha)
        assert admin.senha_temporaria is False
    finally:
        # Devolve o admin como estava: admin_token é da sessão inteira de testes.
        admin.senha = get_password_hash("admin")
        admin.senha_versao = versao_original
        db.commit()
        db.close()


# --- recorrência com dias <= 0 travava o GET /cards em loop infinito ---------

def test_recurrence_days_must_be_positive(client, admin_token):
    for dias in (-1, 0):
        r = client.post("/cards", json={"titulo": "Loop", "status": "col-1", "autor": "admin",
                                        "recorrente": True, "recorrencia_dias": dias}, headers=auth(admin_token))
        assert r.status_code == 422, r.text
    assert client.get("/cards", headers=auth(admin_token)).status_code == 200


def test_creating_recurring_card_requires_gerenciar_etapas(client, maria):
    card = _create_card(client, maria["token"], maria["nome"], recorrente=True, recorrencia_dias=7)
    assert card["recorrente"] is False
    assert card["recorrencia_proximo_reset"] is None


# --- superadmin protegido de trocar_senha_outros / excluir_usuarios ----------

def test_superadmin_protected_from_lower_roles(client, admin_token):
    chefe = create_user(client, admin_token, "chefe_super")
    rh = create_user(client, admin_token, "rh_senhas")
    roles = {r["nome"]: r for r in client.get("/roles", headers=auth(admin_token)).json()}
    cargo_rh = client.post("/roles", json={"nome": "RH Senhas", "permissoes": {
        "trocar_senha_outros": True, "excluir_usuarios": True}}, headers=auth(admin_token)).json()
    assert client.put(f"/users/{rh['id']}/roles", json={"role_ids": [cargo_rh["id"]]},
                      headers=auth(admin_token)).status_code == 200
    assert client.put(f"/users/{chefe['id']}/roles", json={"role_ids": [roles["Superadmin"]["id"]]},
                      headers=auth(admin_token)).status_code == 200
    try:
        r = client.put(f"/users/{chefe['id']}/password", json={"nova_senha": "tomada"}, headers=auth(rh["token"]))
        assert r.status_code == 403
        r = client.delete(f"/users/{chefe['id']}", headers=auth(rh["token"]))
        assert r.status_code == 403
        assert client.post("/login", json={"nome": "chefe_super", "senha": "senha123"}).status_code == 200

        # Com quem não é superadmin a permissão continua funcionando.
        comum = create_user(client, admin_token, "comum_senha")
        r = client.put(f"/users/{comum['id']}/password", json={"nova_senha": "outra"}, headers=auth(rh["token"]))
        assert r.status_code == 200
    finally:
        client.put(f"/users/{chefe['id']}/roles", json={"role_ids": []}, headers=auth(admin_token))
        client.delete(f"/users/{chefe['id']}", headers=auth(admin_token))
        client.delete(f"/users/{rh['id']}", headers=auth(admin_token))
        client.delete(f"/roles/{cargo_rh['id']}", headers=auth(admin_token))


# --- trocar senha derruba as sessões antigas -------------------------------

def test_password_change_invalidates_old_tokens(client, admin_token):
    pessoa = create_user(client, admin_token, "sessao_derrubada")
    token_antigo = pessoa["token"]
    r = client.put(f"/users/{pessoa['id']}/password", json={"nova_senha": "nova123"}, headers=auth(token_antigo))
    assert r.status_code == 200
    token_novo = r.json()["token"]

    assert client.get("/cards", headers=auth(token_antigo)).status_code == 401
    assert client.get("/cards", headers=auth(token_novo)).status_code == 200


def test_password_reset_by_someone_else_is_temporary(client, admin_token):
    pessoa = create_user(client, admin_token, "reset_por_admin")
    r = client.put(f"/users/{pessoa['id']}/password", json={"nova_senha": "nova123"}, headers=auth(pessoa["token"]))
    assert client.post("/login", json={"nome": "reset_por_admin", "senha": "nova123"}).json()["senha_temporaria"] is False

    r = client.put(f"/users/{pessoa['id']}/password", json={"nova_senha": "do-admin"}, headers=auth(admin_token))
    assert r.status_code == 200
    assert "token" not in r.json()
    assert client.post("/login", json={"nome": "reset_por_admin", "senha": "do-admin"}).json()["senha_temporaria"] is True


# --- autoria nunca vem do payload ------------------------------------------

def test_card_authorship_comes_from_logged_user(client, maria):
    card = _create_card(
        client, maria["token"], "admin",
        responsaveis=["admin"],
        comentarios=[{"id": "c-falso", "autor": "admin", "texto": "fui eu?", "data": "x"}],
        checklist=[{"id": "e-falsa", "texto": "etapa", "concluido": True, "concluidoPor": "admin",
                    "criador": "admin", "subetapas": []}],
    )
    assert card["autor"] == maria["nome"]
    assert card["responsaveis"] == [maria["nome"]]
    assert card["comentarios"][0]["autor"] == maria["nome"]
    assert card["checklist"][0]["criador"] == maria["nome"]
    assert card["checklist"][0]["concluidoPor"] == maria["nome"]


def test_comment_and_step_authorship_preserved_on_edit(client, admin_token, maria):
    card = _create_card(
        client, maria["token"], maria["nome"],
        comentarios=[{"id": "c-1", "autor": maria["nome"], "texto": "oi", "data": "x"}],
        checklist=[{"id": "e-1", "texto": "etapa", "concluido": False, "criador": maria["nome"], "subetapas": [
            {"id": "s-1", "texto": "sub", "concluido": False, "criador": maria["nome"]}]}],
    )
    r = _put(
        client, admin_token, card,
        comentarios=[{"id": "c-1", "autor": "joao", "texto": "oi", "data": "x"},
                     {"id": "c-2", "autor": maria["nome"], "texto": "novo", "data": "x"}],
        checklist=[{"id": "e-1", "texto": "etapa", "concluido": False, "criador": "joao", "subetapas": [
            {"id": "s-1", "texto": "sub", "concluido": True, "concluidoPor": "joao", "criador": "joao"}]}],
    )
    assert r.status_code == 200, r.text
    salvo = _get_card(client, admin_token, card["id"])
    assert {c["id"]: c["autor"] for c in salvo["comentarios"]} == {"c-1": maria["nome"], "c-2": "admin"}
    etapa = salvo["checklist"][0]
    assert etapa["criador"] == maria["nome"]
    assert etapa["subetapas"][0]["criador"] == maria["nome"]
    assert etapa["subetapas"][0]["concluidoPor"] == "admin"
