"""E-mails automáticos do Kyndo.

Dois tipos:
- de segurança (link de redefinição, "sua senha/seu e-mail mudou"): sempre
  enviados na hora, ninguém desliga;
- avisos (TIPOS). Quem tem configurar_emails define cada um como opcional,
  obrigatório ou desligado. Cada pessoa escolhe, por aviso, o ALCANCE:
    nenhum   — não recebe
    meus     — cards em que é responsável ou autora
    seguidos — os de cima + os cards que ela segue (botão "Seguir")
    todos    — todos os cards que ela enxerga
  e a ENTREGA: na hora (um e-mail por acontecimento) ou num resumo diário.
  Obrigatório garante no mínimo "meus"; a pessoa pode ampliar.

Tudo aqui é chamado DEPOIS do commit de quem disparou. Quem fez a ação nunca
recebe aviso dela, e ninguém recebe aviso de card que não enxerga. Várias
mudanças no mesmo salvamento viram um e-mail só."""
import logging
import threading
import time
import uuid
from datetime import date, datetime, timedelta

import email_envio
from models import (
    AtividadeDB, AuditLogDB, CardDB, CardSeguidorDB, ColumnDB, ConfigDB, FilaAvisoDB, TimeEntryDB, UserDB,
)
from rbac import get_user_permissions, get_visible_column_ids

log = logging.getLogger("kyndo.email")

ALCANCES = ("nenhum", "meus", "seguidos", "todos")
NIVEL = {a: i for i, a in enumerate(ALCANCES)}
DE_CARD = ALCANCES
PESSOAL = ("nenhum", "meus")
SO_TODOS = ("nenhum", "todos")

# tipo: (rótulo, grupo, alcances possíveis, padrão, permissão necessária)
TIPOS = {
    "responsavel": ("Fui colocado como responsável por um card", "Cards", PESSOAL, "meus", None),
    "comentario": ("Comentário novo", "Cards", DE_CARD, "meus", None),
    "prioridade": ("Prioridade alterada", "Cards", DE_CARD, "nenhum", None),
    "prazo_alterado": ("Prazo alterado", "Cards", DE_CARD, "nenhum", None),
    "coluna": ("Card mudou de coluna", "Cards", DE_CARD, "nenhum", None),
    "concluido": ("Card concluído", "Cards", DE_CARD, "nenhum", None),
    "etapa": ("Etapa concluída", "Cards", DE_CARD, "nenhum", None),
    "anexo": ("Anexo adicionado", "Cards", DE_CARD, "nenhum", None),
    "card_criado": ("Card novo criado", "Cards", SO_TODOS, "nenhum", None),
    "sugestao": ("Sugestão esperando minha decisão", "Sugestões", DE_CARD, "todos", "decidir_sugestoes"),
    "sugestao_decidida": ("Minha sugestão foi aceita ou recusada", "Sugestões", PESSOAL, "meus", None),
    "prazo": ("Resumo diário de prazos vencendo ou vencidos (8h)", "Resumos", DE_CARD, "meus", None),
    "parado": ("Card parado: 3 dias sem nenhuma alteração (8h)", "Resumos", DE_CARD, "meus", None),
    "relatorio_recebido": ("Relatório enviado para mim (também fica no Kyndo)", "Relatórios", PESSOAL, "meus", "acessar_gestao"),
    "relatorio_resposta": ("Resposta na conversa de um relatório", "Relatórios", PESSOAL, "meus", None),
    "cronometro": ("Meu cronômetro ficou ligado 12 horas seguidas (foi esquecido?)", "Cronômetro", PESSOAL, "meus", None),
    "resumo_semanal": ("Resumo semanal da equipe: horas, concluídos e atrasados (segunda, 8h)", "Resumos", PESSOAL, "nenhum", "acessar_gestao"),
}
ROTULO_ALCANCE = {"nenhum": "Não receber", "meus": "Meus cards", "seguidos": "Meus e os que sigo", "todos": "Todos que vejo"}
ENTREGAS = ("imediato", "resumo")

