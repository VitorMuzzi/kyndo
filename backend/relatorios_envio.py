"""Envio de relatórios a gestores: na hora, agendado ou automático, e a
conversa entre quem escreveu e cada gestor.

O relatório enviado fica guardado no Kyndo (RelatorioEnvioDB, com o texto
como estava na hora) — o gestor lê e responde na tela de Relatórios. O e-mail
é um aviso a mais: sai para quem tem e-mail e não desligou o aviso
"relatorio_recebido"; sem e-mail, o gestor recebe só no Kyndo.

Cada conversa é de um relatório (pessoa + dia) com um gestor: dois gestores
que recebem o mesmo relatório conversam em separado com quem escreveu."""
import logging
import uuid
from datetime import date, datetime, timedelta

import email_envio
import notificacoes
from models import (
    RelatorioAgendamentoDB, RelatorioAutomaticoDB, RelatorioDB, RelatorioEnvioDB, RelatorioMensagemDB, UserDB,
)
from rbac import get_user_permissions

log = logging.getLogger("kyndo.relatorios")

DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def gestores(db, exceto_id=None):
    return [u for u in db.query(UserDB).order_by(UserDB.nome).all()
            if u.id != exceto_id and "acessar_gestao" in get_user_permissions(db, u.id)]


def data_br(data):
    return date.fromisoformat(data).strftime("%d/%m/%Y")


def assunto_relatorio(nome, data):
    d = date.fromisoformat(data)
    return f"Relatório de {nome} — {d.strftime('%d/%m/%Y')} ({DIAS_SEMANA[d.weekday()]})"


def link_recebido(autor_id, data):
    return email_envio.link(f"/?relatorio_de={autor_id}&dia={data}")


def link_meu(data):
    return email_envio.link(f"/?meu_relatorio={data}")


def _horas(segundos):
    return f"{segundos // 3600}h{segundos % 3600 // 60:02d}"


def resumo_em_texto(data, atividade):
    """O mesmo resumo do botão "Inserir no relatório" da tela — para o envio
    automático de quem não escreveu nada no dia."""
    linhas = [f"Resumo de {data_br(data)} — {_horas(atividade['total_segundos'])} cronometradas (gerado pelo Kyndo)"]
    for c in atividade["cards"]:
        linhas.append(f"• {c['titulo'] or 'Card excluído'}" + (f" — {_horas(c['segundos'])}" if c["segundos"] else ""))
        for e in c["etapas"]:
            if e["texto"]:
                linhas.append(f"   - {e['texto']}: {_horas(e['segundos'])}")
        for a in c["acoes"]:
            if a["acao"] in ("etapa_concluida", "subetapa_concluida"):
                linhas.append(f"   - {a['rotulo']}: {a['detalhe']}")
    for a in atividade.get("atividades", []):
        linhas.append(f"• {a['titulo']} (atividade) — {_horas(a['segundos'])}")
    return "\n".join(linhas) if len(linhas) > 1 else ""


def enviar(db, autor, data, para_ids, conteudo, origem="manual", pular_repetidos=False):
    """Registra o envio para cada gestor e manda o e-mail de aviso. Gestor que
    perdeu o acesso à Gestão é ignorado. `pular_repetidos` não reenvia a quem
    já recebeu exatamente este texto (envios agendados e automáticos)."""
    validos = {g.id: g for g in gestores(db, autor.id)}
    agora = datetime.now().isoformat()
    modos = notificacoes.modos(db)
    enviados = []
    for uid in dict.fromkeys(para_ids):
        g = validos.get(uid)
        if not g:
            continue
        if pular_repetidos:
            ultimo = (db.query(RelatorioEnvioDB)
                      .filter(RelatorioEnvioDB.de_user_id == autor.id, RelatorioEnvioDB.data == data,
                              RelatorioEnvioDB.para_user_id == g.id)
                      .order_by(RelatorioEnvioDB.enviado_em.desc()).first())
            if ultimo and ultimo.conteudo == conteudo:
                continue
        db.add(RelatorioEnvioDB(id=f"env-{uuid.uuid4().hex[:10]}", data=data, de_user_id=autor.id, de_nome=autor.nome,
                                para_user_id=g.id, para_nome=g.nome, conteudo=conteudo, enviado_em=agora, origem=origem))
        enviados.append(g)
        if g.email and notificacoes.alcance(db, g, "relatorio_recebido", modos) != "nenhum":
            email_envio.enviar(
                g.email, assunto_relatorio(autor.nome, data), [conteudo],
                botao=("Abrir e responder no Kyndo", link_recebido(autor.id, data)),
                rodape=(f"Relatório escrito por {autor.nome} no Kyndo. Responda pelo botão acima"
                        + (" ou respondendo este e-mail." if autor.email else ".")),
                responder_para=autor.email or None,
            )
    db.commit()
    return enviados


# ---------------------------------------------------------------- conversa

def participantes(db, autor_id, data, gestor_id):
    """A conversa existe se o relatório foi enviado a esse gestor."""
    return db.query(RelatorioEnvioDB).filter(
        RelatorioEnvioDB.de_user_id == autor_id, RelatorioEnvioDB.data == data,
        RelatorioEnvioDB.para_user_id == gestor_id).first() is not None


