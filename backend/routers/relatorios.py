"""Relatórios do dia.

Cada pessoa escreve o próprio relatório de cada dia e, ao lado, vê o que fez
naquele dia — tempo cronometrado por card e etapa, mais o que o log de
auditoria registrou em nome dela (etapas concluídas, cards criados, mudanças
de coluna, comentários, anexos). Só a própria pessoa lê o próprio relatório.

Um cronômetro que atravessa a meia-noite conta só a parte que cai no dia, como
na tela de Gestão.

Modelos são textos que a pessoa guarda para começar o relatório; os campos
como {data} e {resumo} são preenchidos pela tela, que tem os dados do dia.

Enviar (na hora, agendado ou automático) e a conversa com o gestor ficam em
relatorios_envio.py; aqui estão as rotas. O gestor vê os relatórios que
recebeu em /relatorios/recebidos."""
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import relatorios_envio
from database import get_db
from models import (
    AtividadeDB, AuditLogDB, CardDB, ColumnDB, RelatorioAgendamentoDB, RelatorioAutomaticoDB, RelatorioDB,
    RelatorioEnvioDB, RelatorioMensagemDB, RelatorioModeloDB, TimeEntryDB, UserDB,
)
from routers.gestao import _sobreposicao
from routers.tempo import _etapas_por_id
from security import get_current_user

router = APIRouter()

MAX_CARACTERES = 20000
MAX_MODELOS = 50
MAX_NOME_MODELO = 60

# O que do log de auditoria entra como "feito no dia".
ACOES_DO_DIA = {
    "card_criado": "Criou o card",
    "etapa_criada": "Criou a etapa",
    "etapa_concluida": "Concluiu a etapa",
    "subetapa_concluida": "Concluiu a sub-etapa",
    "status_alterado": "Mudou de coluna",
    "comentario_adicionado": "Comentou",
    "anexo_adicionado": "Anexou",
}


class RelatorioUpdate(BaseModel):
    conteudo: str = ""


class EnvioRelatorio(BaseModel):
    para: List[str]


class AgendamentoRelatorio(BaseModel):
    para: List[str]
    enviar_em: str  # AAAA-MM-DDTHH:MM


class EnvioAutomatico(BaseModel):
    ativo: bool
    dias: List[int] = []
    hora: str = "18:00"
    para: List[str] = []
    sem_texto: str = "nada"


class MensagemRelatorio(BaseModel):
    autor_id: str
    data: str
    gestor_id: str
    texto: str


class ModeloRelatorio(BaseModel):
    nome: str
    conteudo: str = ""