MODOS = ("opcional", "obrigatorio", "desligado")
CHAVE_MODOS = "email_tipos"
CHAVE_PRAZO = "email_prazo_enviado_em"
CHAVE_FILA = "email_fila_enviada_em"
CHAVE_SEMANAL = "email_semanal_enviado_em"
CHAVE_PARADO = "email_parado_enviado_em"
CHAVE_PARADOS_AVISADOS = "email_parados_avisados"  # card_id → última atividade já avisada
DIAS_PARADO = 3
CHAVE_CRONOMETROS_AVISADOS = "email_cronometros_avisados"  # registros de tempo já avisados
HORAS_CRONOMETRO_LONGO = 12
HORA_DO_RESUMO = 8
HORA_DO_RESUMO_DE_AVISOS = 18

RODAPE_AVISO = ("Você recebe este aviso do Kyndo pelas suas preferências. Para mudar o que recebe, "
                "abra o Kyndo → engrenagem → Minha conta.")


# ------------------------------------------------------------ configuração

def _config(db, chave):
    linha = db.query(ConfigDB).filter(ConfigDB.chave == chave).first()
    return linha.valor if linha else None


def _gravar_config(db, chave, valor):
    linha = db.query(ConfigDB).filter(ConfigDB.chave == chave).first()
    if linha:
        linha.valor = valor
    else:
        db.add(ConfigDB(chave=chave, valor=valor))


def modos(db):
    gravado = _config(db, CHAVE_MODOS) or {}
    return {t: (gravado.get(t) if gravado.get(t) in MODOS else "opcional") for t in TIPOS}


def gravar_modos(db, novos):
    _gravar_config(db, CHAVE_MODOS, {t: novos[t] for t in TIPOS})


def _prefs(user):
    """{"avisos": {tipo: alcance}, "entrega": ...} — aceita o formato antigo
    ({tipo: bool}) de antes do alcance existir."""
    bruto = user.email_prefs or {}
    if "avisos" in bruto or "entrega" in bruto:
        return {"avisos": dict(bruto.get("avisos") or {}), "entrega": bruto.get("entrega", "imediato")}
    avisos = {t: (TIPOS[t][3] if v else "nenhum") for t, v in bruto.items() if t in TIPOS and isinstance(v, bool)}
    return {"avisos": avisos, "entrega": "imediato"}


def entrega(user):
    e = _prefs(user)["entrega"]
    return e if e in ENTREGAS else "imediato"


def pode_receber(db, user, tipo):
    permissao = TIPOS[tipo][4]
    return permissao is None or permissao in get_user_permissions(db, user.id)


def alcance(db, user, tipo, _modos=None):
    _, _, possiveis, padrao, _ = TIPOS[tipo]
    modo = (_modos or modos(db))[tipo]
    if modo == "desligado" or not pode_receber(db, user, tipo):
        return "nenhum"
    escolhido = _prefs(user)["avisos"].get(tipo, padrao)
    if escolhido not in possiveis:
        escolhido = padrao
    if modo == "obrigatorio" and escolhido == "nenhum":
        escolhido = possiveis[1]
    return escolhido


def preferencias(db, user):
    atuais = modos(db)
    return [
        {"tipo": t, "rotulo": rotulo, "grupo": grupo, "modo": atuais[t],
         "alcances": [{"valor": a, "rotulo": ROTULO_ALCANCE[a] if possiveis != PESSOAL else ("Receber" if a == "meus" else "Não receber")}
                      for a in possiveis],
         "alcance": alcance(db, user, t, atuais)}
        for t, (rotulo, grupo, possiveis, _, _) in TIPOS.items()
        if pode_receber(db, user, t)
    ]


def gravar_preferencias(db, user, avisos=None, entrega_nova=None):
    atuais = modos(db)
    prefs = _prefs(user)
    for tipo, valor in (avisos or {}).items():
        if tipo in TIPOS and valor in TIPOS[tipo][2] and atuais[tipo] != "desligado":
            prefs["avisos"][tipo] = valor
    if entrega_nova in ENTREGAS:
        prefs["entrega"] = entrega_nova
    user.email_prefs = prefs


# ----------------------------------------------------------- quem recebe

def _ve_card(db, user, card):
    visiveis = get_visible_column_ids(db, user.id)
    return visiveis is None or card.status in visiveis


