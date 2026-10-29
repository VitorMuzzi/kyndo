"""Atividades fora de card: saída de campo, reunião, treinamento...

Aparecem no Cronograma de todos, na linha de quem é a atividade; só a dona
mexe nelas. Três jeitos de registrar:
- começar agora: cria a atividade e liga o cronômetro nela (o mesmo
  cronômetro dos cards — ligar uma coisa desliga a outra);
- lançar depois: informa início e fim de um período já feito;
- agendar: marca início e fim previstos; quando chegar a hora, a pessoa liga o
  cronômetro ou lança o período.

O tempo registrado soma nas horas da Gestão e no "O que você fez" dos
Relatórios."""
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AtividadeDB, TimeEntryDB, UserDB
from routers.tempo import _em_andamento, _parar, _segundos, _serializar_atual
from security import get_current_user

router = APIRouter()

MAX_TITULO = 80
MAX_PERIODO = timedelta(hours=24)       # um lançamento manual
MAX_AGENDAMENTO = timedelta(days=31)
FOLGA_FUTURO = timedelta(minutes=5)     # relógio do computador um pouco adiantado


class NovaAtividade(BaseModel):
    titulo: str
    modo: str                     # agora | lancar | agendar
    inicio: Optional[str] = None  # AAAA-MM-DDTHH:MM
    fim: Optional[str] = None


class EdicaoAtividade(BaseModel):
    titulo: str
    agendada_inicio: Optional[str] = None
    agendada_fim: Optional[str] = None


class Periodo(BaseModel):
    inicio: str
    fim: str


def _titulo(texto):
    titulo = " ".join((texto or "").split())
    if not titulo:
        raise HTTPException(status_code=400, detail="Dê um nome à atividade (ex.: Saída de campo).")
    if len(titulo) > MAX_TITULO:
        raise HTTPException(status_code=400, detail=f"Nome com no máximo {MAX_TITULO} caracteres.")
    return titulo


def _data_hora(texto, campo):
    try:
        return datetime.fromisoformat(texto).replace(second=0, microsecond=0, tzinfo=None)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Informe a data e a hora de {campo}.")


def _intervalo(inicio, fim, limite, msg_limite):
    ini = _data_hora(inicio, "início")
    fi = _data_hora(fim, "fim")
    if fi <= ini:
        raise HTTPException(status_code=400, detail="O fim tem que ser depois do início.")
    if fi - ini > limite:
        raise HTTPException(status_code=400, detail=msg_limite)
    return ini, fi


def _periodo_feito(inicio, fim):
    ini, fi = _intervalo(inicio, fim, MAX_PERIODO, "Um período lançado pode ter no máximo 24 horas.")
    if fi > datetime.now() + FOLGA_FUTURO:
        raise HTTPException(status_code=400, detail="Só dá para lançar tempo que já passou. Para o futuro, use Agendar.")
    return ini, fi


def _minha(db, user, atividade_id):
    atv = db.query(AtividadeDB).filter(AtividadeDB.id == atividade_id).first()
    if not atv:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")
    if atv.user_id != user.id:
        raise HTTPException(status_code=403, detail="Só quem registrou a atividade pode alterá-la")
    return atv


def _ligar(db, user, atv, agora):
    anterior = _em_andamento(db, user.id)
    if anterior:
        _parar(anterior, agora)
    entry = TimeEntryDB(id=f"tempo-{uuid.uuid4().hex[:10]}", card_id=None, atividade_id=atv.id,
                        user_id=user.id, usuario=user.nome, inicio=agora.isoformat())
    db.add(entry)
    return entry


def _lancar(db, user, atv, ini, fi):
    db.add(TimeEntryDB(id=f"tempo-{uuid.uuid4().hex[:10]}", card_id=None, atividade_id=atv.id,
                       user_id=user.id, usuario=user.nome, inicio=ini.isoformat(), fim=fi.isoformat()))


def _serializar(atv, registros, nomes, agora, eu):
    regs = sorted(registros, key=lambda e: e.inicio)
    return {
        "id": atv.id, "user_id": atv.user_id, "usuario": nomes.get(atv.user_id, "?"), "titulo": atv.titulo,
        "agendada_inicio": atv.agendada_inicio, "agendada_fim": atv.agendada_fim,
        "registros": [{"id": e.id, "inicio": e.inicio, "fim": e.fim, "segundos": _segundos(e, agora)} for e in regs],
        "total_segundos": sum(_segundos(e, agora) for e in regs),
        "em_andamento": any(e.fim is None for e in regs),
        "minha": atv.user_id == eu.id,
    }