def _dia(data: str):
    try:
        d = date.fromisoformat(data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida — use AAAA-MM-DD")
    ini = datetime.combine(d, datetime.min.time())
    return d, ini, ini + timedelta(days=1)


def _do_dia(db, user_id, data):
    return db.query(RelatorioDB).filter(RelatorioDB.user_id == user_id, RelatorioDB.data == data).first()


def atividade_do_dia(db, user: UserDB, ini: datetime, fim: datetime):
    """Tempo e ações da pessoa no dia, agrupados por card — o mais trabalhado primeiro."""
    agora = datetime.now()
    por_card = {}

    def card_de(card_id, titulo):
        if card_id not in por_card:
            por_card[card_id] = {"card_id": card_id, "titulo": titulo, "existe": False, "segundos": 0,
                                 "etapas": defaultdict(int), "acoes": [], "_primeiro": None}
        return por_card[card_id]

    cards = {}

    def card_atual(card_id):
        if card_id not in cards:
            cards[card_id] = db.query(CardDB).filter(CardDB.id == card_id).first()
        return cards[card_id]

    em_andamento = False
    por_atividade = defaultdict(int)
    entradas = db.query(TimeEntryDB).filter(TimeEntryDB.user_id == user.id, TimeEntryDB.inicio < fim.isoformat()).all()
    for e in entradas:
        seg = _sobreposicao(e, ini, fim, agora)
        if seg <= 0:
            continue
        em_andamento = em_andamento or e.fim is None
        if e.atividade_id:
            por_atividade[e.atividade_id] += seg
            continue
        card = card_atual(e.card_id)
        item = card_de(e.card_id, card.titulo if card else "")
        item["segundos"] += seg
        etapa = _etapas_por_id(card.checklist if card else None).get(e.item_id) if e.item_id else None
        item["etapas"][etapa.get("texto") if etapa else ("Etapa removida" if e.item_id else None)] += seg
        inicio = max(datetime.fromisoformat(e.inicio), ini).isoformat()
        if item["_primeiro"] is None or inicio < item["_primeiro"]:
            item["_primeiro"] = inicio

    colunas = {c.id: c.titulo for c in db.query(ColumnDB).all()}
    logs = (db.query(AuditLogDB)
            .filter(AuditLogDB.usuario == user.nome, AuditLogDB.card_id != None,  # noqa: E711
                    AuditLogDB.acao.in_(list(ACOES_DO_DIA)), AuditLogDB.revertido_em == None,  # noqa: E711
                    AuditLogDB.data >= ini.isoformat(), AuditLogDB.data < fim.isoformat())
            .order_by(AuditLogDB.data).all())
    for log in logs:
        card = card_atual(log.card_id)
        item = card_de(log.card_id, card.titulo if card else log.card_titulo)
        if log.acao == "status_alterado":
            detalhe = f"{colunas.get(log.valor_antigo, log.valor_antigo or '?')} → {colunas.get(log.valor_novo, log.valor_novo or '?')}"
        else:
            detalhe = log.detalhe
        item["acoes"].append({"acao": log.acao, "rotulo": ACOES_DO_DIA[log.acao], "detalhe": detalhe, "hora": log.data})
        if item["_primeiro"] is None or log.data < item["_primeiro"]:
            item["_primeiro"] = log.data

    lista = []
    for card_id, item in por_card.items():
        item["existe"] = card_atual(card_id) is not None
        # "Card inteiro" (tempo sem etapa) vai por último.
        etapas = sorted(item.pop("etapas").items(), key=lambda kv: (kv[0] is None, -kv[1]))
        item["etapas"] = [{"texto": texto, "segundos": seg} for texto, seg in etapas]
        lista.append(item)
    lista.sort(key=lambda i: (-i["segundos"], i["_primeiro"] or ""))
    for item in lista:
        del item["_primeiro"]
    titulos = {a.id: a.titulo for a in db.query(AtividadeDB).filter(AtividadeDB.id.in_(list(por_atividade))).all()}
    atividades = sorted(({"atividade_id": aid, "titulo": titulos.get(aid, "Atividade"), "segundos": s}
                         for aid, s in por_atividade.items()), key=lambda a: -a["segundos"])
    return {"total_segundos": sum(i["segundos"] for i in lista) + sum(por_atividade.values()),
            "em_andamento": em_andamento, "cards": lista, "atividades": atividades}


def _nomes(db):
    return {u.id: u.nome for u in db.query(UserDB).all()}


def _validar_para(db, user, para):
    validos = {g.id for g in relatorios_envio.gestores(db, user.id)}
    escolhidos = list(dict.fromkeys(para))
    if not escolhidos:
        raise HTTPException(status_code=400, detail="Escolha pelo menos um gestor.")
    if any(uid not in validos for uid in escolhidos):
        raise HTTPException(status_code=400, detail="Só dá para enviar a quem tem acesso à Gestão.")
    return escolhidos


def _serializar(db, user_id, rel, data, marcar_lidas=False):
    nomes = _nomes(db)
    conteudo = rel.conteudo if rel else ""
    envios = (db.query(RelatorioEnvioDB).filter(RelatorioEnvioDB.de_user_id == user_id, RelatorioEnvioDB.data == data)
              .order_by(RelatorioEnvioDB.enviado_em).all())
    # Uma conversa por gestor que recebeu; "lido" é a última vez que ele abriu.
    conversas = {}
    for e in envios:
        c = conversas.setdefault(e.para_user_id, {"gestor_id": e.para_user_id,
                                                  "gestor_nome": nomes.get(e.para_user_id, e.para_nome), "lido_em": None})
        c["lido_em"] = max(filter(None, [c["lido_em"], e.lido_em]), default=None)
    for gid, c in conversas.items():
        c["mensagens"] = relatorios_envio.mensagens(db, user_id, data, gid, user_id, nomes)
        # Conta antes de marcar: a tela destaca o que chegou desde a última visita.
        c["nao_lidas"] = db.query(RelatorioMensagemDB).filter(
            RelatorioMensagemDB.autor_id == user_id, RelatorioMensagemDB.data == data, RelatorioMensagemDB.gestor_id == gid,
            RelatorioMensagemDB.de_user_id != user_id, RelatorioMensagemDB.lida_em == None).count()  # noqa: E711
        if marcar_lidas and c["nao_lidas"]:
            relatorios_envio.marcar_lidas(db, user_id, data, gid, user_id)
    if marcar_lidas:
        db.commit()
    ag = (db.query(RelatorioAgendamentoDB)
          .filter(RelatorioAgendamentoDB.user_id == user_id, RelatorioAgendamentoDB.data == data).first())
    return {
        "data": data,
        "conteudo": conteudo,
        "atualizado_em": rel.atualizado_em if rel else None,
        "envios": [{"id": e.id, "para_id": e.para_user_id, "para_nome": nomes.get(e.para_user_id, e.para_nome),
                    "enviado_em": e.enviado_em, "origem": e.origem or "manual", "lido_em": e.lido_em,
                    "igual_ao_atual": e.conteudo == conteudo} for e in envios],
        "conversas": list(conversas.values()),
        "agendamento": {"enviar_em": ag.enviar_em, "status": ag.status,
                        "para": [{"id": uid, "nome": nomes.get(uid, "?")} for uid in (ag.para or [])]} if ag else None,
    }


@router.get("/relatorios")
def meus_relatorios(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Os dias em que a pessoa escreveu algo, do mais recente para trás."""
    rels = (db.query(RelatorioDB).filter(RelatorioDB.user_id == current_user.id)
            .order_by(RelatorioDB.data.desc()).limit(120).all())
    return [{"data": r.data, "resumo": " ".join((r.conteudo or "").split())[:120], "atualizado_em": r.atualizado_em}
            for r in rels]


@router.get("/relatorios/dia/{data}")
def relatorio_do_dia(data: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    _, ini, fim = _dia(data)
    return {**_serializar(db, current_user.id, _do_dia(db, current_user.id, data), data, marcar_lidas=True),
            "atividade": atividade_do_dia(db, current_user, ini, fim)}


@router.put("/relatorios/dia/{data}")
def salvar_relatorio(data: str, corpo: RelatorioUpdate, db: Session = Depends(get_db),
                     current_user: UserDB = Depends(get_current_user)):
    _dia(data)
    if len(corpo.conteudo) > MAX_CARACTERES:
        raise HTTPException(status_code=400, detail=f"O relatório passou de {MAX_CARACTERES} caracteres")
    rel = _do_dia(db, current_user.id, data)
    agora = datetime.now().isoformat()
    if not corpo.conteudo.strip():
        # Apagou tudo: o dia sai da lista de relatórios.
        if rel:
            db.delete(rel)
            db.commit()
        return _serializar(db, current_user.id, None, data)
    if rel is None:
        rel = RelatorioDB(id=f"rel-{uuid.uuid4().hex[:10]}", user_id=current_user.id, data=data, criado_em=agora)
        db.add(rel)
    rel.conteudo = corpo.conteudo
    rel.atualizado_em = agora
    db.commit()
    return _serializar(db, current_user.id, rel, data)


@router.get("/relatorios/destinatarios")
def destinatarios(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Gestores para quem dá para mandar o relatório; sem e-mail recebem só no Kyndo."""
    return [{"id": u.id, "nome": u.nome, "tem_email": bool(u.email)} for u in relatorios_envio.gestores(db, current_user.id)]


@router.post("/relatorios/dia/{data}/enviar")
def enviar_relatorio(data: str, corpo: EnvioRelatorio, db: Session = Depends(get_db),
                     current_user: UserDB = Depends(get_current_user)):
    _dia(data)
    rel = _do_dia(db, current_user.id, data)
    if not rel or not (rel.conteudo or "").strip():
        raise HTTPException(status_code=400, detail="Escreva o relatório antes de enviar.")
    para = _validar_para(db, current_user, corpo.para)
    relatorios_envio.enviar(db, current_user, data, para, rel.conteudo)
    return _serializar(db, current_user.id, rel, data)


# ------------------------------------------------------------- agendamento

@router.put("/relatorios/dia/{data}/agendamento")
def agendar_envio(data: str, corpo: AgendamentoRelatorio, db: Session = Depends(get_db),
                  current_user: UserDB = Depends(get_current_user)):
    """Marca (ou remarca) o envio do relatório deste dia. Sai o texto como
    estiver na hora marcada."""
    _dia(data)
    para = _validar_para(db, current_user, corpo.para)
    try:
        quando = datetime.fromisoformat(corpo.enviar_em).replace(second=0, microsecond=0, tzinfo=None)
    except ValueError:
        raise HTTPException(status_code=400, detail="Informe a data e a hora do envio.")
    agora = datetime.now()
    if quando <= agora:
        raise HTTPException(status_code=400, detail="Escolha um horário que ainda não passou.")
    if quando - agora > timedelta(days=31):
        raise HTTPException(status_code=400, detail="Dá para agendar até 31 dias à frente.")
    db.query(RelatorioAgendamentoDB).filter(RelatorioAgendamentoDB.user_id == current_user.id,
                                            RelatorioAgendamentoDB.data == data).delete()
    db.add(RelatorioAgendamentoDB(id=f"ag-{uuid.uuid4().hex[:10]}", user_id=current_user.id, data=data, para=para,
                                  enviar_em=quando.isoformat(), status="pendente", criado_em=agora.isoformat()))
    db.commit()
    return _serializar(db, current_user.id, _do_dia(db, current_user.id, data), data)


@router.delete("/relatorios/dia/{data}/agendamento")
def cancelar_agendamento(data: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    _dia(data)
    db.query(RelatorioAgendamentoDB).filter(RelatorioAgendamentoDB.user_id == current_user.id,
                                            RelatorioAgendamentoDB.data == data).delete()
    db.commit()
    return _serializar(db, current_user.id, _do_dia(db, current_user.id, data), data)


def _serializar_automatico(db, cfg):
    nomes = _nomes(db)
    if not cfg:
        return {"ativo": False, "dias": [0, 1, 2, 3, 4], "hora": "18:00", "para": [], "sem_texto": "nada", "para_nomes": []}
    return {"ativo": bool(cfg.ativo), "dias": cfg.dias or [], "hora": cfg.hora, "para": cfg.para or [],
            "sem_texto": cfg.sem_texto, "para_nomes": [nomes.get(uid, "?") for uid in (cfg.para or [])]}


@router.get("/relatorios/automatico")
def ver_automatico(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return _serializar_automatico(db, db.query(RelatorioAutomaticoDB).filter(RelatorioAutomaticoDB.user_id == current_user.id).first())


@router.put("/relatorios/automatico")
def configurar_automatico(corpo: EnvioAutomatico, db: Session = Depends(get_db),
                          current_user: UserDB = Depends(get_current_user)):
    cfg = db.query(RelatorioAutomaticoDB).filter(RelatorioAutomaticoDB.user_id == current_user.id).first()
    if corpo.ativo:
        dias = sorted({d for d in corpo.dias if 0 <= d <= 6})
        if not dias:
            raise HTTPException(status_code=400, detail="Escolha pelo menos um dia da semana.")
        try:
            h, m = (int(x) for x in corpo.hora.split(":"))
            assert 0 <= h <= 23 and 0 <= m <= 59
        except (ValueError, AssertionError):
            raise HTTPException(status_code=400, detail="Hora inválida.")
        para = _validar_para(db, current_user, corpo.para)
        if corpo.sem_texto not in ("nada", "resumo"):
            raise HTTPException(status_code=400, detail="Opção inválida.")
    if cfg is None:
        cfg = RelatorioAutomaticoDB(user_id=current_user.id)
        db.add(cfg)
    cfg.ativo = corpo.ativo
    if corpo.ativo:
        novo_horario = cfg.hora != f"{h:02d}:{m:02d}"
        cfg.dias, cfg.hora, cfg.para, cfg.sem_texto = dias, f"{h:02d}:{m:02d}", para, corpo.sem_texto
        agora = datetime.now()
        # Ligou (ou mudou a hora) depois do horário de hoje: começa amanhã,
        # em vez de disparar na hora.
        if novo_horario or cfg.ultimo_envio is None:
            cfg.ultimo_envio = agora.date().isoformat() if (agora.hour, agora.minute) >= (h, m) else None
    db.commit()
    return _serializar_automatico(db, cfg)


# ------------------------------------------------------- recebidos/conversa

@router.get("/relatorios/recebidos")
def recebidos(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Relatórios enviados à pessoa, um por (quem escreveu, dia), mais recente primeiro."""
    nomes = _nomes(db)
    grupos = {}
    for e in (db.query(RelatorioEnvioDB).filter(RelatorioEnvioDB.para_user_id == current_user.id)
              .order_by(RelatorioEnvioDB.enviado_em).all()):
        g = grupos.setdefault((e.de_user_id, e.data), {"autor_id": e.de_user_id, "autor_nome": nomes.get(e.de_user_id, e.de_nome),
                                                     "data": e.data, "lido": True})
        g["enviado_em"] = e.enviado_em
        g["resumo"] = " ".join((e.conteudo or "").split())[:120]
        g["lido"] = g["lido"] and e.lido_em is not None
    for (autor_id, data), g in grupos.items():
        g["mensagens_nao_lidas"] = db.query(RelatorioMensagemDB).filter(
            RelatorioMensagemDB.autor_id == autor_id, RelatorioMensagemDB.data == data,
            RelatorioMensagemDB.gestor_id == current_user.id, RelatorioMensagemDB.de_user_id != current_user.id,
            RelatorioMensagemDB.lida_em == None).count()  # noqa: E711
    return sorted(grupos.values(), key=lambda g: g["enviado_em"], reverse=True)[:200]


@router.get("/relatorios/recebidos/{autor_id}/{data}")
def relatorio_recebido(autor_id: str, data: str, db: Session = Depends(get_db),
                       current_user: UserDB = Depends(get_current_user)):
    _dia(data)
    envios = (db.query(RelatorioEnvioDB)
              .filter(RelatorioEnvioDB.de_user_id == autor_id, RelatorioEnvioDB.data == data,
                      RelatorioEnvioDB.para_user_id == current_user.id)
              .order_by(RelatorioEnvioDB.enviado_em).all())
    if not envios:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    agora = datetime.now().isoformat()
    for e in envios:
        e.lido_em = e.lido_em or agora
    relatorios_envio.marcar_lidas(db, autor_id, data, current_user.id, current_user.id)
    db.commit()
    nomes = _nomes(db)
    ultimo = envios[-1]
    return {
        "autor_id": autor_id, "autor_nome": nomes.get(autor_id, ultimo.de_nome), "data": data,
        "conteudo": ultimo.conteudo, "enviado_em": ultimo.enviado_em, "origem": ultimo.origem or "manual",
        "envios": len(envios),
        "mensagens": relatorios_envio.mensagens(db, autor_id, data, current_user.id, current_user.id, nomes),
    }


@router.post("/relatorios/conversa")
def mandar_mensagem(corpo: MensagemRelatorio, db: Session = Depends(get_db),
                    current_user: UserDB = Depends(get_current_user)):
    _dia(corpo.data)
    texto = corpo.texto.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Escreva a mensagem.")
    if len(texto) > 5000:
        raise HTTPException(status_code=400, detail="Mensagem com no máximo 5000 caracteres.")
    if current_user.id not in (corpo.autor_id, corpo.gestor_id):
        raise HTTPException(status_code=403, detail="Essa conversa não é sua.")
    if not relatorios_envio.participantes(db, corpo.autor_id, corpo.data, corpo.gestor_id):
        raise HTTPException(status_code=404, detail="Esse relatório não foi enviado a esse gestor.")
    autor = db.query(UserDB).filter(UserDB.id == corpo.autor_id).first()
    gestor = db.query(UserDB).filter(UserDB.id == corpo.gestor_id).first()
    if not autor or not gestor:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    relatorios_envio.responder(db, autor, corpo.data, gestor, current_user, texto)
    return {"mensagens": relatorios_envio.mensagens(db, autor.id, corpo.data, gestor.id, current_user.id, _nomes(db))}


# ---------------------------------------------------------------- modelos

def _validar_modelo(corpo: ModeloRelatorio):
    nome = " ".join(corpo.nome.split())
    if not nome:
        raise HTTPException(status_code=400, detail="Dê um nome ao modelo.")
    if len(nome) > MAX_NOME_MODELO:
        raise HTTPException(status_code=400, detail=f"Nome com no máximo {MAX_NOME_MODELO} caracteres.")
    if not corpo.conteudo.strip():
        raise HTTPException(status_code=400, detail="O modelo está vazio.")
    if len(corpo.conteudo) > MAX_CARACTERES:
        raise HTTPException(status_code=400, detail=f"O modelo passou de {MAX_CARACTERES} caracteres.")
    return nome


def _modelo_meu(db, user_id, modelo_id):
    m = db.query(RelatorioModeloDB).filter(RelatorioModeloDB.id == modelo_id, RelatorioModeloDB.user_id == user_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    return m


def _serializar_modelo(m):
    return {"id": m.id, "nome": m.nome, "conteudo": m.conteudo, "atualizado_em": m.atualizado_em}


@router.get("/relatorios/modelos")
def meus_modelos(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    modelos = (db.query(RelatorioModeloDB).filter(RelatorioModeloDB.user_id == current_user.id)
               .order_by(RelatorioModeloDB.nome).all())
    return [_serializar_modelo(m) for m in modelos]


@router.post("/relatorios/modelos")
def criar_modelo(corpo: ModeloRelatorio, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    nome = _validar_modelo(corpo)
    if db.query(RelatorioModeloDB).filter(RelatorioModeloDB.user_id == current_user.id).count() >= MAX_MODELOS:
        raise HTTPException(status_code=400, detail=f"Limite de {MAX_MODELOS} modelos — apague algum antes.")
    agora = datetime.now().isoformat()
    m = RelatorioModeloDB(id=f"mod-{uuid.uuid4().hex[:10]}", user_id=current_user.id, nome=nome,
                          conteudo=corpo.conteudo, criado_em=agora, atualizado_em=agora)
    db.add(m)
    db.commit()
    return _serializar_modelo(m)


@router.put("/relatorios/modelos/{modelo_id}")
def editar_modelo(modelo_id: str, corpo: ModeloRelatorio, db: Session = Depends(get_db),
                  current_user: UserDB = Depends(get_current_user)):
    m = _modelo_meu(db, current_user.id, modelo_id)
    m.nome = _validar_modelo(corpo)
    m.conteudo = corpo.conteudo
    m.atualizado_em = datetime.now().isoformat()
    db.commit()
    return _serializar_modelo(m)


@router.delete("/relatorios/modelos/{modelo_id}")
def apagar_modelo(modelo_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db.delete(_modelo_meu(db, current_user.id, modelo_id))
    db.commit()
    return {"ok": True}
