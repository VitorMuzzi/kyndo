"""Tela de Gestão: horas e andamento da equipe, para quem tem acessar_gestao.

Tudo aqui é leitura. O período é um intervalo de dias inteiros (início e fim
inclusive) e cada registro de tempo conta só a parte que cai dentro dele — um
cronômetro ligado às 23h e desligado à 1h soma uma hora em cada dia.

Respeita as colunas visíveis do gestor: card que ele não enxerga no quadro
não entra nem no andamento nem nas horas."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import AtividadeDB, CardDB, ColumnDB, TimeEntryDB, UserDB
from rbac import get_visible_column_ids, require_permission
from routers.tempo import _etapas_por_id

router = APIRouter()

MAX_DIAS_PERIODO = 400


def _periodo(inicio: Optional[str], fim: Optional[str]):
    """Dias inclusive → [início do primeiro dia, início do dia seguinte ao último)."""
    hoje = date.today()
    try:
        d_ini = date.fromisoformat(inicio) if inicio else hoje
        d_fim = date.fromisoformat(fim) if fim else d_ini
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida — use AAAA-MM-DD")
    if d_fim < d_ini:
        raise HTTPException(status_code=400, detail="O fim do período é anterior ao início")
    if (d_fim - d_ini).days >= MAX_DIAS_PERIODO:
        raise HTTPException(status_code=400, detail=f"Período máximo de {MAX_DIAS_PERIODO} dias")
    return d_ini, d_fim, datetime.combine(d_ini, datetime.min.time()), datetime.combine(d_fim + timedelta(days=1), datetime.min.time())


def _sobreposicao(e: TimeEntryDB, ini: datetime, fim: datetime, agora: datetime) -> int:
    e_ini = datetime.fromisoformat(e.inicio)
    e_fim = datetime.fromisoformat(e.fim) if e.fim else agora
    return max(0, int((min(e_fim, fim) - max(e_ini, ini)).total_seconds()))


def _colunas_visiveis(db, user_id):
    visible = get_visible_column_ids(db, user_id)
    cols = db.query(ColumnDB).filter(ColumnDB.arquivado == False).order_by(ColumnDB.ordem).all()  # noqa: E712
    if visible is not None:
        cols = [c for c in cols if c.id in visible]
    return {c.id: c for c in cols}


def _progresso(checklist):
    """Mesma conta do card: cada etapa vale 1, dividida entre as sub-etapas."""
    itens = [i for i in (checklist or []) if isinstance(i, dict)]
    if not itens:
        return None
    soma = 0.0
    for item in itens:
        subs = [s for s in (item.get("subetapas") or []) if isinstance(s, dict)]
        if subs:
            soma += sum(1 for s in subs if s.get("concluido")) / len(subs)
        else:
            soma += 1 if item.get("concluido") else 0
    return round(soma / len(itens) * 100)


def _responsaveis(card):
    nomes = card.responsaveis or ([card.autor] if card.autor else [])
    return [n.strip() for n in nomes if n and n.strip()]


def _resumo_card(card, col, hoje):
    concluido = bool(col.auto_concluido)
    atrasado = False
    if card.prazo and not concluido:
        try:
            atrasado = datetime.strptime(card.prazo, "%Y-%m-%d").date() < hoje
        except ValueError:
            pass
    return {
        "id": card.id, "titulo": card.titulo, "prioridade": card.prioridade or "Normal",
        "coluna_id": col.id, "coluna": col.titulo, "coluna_cor": col.cor,
        "prazo": card.prazo, "atrasado": atrasado, "concluido": concluido,
        "progresso": _progresso(card.checklist), "responsaveis": _responsaveis(card),
    }


def _entradas_no_periodo(db, card_ids, ini, fim):
    if not card_ids:
        return []
    # Datas em isoformat comparam certo como texto; o recorte fino é em _sobreposicao.
    return db.query(TimeEntryDB).filter(
        TimeEntryDB.card_id.in_(card_ids),
        TimeEntryDB.inicio < fim.isoformat(),
        (TimeEntryDB.fim == None) | (TimeEntryDB.fim > ini.isoformat()),  # noqa: E711
    ).all()


def _entradas_de_atividades(db, ini, fim):
    """Tempo das atividades fora de card (saída de campo...) no período —
    entram nas horas de cada pessoa, sem depender das colunas visíveis."""
    return db.query(TimeEntryDB).filter(
        TimeEntryDB.atividade_id != None,  # noqa: E711
        TimeEntryDB.inicio < fim.isoformat(),
        (TimeEntryDB.fim == None) | (TimeEntryDB.fim > ini.isoformat()),  # noqa: E711
    ).all()


def _titulos_atividades(db):
    return {a.id: a.titulo for a in db.query(AtividadeDB).all()}


def _em_andamento(db, cards_por_id, agora, user_id=None):
    q = db.query(TimeEntryDB).filter(TimeEntryDB.fim == None)  # noqa: E711
    if user_id:
        q = q.filter(TimeEntryDB.user_id == user_id)
    rodando = []
    atividades = None
    for e in q.all():
        if e.atividade_id:
            atividades = atividades if atividades is not None else _titulos_atividades(db)
            rodando.append({
                "user_id": e.user_id, "usuario": e.usuario, "card_id": None, "atividade_id": e.atividade_id,
                "card_titulo": atividades.get(e.atividade_id, "Atividade"), "etapa_texto": None, "inicio": e.inicio,
                "decorrido_segundos": max(0, int((agora - datetime.fromisoformat(e.inicio)).total_seconds())),
            })
            continue
        card = cards_por_id.get(e.card_id)
        if not card:
            continue
        etapa = _etapas_por_id(card.checklist).get(e.item_id) if e.item_id else None
        rodando.append({
            "user_id": e.user_id, "usuario": e.usuario, "card_id": e.card_id, "card_titulo": card.titulo,
            "etapa_texto": etapa.get("texto") if etapa else None, "inicio": e.inicio,
            "decorrido_segundos": max(0, int((agora - datetime.fromisoformat(e.inicio)).total_seconds())),
        })
    return sorted(rodando, key=lambda r: -r["decorrido_segundos"])


@router.get("/gestao/visao-geral")
def visao_geral(inicio: Optional[str] = None, fim: Optional[str] = None, db: Session = Depends(get_db),
                current_user: UserDB = Depends(require_permission("acessar_gestao"))):
    d_ini, d_fim, ini, fim_dt = _periodo(inicio, fim)
    agora = datetime.now()
    cols = _colunas_visiveis(db, current_user.id)
    cards = db.query(CardDB).filter(CardDB.status.in_(list(cols))).all() if cols else []
    cards_por_id = {c.id: c for c in cards}

    seg_card = defaultdict(int)
    seg_user = defaultdict(int)
    cards_user = defaultdict(set)
    for e in _entradas_no_periodo(db, list(cards_por_id), ini, fim_dt):
        seg = _sobreposicao(e, ini, fim_dt, agora)
        if not seg:
            continue
        seg_card[e.card_id] += seg
        seg_user[e.user_id] += seg
        cards_user[e.user_id].add(e.card_id)
    for e in _entradas_de_atividades(db, ini, fim_dt):
        seg_user[e.user_id] += _sobreposicao(e, ini, fim_dt, agora)

    # Tempo total de cada card, desde sempre — o andamento compara o período com o acumulado.
    seg_total_card = defaultdict(int)
    todas = db.query(TimeEntryDB).filter(TimeEntryDB.card_id.in_(list(cards_por_id))).all() if cards_por_id else []
    for e in todas:
        fim_e = datetime.fromisoformat(e.fim) if e.fim else agora
        seg_total_card[e.card_id] += max(0, int((fim_e - datetime.fromisoformat(e.inicio)).total_seconds()))

    rodando = _em_andamento(db, cards_por_id, agora)
    rodando_ids = {r["user_id"] for r in rodando}

    # Quem não registrou nada no período também aparece, com zero:
    # pra quem gere, "não registrou" é informação.
    funcionarios = [
        {"user_id": u.id, "nome": u.nome, "segundos": seg_user.get(u.id, 0),
         "cards": len(cards_user.get(u.id, ())), "rodando": u.id in rodando_ids}
        for u in db.query(UserDB).all()
    ]
    funcionarios.sort(key=lambda f: (-f["segundos"], f["nome"].lower()))

    hoje = date.today()
    andamento = []
    for card in cards:
        resumo = _resumo_card(card, cols[card.status], hoje)
        resumo["segundos_periodo"] = seg_card.get(card.id, 0)
        resumo["segundos_total"] = seg_total_card.get(card.id, 0)
        andamento.append(resumo)

    return {
        "periodo": {"inicio": d_ini.isoformat(), "fim": d_fim.isoformat()},
        "total_segundos": sum(seg_user.values()),
        "funcionarios": funcionarios,
        "trabalhando_agora": rodando,
        "cards": andamento,
    }


@router.get("/gestao/funcionario/{user_id}")
def ficha_funcionario(user_id: str, inicio: Optional[str] = None, fim: Optional[str] = None, db: Session = Depends(get_db),
                      current_user: UserDB = Depends(require_permission("acessar_gestao"))):
    alvo = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    d_ini, d_fim, ini, fim_dt = _periodo(inicio, fim)
    agora = datetime.now()
    cols = _colunas_visiveis(db, current_user.id)
    cards = db.query(CardDB).filter(CardDB.status.in_(list(cols))).all() if cols else []
    cards_por_id = {c.id: c for c in cards}

    entradas = [e for e in _entradas_no_periodo(db, list(cards_por_id), ini, fim_dt) if e.user_id == alvo.id]
    entradas += [e for e in _entradas_de_atividades(db, ini, fim_dt) if e.user_id == alvo.id]
    entradas.sort(key=lambda e: e.inicio, reverse=True)
    titulos_atv = _titulos_atividades(db)
    por_atividade = defaultdict(int)

    por_dia = defaultdict(int)
    por_card = defaultdict(int)
    registros = []
    for e in entradas:
        seg = _sobreposicao(e, ini, fim_dt, agora)
        if not seg:
            continue
        if e.atividade_id:
            por_atividade[e.atividade_id] += seg
        else:
            por_card[e.card_id] += seg
        # Reparte entre os dias que o intervalo atravessa.
        dia = max(datetime.fromisoformat(e.inicio).date(), d_ini)
        ultimo = min((datetime.fromisoformat(e.fim) if e.fim else agora).date(), d_fim)
        while dia <= ultimo:
            d0 = datetime.combine(dia, datetime.min.time())
            por_dia[dia.isoformat()] += _sobreposicao(e, d0, d0 + timedelta(days=1), agora)
            dia += timedelta(days=1)
        if e.atividade_id:
            registros.append({
                "id": e.id, "card_id": None, "atividade_id": e.atividade_id,
                "card_titulo": titulos_atv.get(e.atividade_id, "Atividade"), "etapa_texto": None,
                "inicio": e.inicio, "fim": e.fim, "segundos": seg,
            })
            continue
        card = cards_por_id[e.card_id]
        etapa = _etapas_por_id(card.checklist).get(e.item_id) if e.item_id else None
        registros.append({
            "id": e.id, "card_id": e.card_id, "card_titulo": card.titulo,
            "etapa_texto": etapa.get("texto") if etapa else None,
            "inicio": e.inicio, "fim": e.fim, "segundos": seg,
        })

    dias = []
    dia = d_ini
    while dia <= d_fim:
        dias.append({"data": dia.isoformat(), "segundos": por_dia.get(dia.isoformat(), 0)})
        dia += timedelta(days=1)

    hoje = date.today()
    responsavel = []
    etapas_concluidas = 0
    for card in cards:
        if alvo.nome in _responsaveis(card):
            responsavel.append(_resumo_card(card, cols[card.status], hoje))
        for item in _etapas_por_id(card.checklist).values():
            if item.get("concluido") and item.get("concluidoPor") == alvo.nome:
                etapas_concluidas += 1
    responsavel.sort(key=lambda c: (c["concluido"], not c["atrasado"], c["prazo"] or "9999"))

    rodando = _em_andamento(db, cards_por_id, agora, user_id=alvo.id)
    return {
        "usuario": {"id": alvo.id, "nome": alvo.nome},
        "periodo": {"inicio": d_ini.isoformat(), "fim": d_fim.isoformat()},
        "total_segundos": sum(por_card.values()) + sum(por_atividade.values()),
        "por_dia": dias,
        "por_card": sorted(
            ({"card_id": cid, "titulo": cards_por_id[cid].titulo, "segundos": s} for cid, s in por_card.items()),
            key=lambda c: -c["segundos"],
        ),
        "por_atividade": sorted(
            ({"atividade_id": aid, "titulo": titulos_atv.get(aid, "Atividade"), "segundos": s} for aid, s in por_atividade.items()),
            key=lambda a: -a["segundos"],
        ),
        "registros": registros,
        "cards_responsavel": responsavel,
        # Etapas não guardam a data em que foram concluídas — este número é desde sempre.
        "etapas_concluidas": etapas_concluidas,
        "rodando": rodando[0] if rodando else None,
    }