def _responsaveis(card):
    return [n for n in (card.responsaveis or []) if n] or ([card.autor] if card.autor else [])


def _relacao(user, card, seguidores):
    """Quão perto a pessoa está do card, no mesmo eixo do alcance."""
    if user.nome in (card.responsaveis or []) or user.nome == card.autor:
        return "meus"
    if user.id in seguidores:
        return "seguidos"
    return "todos"


def seguidores(db, card_id):
    return {s.user_id for s in db.query(CardSeguidorDB).filter(CardSeguidorDB.card_id == card_id).all()}


def _link_card(card):
    return email_envio.link(f"/?card={card.id}")


def _data_br(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or ""


def _entregar(db, user, card, ator, linhas, assunto):
    """Na hora (e-mail agora) ou pra fila do resumo diário."""
    if entrega(user) == "resumo":
        agora = datetime.now().isoformat()
        for linha in linhas:
            db.add(FilaAvisoDB(id=uuid.uuid4().hex, user_id=user.id, card_id=card.id if card else None,
                               card_titulo=card.titulo if card else "", texto=linha, criado_em=agora))
        db.commit()
        return
    email_envio.enviar(
        user.email, assunto,
        [f"Olá, {user.nome}."] + ([f'No card "{card.titulo}"' + (f", por {ator.nome}:" if ator else ":")] if card else [])
        + [f"• {l}" for l in linhas],
        botao=("Abrir o card", _link_card(card)) if card else None, rodape=RODAPE_AVISO,
    )


def avisar_card(db, card, ator, mudancas, candidatos=None):
    """`mudancas` = [(tipo, linha)]. Cada pessoa recebe, num e-mail só, as
    linhas dos tipos que ela quer no alcance em que está deste card."""
    if not email_envio.configurado() or not mudancas:
        return
    atuais = modos(db)
    if all(atuais[t] == "desligado" for t, _ in mudancas):
        return
    segs = seguidores(db, card.id)
    for u in candidatos if candidatos is not None else db.query(UserDB).all():
        if not u.email or (ator and u.id == ator.id) or not _ve_card(db, u, card):
            continue
        nivel = NIVEL[_relacao(u, card, segs)]
        linhas = [linha for tipo, linha in mudancas if NIVEL[alcance(db, u, tipo, atuais)] >= nivel]
        if linhas:
            assunto = (f'{TIPOS[mudancas[0][0]][0]}: "{card.titulo}"' if len(linhas) == 1
                       else f'Novidades no card "{card.titulo}"')
            _entregar(db, u, card, ator, linhas, assunto)


def avisar_pessoa(db, user, tipo, card, ator, linha, assunto):
    """Aviso que é de uma pessoa específica (virou responsável, sugestão dela)."""
    if (not email_envio.configurado() or not user or not user.email or (ator and user.id == ator.id)
            or (card and not _ve_card(db, user, card)) or alcance(db, user, tipo) == "nenhum"):
        return
    _entregar(db, user, card, ator, [linha], assunto)


# ------------------------------------------------- eventos (ganchos)

def foto_card(card):
    """Estado antes de salvar, pra saber depois o que mudou."""
    concluidas = set()
    for item in card.checklist or []:
        if isinstance(item, dict):
            if item.get("concluido"):
                concluidas.add(item.get("id"))
            for s in item.get("subetapas") or []:
                if isinstance(s, dict) and s.get("concluido"):
                    concluidas.add(s.get("id"))
    return {
        "prioridade": card.prioridade, "prazo": card.prazo or "", "status": card.status,
        "responsaveis": set(card.responsaveis or []),
        "comentarios": {c.get("id") for c in card.comentarios or [] if isinstance(c, dict)},
        "concluidas": concluidas,
    }


def _nome_coluna(db, col_id):
    col = db.query(ColumnDB).filter(ColumnDB.id == col_id).first()
    return (col.titulo if col else col_id), bool(col and col.auto_concluido)


def _etapas(card):
    for item in card.checklist or []:
        if isinstance(item, dict):
            yield item
            for s in item.get("subetapas") or []:
                if isinstance(s, dict):
                    yield s


def card_salvo(db, card, ator, antes):
    """Depois de editar um card; `antes` = foto_card() tirada antes de salvar."""
    if not email_envio.configurado():
        return
    depois = foto_card(card)
    mudancas = []
    if antes.get("novo"):
        coluna, _ = _nome_coluna(db, card.status)
        mudancas.append(("card_criado", f"{ator.nome} criou o card na coluna {coluna}"
                         + (f", prioridade {card.prioridade}" if card.prioridade else "") + "."))
    if antes["prioridade"] != depois["prioridade"]:
        mudancas.append(("prioridade", f"Prioridade: {antes['prioridade'] or '—'} → {depois['prioridade'] or '—'}"))
    if antes["prazo"] != depois["prazo"]:
        mudancas.append(("prazo_alterado", f"Prazo: {_data_br(antes['prazo']) or 'sem prazo'} → {_data_br(depois['prazo']) or 'sem prazo'}"))
    if antes["status"] != depois["status"]:
        de, _ = _nome_coluna(db, antes["status"])
        para, concluiu = _nome_coluna(db, depois["status"])
        if concluiu:
            mudancas.append(("concluido", f"Card concluído (movido para {para})"))
        mudancas.append(("coluna", f"Coluna: {de} → {para}"))
    for etapa in _etapas(card):
        if etapa.get("concluido") and etapa.get("id") not in antes["concluidas"]:
            mudancas.append(("etapa", f"Etapa concluída: {etapa.get('texto') or '(sem texto)'}"))
    for c in card.comentarios or []:
        if isinstance(c, dict) and c.get("id") not in antes["comentarios"]:
            mudancas.append(("comentario", f"Comentário: “{(c.get('texto') or '')[:600]}”"))
    avisar_card(db, card, ator, mudancas)

    novos = [n for n in card.responsaveis or [] if n not in antes["responsaveis"]]
    for u in db.query(UserDB).filter(UserDB.nome.in_(novos)).all() if novos else []:
        avisar_pessoa(db, u, "responsavel", card, ator,
                      f"{ator.nome} colocou você como responsável." + (f" Prazo: {_data_br(card.prazo)}." if card.prazo else ""),
                      f'Você é responsável por "{card.titulo}"')


def card_criado(db, card, ator):
    antes = foto_card(card)
    antes.update({"responsaveis": set(), "comentarios": set(), "concluidas": set(), "novo": True})
    card_salvo(db, card, ator, antes)


def sugestao_nova(db, card, ator, sugestao):
    if not email_envio.configurado():
        return
    decisores = [u for u in db.query(UserDB).all() if "decidir_sugestoes" in get_user_permissions(db, u.id)]
    quem = sugestao.identificacao or ator.nome
    avisar_card(db, card, ator, [("sugestao", f"{quem} sugeriu: “{(sugestao.texto or '')[:600]}”")], candidatos=decisores)


def sugestao_decidida(db, card, ator, sugestao):
    autor = db.query(UserDB).filter(UserDB.nome == sugestao.autor).first()
    if sugestao.status == "aceita":
        linha = f"{ator.nome} aceitou sua sugestão “{(sugestao.texto or '')[:300]}”. Prazo de entrega: {_data_br(sugestao.prazo_entrega)}."
    else:
        linha = f"{ator.nome} recusou sua sugestão “{(sugestao.texto or '')[:300]}”. Motivo: {sugestao.motivo_recusa}"
    avisar_pessoa(db, autor, "sugestao_decidida", card, ator, linha, f'Sua sugestão em "{card.titulo}" foi {sugestao.status}')


def anexo_adicionado(db, card, ator, nome_arquivo):
    avisar_card(db, card, ator, [("anexo", f"{ator.nome} anexou o arquivo {nome_arquivo}")])


# ------------------------------------------------------ resumos agendados

def enviar_resumo_de_prazos(db, hoje=None):
    """Um e-mail por pessoa com os cards que vencem até amanhã ou já venceram,
    fora das colunas de concluído e das arquivadas, no alcance que ela escolheu."""
    if not email_envio.configurado():
        return 0
    hoje = hoje or date.today()
    atuais = modos(db)
    if atuais["prazo"] == "desligado":
        return 0
    limite = (hoje + timedelta(days=1)).isoformat()
    encerradas = {c.id for c in db.query(ColumnDB).all() if c.auto_concluido or c.arquivado}
    cards = [c for c in db.query(CardDB).filter(CardDB.prazo != None, CardDB.prazo != "").all()  # noqa: E711
             if c.prazo <= limite and c.status not in encerradas]
    if not cards:
        return 0
    segs = {c.id: seguidores(db, c.id) for c in cards}

    enviados = 0
    for u in db.query(UserDB).all():
        quero = NIVEL[alcance(db, u, "prazo", atuais)]
        if not u.email or quero == 0:
            continue
        meus = sorted((c for c in cards if NIVEL[_relacao(u, c, segs[c.id])] <= quero and _ve_card(db, u, c)),
                      key=lambda c: c.prazo)
        if not meus:
            continue
        linhas = []
        for c in meus:
            if c.prazo < hoje.isoformat():
                situacao = f"venceu em {_data_br(c.prazo)}"
            elif c.prazo == hoje.isoformat():
                situacao = "vence hoje"
            else:
                situacao = "vence amanhã"
            quem = ", ".join(_responsaveis(c))
            linhas.append(f"• {c.titulo} — {situacao}" + (f" ({quem})" if quero > 1 and quem else ""))
        email_envio.enviar(
            u.email, f"Kyndo: {len(meus)} card(s) com prazo vencendo",
            [f"Olá, {u.nome}.", "Estes cards estão com o prazo vencendo ou vencido:"] + linhas,
            botao=("Abrir o Kyndo", email_envio.link("/")), rodape=RODAPE_AVISO,
        )
        enviados += 1
    return enviados


def _ultima_atividade(db, cards, agora):
    """Último sinal de vida de cada card: qualquer alteração feita por uma
    pessoa (o log de auditoria — o reinício automático da recorrência não
    conta) ou cronômetro ligado nele. Card antigo sem log usa a data de criação."""
    ultima = {}

    def marcar(card_id, quando):
        if card_id in cards and quando and quando > ultima.get(card_id, ""):
            ultima[card_id] = quando

    for card_id, data in (db.query(AuditLogDB.card_id, AuditLogDB.data)
                          .filter(AuditLogDB.card_id != None, AuditLogDB.usuario != "sistema").all()):  # noqa: E711
        marcar(card_id, data)
    for e in db.query(TimeEntryDB).all():
        marcar(e.card_id, e.fim or agora.isoformat())
    for card_id, card in cards.items():
        if card_id not in ultima:
            try:
                ultima[card_id] = datetime.strptime(card.data_criacao or "", "%d/%m/%Y").isoformat()
            except ValueError:
                ultima[card_id] = agora.isoformat()  # sem como saber: não acusa
    return ultima


def _relacao_parado(user, card, seguidores):
    """Aqui "meus" são só os responsáveis (ou o autor, se não houver nenhum)."""
    if user.nome in _responsaveis(card):
        return "meus"
    return "seguidos" if user.id in seguidores else "todos"


def enviar_cards_parados(db, agora=None):
    """Um e-mail por pessoa com os cards abertos sem nenhuma alteração há
    DIAS_PARADO dias. Cada parada é avisada uma vez só: se alguém mexer no
    card e ele parar de novo, avisa de novo depois de mais DIAS_PARADO dias."""
    if not email_envio.configurado():
        return 0
    agora = agora or datetime.now()
    atuais = modos(db)
    if atuais["parado"] == "desligado":
        return 0
    encerradas = {c.id for c in db.query(ColumnDB).all() if c.auto_concluido or c.arquivado}
    abertos = {c.id: c for c in db.query(CardDB).all() if c.status not in encerradas}
    ultima = _ultima_atividade(db, abertos, agora)
    limite = (agora - timedelta(days=DIAS_PARADO)).isoformat()
    ja_avisados = _config(db, CHAVE_PARADOS_AVISADOS) or {}
    novos = {cid: quando for cid, quando in ultima.items() if quando <= limite and ja_avisados.get(cid) != quando}
    # Guarda só as paradas que continuam valendo, pra lista não crescer à toa.
    _gravar_config(db, CHAVE_PARADOS_AVISADOS, {cid: q for cid, q in ultima.items() if q <= limite})
    db.commit()
    if not novos:
        return 0
    cards = sorted((abertos[cid] for cid in novos), key=lambda c: novos[c.id])
    segs = {c.id: seguidores(db, c.id) for c in cards}

    enviados = 0
    for u in db.query(UserDB).all():
        quero = NIVEL[alcance(db, u, "parado", atuais)]
        if not u.email or quero == 0:
            continue
        meus = [c for c in cards if NIVEL[_relacao_parado(u, c, segs[c.id])] <= quero and _ve_card(db, u, c)]
        if not meus:
            continue
        linhas = []
        for c in meus:
            desde = datetime.fromisoformat(novos[c.id])
            dias = (agora - desde).days
            quem = ", ".join(_responsaveis(c))
            linhas.append(f"• {c.titulo} — parado desde {desde.strftime('%d/%m/%Y')} ({dias} dias)"
                          + (f" — responsável: {quem}" if quem else ""))
        email_envio.enviar(
            u.email, f"Kyndo: {len(meus)} card(s) parado(s) há {DIAS_PARADO} dias ou mais",
            [f"Olá, {u.nome}.", f"Estes cards estão há {DIAS_PARADO} dias ou mais sem nenhuma alteração:"] + linhas,
            botao=("Abrir o Kyndo", email_envio.link("/")), rodape=RODAPE_AVISO,
        )
        enviados += 1
    return enviados


def avisar_cronometros_longos(db, agora=None):
    """Cronômetro ligado há HORAS_CRONOMETRO_LONGO horas seguidas: avisa o
    dono uma vez, na hora (não espera o resumo do dia), pra ele conferir se
    não esqueceu ligado."""
    if not email_envio.configurado():
        return 0
    agora = agora or datetime.now()
    atuais = modos(db)
    limite = (agora - timedelta(hours=HORAS_CRONOMETRO_LONGO)).isoformat()
    rodando = db.query(TimeEntryDB).filter(TimeEntryDB.fim == None).all()  # noqa: E711
    ja_avisados = set(_config(db, CHAVE_CRONOMETROS_AVISADOS) or [])
    longos = [e for e in rodando if e.inicio <= limite and e.id not in ja_avisados]
    # Guarda só os que ainda estão rodando, pra lista não crescer à toa.
    _gravar_config(db, CHAVE_CRONOMETROS_AVISADOS, sorted({e.id for e in rodando} & (ja_avisados | {e.id for e in longos})))
    db.commit()

    enviados = 0
    for e in longos:
        u = db.query(UserDB).filter(UserDB.id == e.user_id).first()
        if not u or not u.email or alcance(db, u, "cronometro", atuais) == "nenhum":
            continue
        inicio = datetime.fromisoformat(e.inicio)
        horas = int((agora - inicio).total_seconds() // 3600)
        desde = f'desde {inicio.strftime("%d/%m/%Y às %H:%M")} — {horas} horas seguidas.'
        if e.atividade_id:
            atv = db.query(AtividadeDB).filter(AtividadeDB.id == e.atividade_id).first()
            texto = [f'Seu cronômetro está ligado na atividade "{atv.titulo if atv else "sem nome"}" {desde}',
                     "Se você esqueceu ligado, pare o cronômetro e, no Cronograma, abra a atividade para apagar "
                     "o período que não foi trabalho de verdade."]
            botao = ("Abrir o Kyndo", email_envio.link("/"))
        else:
            card = db.query(CardDB).filter(CardDB.id == e.card_id).first()
            texto = [f'Seu cronômetro está ligado no card "{card.titulo if card else "sem nome"}" {desde}',
                     "Se você esqueceu ligado, abra o card e pare o cronômetro. Depois, no histórico de tempo do card "
                     "(botão \"...\" da tarefa), dá para apagar o período que não foi trabalho de verdade."]
            botao = ("Abrir o card", _link_card(card)) if card else None
        email_envio.enviar(
            u.email, f"Kyndo: cronômetro ligado há {horas} horas — foi esquecido?",
            [f"Olá, {u.nome}."] + texto, botao=botao, rodape=RODAPE_AVISO,
        )
        enviados += 1
    return enviados


def enviar_fila_de_avisos(db):
    """Resumo diário de quem escolheu receber os avisos juntos."""
    if not email_envio.configurado():
        return 0
    por_pessoa = {}
    for item in db.query(FilaAvisoDB).order_by(FilaAvisoDB.criado_em).all():
        por_pessoa.setdefault(item.user_id, []).append(item)
    enviados = 0
    for user_id, itens in por_pessoa.items():
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if user and user.email:
            paragrafos = [f"Olá, {user.nome}.", "O que aconteceu hoje nos cards que você acompanha:"]
            por_card = {}
            for i in itens:
                por_card.setdefault(i.card_titulo or "(sem card)", []).append(i.texto)
            for titulo, linhas in por_card.items():
                paragrafos.append(f"{titulo}:")
                paragrafos += [f"   • {l}" for l in linhas]
            email_envio.enviar(user.email, f"Kyndo: resumo do dia ({len(itens)} aviso(s))", paragrafos,
                               botao=("Abrir o Kyndo", email_envio.link("/")), rodape=RODAPE_AVISO)
            enviados += 1
        for i in itens:
            db.delete(i)
    db.commit()
    return enviados


def _segundos_no_periodo(e, inicio, fim):
    a = max(datetime.fromisoformat(e.inicio), inicio)
    b = min(datetime.fromisoformat(e.fim) if e.fim else datetime.now(), fim)
    return max(0, int((b - a).total_seconds()))


def _horas(segundos):
    return f"{segundos // 3600}h{segundos % 3600 // 60:02d}"


def enviar_resumo_semanal(db, hoje=None):
    """Pra quem tem acessar_gestao e pediu: horas por pessoa nos últimos 7
    dias, cards concluídos na semana e os atrasados agora — só do que a
    pessoa enxerga."""
    if not email_envio.configurado():
        return 0
    hoje = hoje or date.today()
    atuais = modos(db)
    fim = datetime.combine(hoje, datetime.min.time())
    inicio = fim - timedelta(days=7)
    colunas = {c.id: c for c in db.query(ColumnDB).all()}
    concluidas = {cid for cid, c in colunas.items() if c.auto_concluido}
    cards = {c.id: c for c in db.query(CardDB).all()}
    entradas = db.query(TimeEntryDB).filter(TimeEntryDB.inicio < fim.isoformat()).all()
    movidos = db.query(AuditLogDB).filter(AuditLogDB.acao == "status_alterado", AuditLogDB.data >= inicio.isoformat(),
                                          AuditLogDB.data < fim.isoformat()).all()

    enviados = 0
    for u in db.query(UserDB).all():
        if not u.email or alcance(db, u, "resumo_semanal", atuais) == "nenhum":
            continue
        visiveis = get_visible_column_ids(db, u.id)
        ve = (lambda c: c is not None and (visiveis is None or c.status in visiveis))
        horas = {}
        for e in entradas:
            if e.atividade_id or ve(cards.get(e.card_id)):
                horas[e.usuario] = horas.get(e.usuario, 0) + _segundos_no_periodo(e, inicio, fim)
        feitos = sorted({cards[l.card_id].titulo for l in movidos
                         if l.card_id in cards and ve(cards[l.card_id]) and cards[l.card_id].status in concluidas})
        atrasados = sorted((c for c in cards.values() if ve(c) and c.prazo and c.prazo < hoje.isoformat()
                            and c.status not in concluidas and not getattr(colunas.get(c.status), "arquivado", False)),
                           key=lambda c: c.prazo)
        paragrafos = [f"Olá, {u.nome}.",
                      f"Resumo da equipe de {inicio.strftime('%d/%m')} a {(fim - timedelta(days=1)).strftime('%d/%m')}."]
        paragrafos.append("Horas registradas:")
        paragrafos += ([f"   • {n}: {_horas(s)}" for n, s in sorted(horas.items(), key=lambda x: -x[1]) if s > 0]
                       or ["   • ninguém registrou tempo"])
        paragrafos.append(f"Cards concluídos ({len(feitos)}):")
        paragrafos += [f"   • {t}" for t in feitos] or ["   • nenhum"]
        paragrafos.append(f"Atrasados agora ({len(atrasados)}):")
        paragrafos += [f"   • {c.titulo} — venceu em {_data_br(c.prazo)} ({', '.join(_responsaveis(c))})" for c in atrasados] or ["   • nenhum"]
        email_envio.enviar(u.email, "Kyndo: resumo semanal da equipe", paragrafos,
                           botao=("Abrir a Gestão", email_envio.link("/")), rodape=RODAPE_AVISO)
        enviados += 1
    return enviados


def _uma_vez(db, chave, marca, funcao):
    if _config(db, chave) == marca:
        return
    # Marca antes de enviar: se cair no meio, melhor faltar um resumo do que
    # mandar o mesmo duas vezes.
    _gravar_config(db, chave, marca)
    db.commit()
    funcao(db)


def rodar_agendados(fabrica_sessao, agora=None):
    agora = agora or datetime.now()
    if not email_envio.configurado():
        return
    db = fabrica_sessao()
    try:
        hoje = agora.date().isoformat()
        avisar_cronometros_longos(db, agora)
        if agora.hour >= HORA_DO_RESUMO:
            _uma_vez(db, CHAVE_PRAZO, hoje, lambda d: enviar_resumo_de_prazos(d, agora.date()))
            _uma_vez(db, CHAVE_PARADO, hoje, lambda d: enviar_cards_parados(d, agora))
            if agora.weekday() == 0:
                _uma_vez(db, CHAVE_SEMANAL, hoje, lambda d: enviar_resumo_semanal(d, agora.date()))
        if agora.hour >= HORA_DO_RESUMO_DE_AVISOS:
            _uma_vez(db, CHAVE_FILA, hoje, enviar_fila_de_avisos)
    except Exception:  # noqa: BLE001
        log.exception("Falha nos e-mails agendados")
    finally:
        db.close()


def iniciar_agendador(fabrica_sessao, intervalo=60):
    """Confere a cada `intervalo` segundos se já é hora de algum resumo ou
    envio de relatório agendado (esses saem mesmo sem e-mail configurado:
    o gestor recebe no Kyndo)."""
    import relatorios_envio  # import tardio: relatorios_envio importa este módulo

    def laco():
        while True:
            relatorios_envio.processar_com_log(fabrica_sessao)
            rodar_agendados(fabrica_sessao)
            time.sleep(intervalo)
    threading.Thread(target=laco, name="kyndo-resumos", daemon=True).start()


# ------------------------------------------------------------- segurança

def avisar_senha_alterada(user, por_outra_pessoa=False):
    if not user.email:
        return
    texto = ("Um administrador definiu uma senha temporária para a sua conta. Você vai criar uma nova no próximo login."
             if por_outra_pessoa else "A senha da sua conta acabou de ser alterada.")
    email_envio.enviar(
        user.email, "A senha da sua conta Kyndo foi alterada",
        [f"Olá, {user.nome}.", texto,
         "Se não foi você nem alguém que você pediu, fale com um administrador do Kyndo imediatamente."],
    )


def enviar_link_de_redefinicao(user, url):
    return email_envio.enviar(
        user.email, "Redefinir sua senha do Kyndo",
        [f"Olá, {user.nome}.", "Recebemos um pedido para redefinir a senha da sua conta no Kyndo.",
         "O link abaixo vale por 1 hora e só pode ser usado uma vez.",
         "Se não foi você, ignore este e-mail — sua senha continua a mesma."],
        botao=("Criar nova senha", url),
    )


def avisar_email_alterado(user, antigo, novo):
    if antigo:
        email_envio.enviar(
            antigo, "O e-mail da sua conta Kyndo foi alterado",
            [f"Olá, {user.nome}.", f"Este endereço deixou de ser o e-mail da sua conta no Kyndo (agora é {novo or 'nenhum'}).",
             "Se não foi você nem alguém que você pediu, fale com um administrador do Kyndo imediatamente."],
        )
    if novo:
        email_envio.enviar(
            novo, "Este e-mail agora está na sua conta Kyndo",
            [f"Olá, {user.nome}.", "Este endereço passou a ser o e-mail da sua conta no Kyndo.",
             "É por ele que chegam os avisos e o link de redefinição de senha."],
        )
