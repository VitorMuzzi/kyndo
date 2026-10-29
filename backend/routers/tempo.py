"""Cronômetro de trabalho por card.

Cada pessoa liga o cronômetro num card (opcionalmente numa etapa dele) e o
tempo corre no servidor — fechar a aba ou trocar de máquina não perde nada.
Só um cronômetro por pessoa: ligar outro encerra o anterior.

Ligar e desligar não entra no log de auditoria nem acende o aviso de "não
visto" do card: é registro de quem trabalha, não alteração da demanda."""
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from audit import _mk_log
from database import get_db
from lixeira import excluir_linha
from models import AtividadeDB, CardDB, TimeEntryDB, UserDB
from rbac import get_user_permissions, get_visible_column_ids
from security import get_current_user

router = APIRouter()


class IniciarTempo(BaseModel):
    item_id: Optional[str] = None


def _assert_card_visible(db, current_user, db_card):
    """Mirrors the same guard in routers/cards.py — a card whose column is
    outside the caller's visible set doesn't exist for them."""
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None and db_card.status not in visible:
        raise HTTPException(status_code=404, detail="Card não encontrado")


def _etapas_por_id(checklist):
    """Etapas e sub-etapas num mapa só — o cronômetro aceita qualquer nível."""
    mapa = {}
    for item in checklist or []:
        if isinstance(item, dict) and "id" in item:
            mapa[item["id"]] = item
            for s in item.get("subetapas") or []:
                if isinstance(s, dict) and "id" in s:
                    mapa[s["id"]] = s
    return mapa


def _segundos(entry: TimeEntryDB, agora: datetime) -> int:
    fim = datetime.fromisoformat(entry.fim) if entry.fim else agora
    return max(0, int((fim - datetime.fromisoformat(entry.inicio)).total_seconds()))


def _em_andamento(db, user_id):
    return db.query(TimeEntryDB).filter(TimeEntryDB.user_id == user_id, TimeEntryDB.fim == None).first()  # noqa: E711


def _parar(entry: TimeEntryDB, agora: datetime):
    entry.fim = agora.isoformat()


def _serializar_atual(db, entry: TimeEntryDB, agora: datetime):
    if entry is None:
        return None
    if entry.atividade_id:
        atv = db.query(AtividadeDB).filter(AtividadeDB.id == entry.atividade_id).first()
        return {
            "id": entry.id, "card_id": None, "card_titulo": "", "item_id": None, "etapa_texto": None,
            "atividade_id": entry.atividade_id, "atividade_titulo": atv.titulo if atv else "Atividade",
            "inicio": entry.inicio, "decorrido_segundos": _segundos(entry, agora),
        }
    card = db.query(CardDB).filter(CardDB.id == entry.card_id).first()
    etapa = _etapas_por_id(card.checklist if card else None).get(entry.item_id) if entry.item_id else None
    return {
        "id": entry.id, "card_id": entry.card_id, "card_titulo": card.titulo if card else "",
        "item_id": entry.item_id, "etapa_texto": etapa.get("texto") if etapa else None,
        "inicio": entry.inicio,
        # O cliente conta a partir daqui em vez de usar o próprio relógio, que
        # pode estar desacertado em relação ao do servidor.
        "decorrido_segundos": _segundos(entry, agora),
    }