def _uma(db, atv, user):
    regs = db.query(TimeEntryDB).filter(TimeEntryDB.atividade_id == atv.id).all()
    nomes = {u.id: u.nome for u in db.query(UserDB).filter(UserDB.id == atv.user_id).all()}
    return _serializar(atv, regs, nomes, datetime.now(), user)


@router.get("/atividades")
def listar(inicio: str, fim: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Atividades de todos que caem entre os dias `inicio` e `fim` (inclusive),
    pelo agendamento ou por tempo registrado."""
    try:
        ini = datetime.combine(date.fromisoformat(inicio), datetime.min.time())
        fi = datetime.combine(date.fromisoformat(fim), datetime.min.time()) + timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida — use AAAA-MM-DD")
    agora = datetime.now()
    por_atv = {}
    for e in db.query(TimeEntryDB).filter(TimeEntryDB.atividade_id != None).all():  # noqa: E711
        por_atv.setdefault(e.atividade_id, []).append(e)

    def cai_na_janela(a):
        if a.agendada_inicio and a.agendada_fim and a.agendada_inicio < fi.isoformat() and a.agendada_fim > ini.isoformat():
            return True
        return any(e.inicio < fi.isoformat() and (e.fim is None or e.fim > ini.isoformat()) for e in por_atv.get(a.id, []))

    nomes = {u.id: u.nome for u in db.query(UserDB).all()}
    return [_serializar(a, por_atv.get(a.id, []), nomes, agora, current_user)
            for a in db.query(AtividadeDB).all() if cai_na_janela(a)]


@router.post("/atividades")
def criar(corpo: NovaAtividade, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    titulo = _titulo(corpo.titulo)
    agora = datetime.now()
    atv = AtividadeDB(id=f"atv-{uuid.uuid4().hex[:10]}", user_id=current_user.id, titulo=titulo, criado_em=agora.isoformat())
    if corpo.modo == "agora":
        db.add(atv)
        _ligar(db, current_user, atv, agora)
    elif corpo.modo == "lancar":
        ini, fi = _periodo_feito(corpo.inicio, corpo.fim)
        db.add(atv)
        _lancar(db, current_user, atv, ini, fi)
    elif corpo.modo == "agendar":
        ini, fi = _intervalo(corpo.inicio, corpo.fim, MAX_AGENDAMENTO, "Um agendamento pode durar no máximo 31 dias.")
        atv.agendada_inicio, atv.agendada_fim = ini.isoformat(), fi.isoformat()
        db.add(atv)
    else:
        raise HTTPException(status_code=400, detail="Modo inválido")
    db.commit()
    return {"atividade": _uma(db, atv, current_user),
            "cronometro": _serializar_atual(db, _em_andamento(db, current_user.id), datetime.now())}


@router.put("/atividades/{atividade_id}")
def editar(atividade_id: str, corpo: EdicaoAtividade, db: Session = Depends(get_db),
           current_user: UserDB = Depends(get_current_user)):
    atv = _minha(db, current_user, atividade_id)
    atv.titulo = _titulo(corpo.titulo)
    if corpo.agendada_inicio or corpo.agendada_fim:
        ini, fi = _intervalo(corpo.agendada_inicio, corpo.agendada_fim, MAX_AGENDAMENTO,
                             "Um agendamento pode durar no máximo 31 dias.")
        atv.agendada_inicio, atv.agendada_fim = ini.isoformat(), fi.isoformat()
    else:
        atv.agendada_inicio = atv.agendada_fim = None
    db.commit()
    return _uma(db, atv, current_user)


@router.post("/atividades/{atividade_id}/iniciar")
def iniciar(atividade_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    atv = _minha(db, current_user, atividade_id)
    agora = datetime.now()
    entry = _ligar(db, current_user, atv, agora)
    db.commit()
    return {"atividade": _uma(db, atv, current_user), "cronometro": _serializar_atual(db, entry, agora)}


@router.post("/atividades/{atividade_id}/registros")
def lancar_periodo(atividade_id: str, corpo: Periodo, db: Session = Depends(get_db),
                   current_user: UserDB = Depends(get_current_user)):
    atv = _minha(db, current_user, atividade_id)
    ini, fi = _periodo_feito(corpo.inicio, corpo.fim)
    _lancar(db, current_user, atv, ini, fi)
    db.commit()
    return _uma(db, atv, current_user)


@router.delete("/atividades/{atividade_id}")
def apagar(atividade_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    atv = _minha(db, current_user, atividade_id)
    db.query(TimeEntryDB).filter(TimeEntryDB.atividade_id == atv.id).delete()
    db.delete(atv)
    db.commit()
    return {"ok": True}