def mensagens(db, autor_id, data, gestor_id, eu_id, nomes):
    msgs = (db.query(RelatorioMensagemDB)
            .filter(RelatorioMensagemDB.autor_id == autor_id, RelatorioMensagemDB.data == data,
                    RelatorioMensagemDB.gestor_id == gestor_id)
            .order_by(RelatorioMensagemDB.criado_em).all())
    return [{"id": m.id, "eu": m.de_user_id == eu_id, "nome": nomes.get(m.de_user_id, "?"),
             "texto": m.texto, "criado_em": m.criado_em} for m in msgs]


def marcar_lidas(db, autor_id, data, gestor_id, leitor_id):
    """Quem abre a conversa leu as mensagens do outro lado."""
    agora = datetime.now().isoformat()
    (db.query(RelatorioMensagemDB)
     .filter(RelatorioMensagemDB.autor_id == autor_id, RelatorioMensagemDB.data == data,
             RelatorioMensagemDB.gestor_id == gestor_id, RelatorioMensagemDB.de_user_id != leitor_id,
             RelatorioMensagemDB.lida_em == None)  # noqa: E711
     .update({"lida_em": agora}, synchronize_session=False))


def responder(db, autor, data, gestor, quem, texto):
    db.add(RelatorioMensagemDB(id=f"msg-{uuid.uuid4().hex[:10]}", autor_id=autor.id, data=data, gestor_id=gestor.id,
                               de_user_id=quem.id, texto=texto, criado_em=datetime.now().isoformat()))
    db.commit()
    outro = gestor if quem.id == autor.id else autor
    if outro.email and email_envio.configurado() and notificacoes.alcance(db, outro, "relatorio_resposta") != "nenhum":
        sobre = "o seu relatório" if outro.id == autor.id else f"o relatório de {autor.nome}"
        email_envio.enviar(
            outro.email, f"Kyndo: {quem.nome} respondeu sobre {sobre} de {data_br(data)}",
            [f"Olá, {outro.nome}.", f"{quem.nome} escreveu sobre {sobre} de {data_br(data)}:", texto],
            botao=("Ver a conversa no Kyndo", link_meu(data) if outro.id == autor.id else link_recebido(autor.id, data)),
            rodape=notificacoes.RODAPE_AVISO,
        )


def nao_lidos(db, user):
    """Para o pontinho no menu: relatórios recebidos ainda não abertos +
    mensagens do outro lado ainda não lidas, nas conversas da pessoa."""
    recebidos = {(e.de_user_id, e.data) for e in db.query(RelatorioEnvioDB).filter(
        RelatorioEnvioDB.para_user_id == user.id, RelatorioEnvioDB.lido_em == None).all()}  # noqa: E711
    msgs = db.query(RelatorioMensagemDB).filter(
        RelatorioMensagemDB.de_user_id != user.id, RelatorioMensagemDB.lida_em == None,  # noqa: E711
        (RelatorioMensagemDB.autor_id == user.id) | (RelatorioMensagemDB.gestor_id == user.id)).count()
    return len(recebidos) + msgs


# ------------------------------------------------------- agendados/automático

def _texto_do_dia(db, user_id, data):
    rel = db.query(RelatorioDB).filter(RelatorioDB.user_id == user_id, RelatorioDB.data == data).first()
    return (rel.conteudo or "") if rel else ""


def _automatico_devido(cfg, agora):
    if not cfg.ativo or not cfg.para or agora.weekday() not in (cfg.dias or []):
        return False
    try:
        h, m = (int(x) for x in (cfg.hora or "").split(":"))
    except ValueError:
        return False
    return (agora.hour, agora.minute) >= (h, m) and cfg.ultimo_envio != agora.date().isoformat()


def processar_agendados(db, agora=None):
    """Chamado pelo agendador a cada minuto: envios marcados que já venceram
    e o envio automático de quem configurou para hoje e já passou da hora."""
    from routers.relatorios import atividade_do_dia  # import tardio: o router importa este módulo

    agora = agora or datetime.now()
    for ag in db.query(RelatorioAgendamentoDB).filter(RelatorioAgendamentoDB.status == "pendente",
                                                      RelatorioAgendamentoDB.enviar_em <= agora.isoformat()).all():
        autor = db.query(UserDB).filter(UserDB.id == ag.user_id).first()
        texto = _texto_do_dia(db, ag.user_id, ag.data)
        if not autor or not texto.strip():
            # Fica visível na tela até a pessoa agendar de novo ou dispensar.
            ag.status = "vazio"
            db.commit()
            continue
        enviar(db, autor, ag.data, ag.para or [], texto, origem="agendado", pular_repetidos=True)
        db.delete(ag)
        db.commit()

    hoje = agora.date().isoformat()
    for cfg in db.query(RelatorioAutomaticoDB).all():
        if not _automatico_devido(cfg, agora):
            continue
        cfg.ultimo_envio = hoje  # marca antes: melhor faltar um envio do que mandar dois
        db.commit()
        autor = db.query(UserDB).filter(UserDB.id == cfg.user_id).first()
        if not autor:
            continue
        texto = _texto_do_dia(db, autor.id, hoje)
        if not texto.strip() and cfg.sem_texto == "resumo":
            ini = datetime.combine(agora.date(), datetime.min.time())
            texto = resumo_em_texto(hoje, atividade_do_dia(db, autor, ini, ini + timedelta(days=1)))
        if texto.strip():
            enviar(db, autor, hoje, cfg.para, texto, origem="automatico", pular_repetidos=True)


def processar_com_log(fabrica_sessao):
    db = fabrica_sessao()
    try:
        processar_agendados(db)
    except Exception:  # noqa: BLE001
        log.exception("Falha nos envios agendados de relatório")
    finally:
        db.close()