@router.get("/tempo/atual")
def cronometro_atual(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return _serializar_atual(db, _em_andamento(db, current_user.id), datetime.now())


@router.post("/cards/{card_id}/tempo/iniciar")
def iniciar_cronometro(card_id: str, body: IniciarTempo, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)
    if body.item_id and body.item_id not in _etapas_por_id(db_card.checklist):
        raise HTTPException(status_code=400, detail="Etapa não encontrada neste card")

    agora = datetime.now()
    anterior = _em_andamento(db, current_user.id)
    if anterior:
        _parar(anterior, agora)

    novo = TimeEntryDB(
        id=f"tempo-{uuid.uuid4().hex[:10]}", card_id=card_id, item_id=body.item_id or None,
        user_id=current_user.id, usuario=current_user.nome, inicio=agora.isoformat(),
    )
    db.add(novo)
    db.commit()
    return _serializar_atual(db, novo, agora)


@router.post("/tempo/parar")
def parar_cronometro(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    entry = _em_andamento(db, current_user.id)
    if entry:
        _parar(entry, datetime.now())
        db.commit()
    return {"ok": True}


@router.get("/cards/{card_id}/tempo")
def tempo_do_card(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)

    agora = datetime.now()
    ver_equipe = "ver_tempo_equipe" in get_user_permissions(db, current_user.id)
    entries = db.query(TimeEntryDB).filter(TimeEntryDB.card_id == card_id).order_by(TimeEntryDB.inicio.desc()).all()

    total = 0
    meu_total = 0
    por_etapa = defaultdict(int)
    por_pessoa = defaultdict(int)
    registros = []
    for e in entries:
        seg = _segundos(e, agora)
        total += seg
        por_pessoa[e.usuario] += seg
        if e.item_id:
            por_etapa[e.item_id] += seg
        meu = e.user_id == current_user.id
        if meu:
            meu_total += seg
        # Total e quanto cada pessoa trabalhou são de todos que veem o card;
        # os registros com horário (quando cada um trabalhou) só com
        # ver_tempo_equipe — cada um sempre vê os próprios.
        if meu or ver_equipe:
            registros.append({
                "id": e.id, "usuario": e.usuario, "item_id": e.item_id,
                "inicio": e.inicio, "fim": e.fim, "segundos": seg, "meu": meu,
            })

    return {
        "total_segundos": total,
        "meu_total_segundos": meu_total,
        "por_etapa": dict(por_etapa),
        "por_pessoa": sorted(({"usuario": k, "segundos": v} for k, v in por_pessoa.items()), key=lambda p: -p["segundos"]),
        "registros": registros,
        "pode_ver_equipe": ver_equipe,
    }


@router.put("/tempo/{entry_id}")
def vincular_etapa(entry_id: str, body: IniciarTempo, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Troca a etapa de um registro já feito (ou do que está rodando) — pra
    quem esqueceu de escolher a etapa ao ligar, ou escolheu a errada. Só o
    próprio registro, como apagar. item_id nulo = card inteiro."""
    entry = db.query(TimeEntryDB).filter(TimeEntryDB.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Só dá pra alterar o próprio registro de tempo")
    if entry.atividade_id:
        raise HTTPException(status_code=400, detail="Registro de atividade não tem etapa")
    card = db.query(CardDB).filter(CardDB.id == entry.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, card)
    if body.item_id and body.item_id not in _etapas_por_id(card.checklist):
        raise HTTPException(status_code=400, detail="Etapa não encontrada neste card")
    entry.item_id = body.item_id or None
    db.commit()
    return {"ok": True, "item_id": entry.item_id}


@router.delete("/tempo/{entry_id}")
def apagar_registro(entry_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Pra corrigir engano (ligou no card errado, esqueceu ligado). Só o
    próprio registro — o tempo dos outros não é de quem está olhando."""
    entry = db.query(TimeEntryDB).filter(TimeEntryDB.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Só dá pra apagar o próprio registro de tempo")
    if entry.atividade_id:
        # Tempo de atividade não é histórico de card: some sem log nem lixeira,
        # como a própria atividade.
        db.delete(entry)
        db.commit()
        return {"ok": True}
    card = db.query(CardDB).filter(CardDB.id == entry.card_id).first()
    duracao = _segundos(entry, datetime.now())
    lixeira_id = excluir_linha(db, "tempo", entry, current_user.nome)
    _mk_log(db, entry.card_id, card.titulo if card else "", current_user.nome, "tempo_apagado",
            detalhe=f"{duracao // 3600}h {duracao % 3600 // 60:02d}min de {entry.usuario}",
            lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})
    db.commit()
    return {"ok": True}
