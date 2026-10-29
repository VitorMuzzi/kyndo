from sqlalchemy import Column, String, Boolean, Integer, JSON

from database import Base


class UserDB(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    senha = Column(String)
    role = Column(String)
    senha_temporaria = Column(Boolean, default=False)
    senha_versao = Column(Integer, default=0)  # sobe a cada troca de senha; token com versão diferente é recusado
    email = Column(String, nullable=True, index=True)  # minúsculo; único (conferido em routers/emails.py)
    email_prefs = Column(JSON, nullable=True)  # {tipo de aviso: bool}; ausente = ligado — ver notificacoes.py


class ColumnDB(Base):
    __tablename__ = "columns"
    id = Column(String, primary_key=True, index=True)
    titulo = Column(String)
    cor = Column(String)
    ordem = Column(Integer)
    publica = Column(Boolean, default=False)
    auto_andamento = Column(Boolean, default=False)
    auto_concluido = Column(Boolean, default=False)
    arquivado = Column(Boolean, default=False)


class CardDB(Base):
    __tablename__ = "cards"
    id = Column(String, primary_key=True, index=True)
    titulo = Column(String)
    descricao = Column(String)
    status = Column(String)
    prioridade = Column(String)
    autor = Column(String)
    prazo = Column(String, nullable=True)
    data_criacao = Column(String)
    checklist = Column(JSON)
    comentarios = Column(JSON)
    responsaveis = Column(JSON)
    github_url = Column(String, nullable=True)
    ordem = Column(Integer, default=0)
    updated_em = Column(String, default="")
    alteracoes = Column(Integer, default=0)
    recorrente = Column(Boolean, default=False)
    recorrencia_dias = Column(Integer, nullable=True)
    recorrencia_coluna_reset = Column(String, nullable=True)
    recorrencia_proximo_reset = Column(String, nullable=True)


class CardSeenDB(Base):
    __tablename__ = "card_seen"
    card_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, primary_key=True, index=True)
    visto_em = Column(String, default="")
    visto_versao = Column(Integer, default=0)


class ItemSeenDB(Base):
    __tablename__ = "item_seen"
    card_id = Column(String, primary_key=True, index=True)
    item_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, primary_key=True, index=True)
    visto_versao = Column(Integer, default=0)


class AuditLogDB(Base):
    __tablename__ = "audit_log"
    id = Column(String, primary_key=True, index=True)
    card_id = Column(String, index=True, nullable=True)
    card_titulo = Column(String, default="")
    usuario = Column(String)
    acao = Column(String)
    campo = Column(String, nullable=True)
    valor_antigo = Column(String, nullable=True)
    valor_novo = Column(String, nullable=True)
    detalhe = Column(String, nullable=True)
    data = Column(String)
    # O que o registro alterou fora de card (nota, usuário, cargo...); nulo = card.
    alvo_tipo = Column(String, nullable=True)
    alvo_id = Column(String, nullable=True, index=True)
    # Dados pra desfazer a alteração — ver reversao.py. Nulo em registros
    # antigos e nos que são só informativos.
    reversao = Column(JSON, nullable=True)
    lixeira_id = Column(String, nullable=True, index=True)
    revertido_em = Column(String, nullable=True)
    revertido_por = Column(String, nullable=True)


class LixeiraDB(Base):
    """Tudo que é excluído vem pra cá com uma fotografia completa (linha
    principal e o que depende dela) e fica recuperável por PRAZO_DIAS — ver
    lixeira.py. Recuperar apaga a linha daqui; expirar também, de vez."""
    __tablename__ = "lixeira"
    id = Column(String, primary_key=True, index=True)
    tipo = Column(String, index=True)  # card, anexo, sugestao, nota, desenho, usuario, cargo, tempo
    alvo_id = Column(String, index=True)
    titulo = Column(String, default="")
    card_id = Column(String, nullable=True, index=True)  # card a que o item pertencia, quando pertence
    dono_id = Column(String, nullable=True, index=True)  # dono de nota/desenho — recupera pela própria lixeira
    dados = Column(JSON)
    excluido_por = Column(String)
    excluido_em = Column(String, index=True)


class RoleDB(Base):
    __tablename__ = "roles"
    id = Column(String, primary_key=True, index=True)
    nome = Column(String, unique=True)
    cor = Column(String, default="#94a3b8")
    protegido = Column(Boolean, default=False)
    permissoes = Column(JSON, default=dict)
    ordem = Column(Integer, default=0)
    colunas_visiveis = Column(JSON, nullable=True, default=None)  # None = sem restrição (vê tudo)


class UserRoleDB(Base):
    __tablename__ = "user_roles"
    user_id = Column(String, primary_key=True, index=True)
    role_id = Column(String, primary_key=True, index=True)


class SuggestionDB(Base):
    __tablename__ = "suggestions"
    id = Column(String, primary_key=True, index=True)
    card_id = Column(String, index=True)
    autor = Column(String)
    identificacao = Column(String, nullable=True)  # nome de quem escreveu, digitado à mão — várias pessoas usam a mesma conta
    texto = Column(String)
    campo_alvo = Column(String, nullable=True)
    valor_proposto = Column(String, nullable=True)
    status = Column(String, default="pendente")
    data = Column(String)
    decidido_por = Column(String, nullable=True)
    decidido_em = Column(String, nullable=True)
    prazo_entrega = Column(String, nullable=True)
    motivo_recusa = Column(String, nullable=True)
    valor_anterior = Column(String, nullable=True)


class AttachmentDB(Base):
    __tablename__ = "attachments"
    id = Column(String, primary_key=True, index=True)
    card_id = Column(String, index=True)
    nome_original = Column(String)
    nome_arquivo = Column(String)  # nome único no disco — nunca o nome enviado pelo usuário
    content_type = Column(String, nullable=True)
    tamanho = Column(Integer)
    enviado_por = Column(String)
    enviado_em = Column(String)


class TimeEntryDB(Base):
    """Um intervalo de trabalho cronometrado num card — ou numa atividade fora
    de card (atividade_id preenchido, card_id nulo). fim nulo = cronômetro
    rodando; cada pessoa tem no máximo um rodando por vez."""
    __tablename__ = "time_entries"
    id = Column(String, primary_key=True, index=True)
    card_id = Column(String, index=True)
    atividade_id = Column(String, nullable=True, index=True)
    item_id = Column(String, nullable=True)  # etapa/sub-etapa do checklist, opcional
    user_id = Column(String, index=True)
    usuario = Column(String)  # nome na hora do registro, pra exibir sem join
    inicio = Column(String)
    fim = Column(String, nullable=True)


class NoteDB(Base):
    __tablename__ = "notes"
    user_id = Column(String, primary_key=True, index=True)
    conteudo = Column(String, default="")


class UserNoteDB(Base):
    __tablename__ = "user_notes"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    titulo = Column(String, default="Nova Nota")
    conteudo = Column(String, default="")
    tipo = Column(String, default="texto")
    canvas_data = Column(JSON, default=None)
    criado_em = Column(String, default="")
    card_id = Column(String, nullable=True, default=None)
    publico = Column(Boolean, default=False)
    compartilhado_com = Column(JSON, default=list)


class DrawingDB(Base):
    __tablename__ = "drawings"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    titulo = Column(String, default="Novo Desenho")
    data = Column(String, default="")
    criado_em = Column(String, default="")
    card_id = Column(String, nullable=True, default=None)
    publico = Column(Boolean, default=False)
    compartilhado_com = Column(JSON, default=list)


class PedidoSenhaDB(Base):
    """Pedido de "esqueci a senha". Não há e-mail no sistema, então o pedido fica
    esperando alguém com trocar_senha_outros definir uma senha temporária.
    Sai daqui quando a senha muda (por qualquer um) ou a pessoa entra."""
    __tablename__ = "pedidos_senha"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    criado_em = Column(String)


class TokenSenhaDB(Base):
    """Link de "esqueci a senha" enviado por e-mail. Guarda só o hash do
    token (quem lê o banco não consegue usar o link); vale 1 hora e uma vez."""
    __tablename__ = "tokens_senha"
    id = Column(String, primary_key=True, index=True)  # sha256 do token
    user_id = Column(String, index=True)
    criado_em = Column(String)
    expira_em = Column(String)


class ConfigDB(Base):
    """Configurações gerais do sistema que se mudam pela tela (chave → JSON)."""
    __tablename__ = "config"
    chave = Column(String, primary_key=True)
    valor = Column(JSON)


class CardSeguidorDB(Base):
    """Quem segue um card (botão "Seguir") — recebe os avisos dele no alcance "seguidos"."""
    __tablename__ = "card_seguidores"
    card_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, primary_key=True, index=True)


class FilaAvisoDB(Base):
    """Avisos de quem escolheu receber tudo num resumo diário — saem às 18h."""
    __tablename__ = "fila_avisos"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    card_id = Column(String, nullable=True)
    card_titulo = Column(String, default="")
    texto = Column(String)
    criado_em = Column(String)


class RelatorioDB(Base):
    """Relatório do dia que a pessoa escreve na tela de Relatórios — um por dia."""
    __tablename__ = "relatorios"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    data = Column(String, index=True)  # AAAA-MM-DD
    conteudo = Column(String, default="")
    criado_em = Column(String)
    atualizado_em = Column(String)


class RelatorioEnvioDB(Base):
    """Um relatório mandado a um gestor. Guarda o texto como foi enviado:
    editar o relatório depois não muda o que o gestor recebeu."""
    __tablename__ = "relatorio_envios"
    id = Column(String, primary_key=True)
    data = Column(String, index=True)  # dia do relatório, AAAA-MM-DD
    de_user_id = Column(String, index=True)
    de_nome = Column(String)
    para_user_id = Column(String, index=True)
    para_nome = Column(String)
    conteudo = Column(String)
    enviado_em = Column(String)
    origem = Column(String, default="manual")  # manual | agendado | automatico
    lido_em = Column(String, nullable=True)    # quando o gestor abriu no Kyndo


class RelatorioModeloDB(Base):
    """Modelo de relatório salvo por uma pessoa, para começar o texto do dia."""
    __tablename__ = "relatorio_modelos"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    nome = Column(String)
    conteudo = Column(String, default="")
    criado_em = Column(String)
    atualizado_em = Column(String)


class AtividadeDB(Base):
    """Atividade fora de card (saída de campo, reunião...). Pode estar agendada
    (agendada_inicio/fim, aparece no Cronograma antes de acontecer) e ter
    tempo registrado em TimeEntryDB.atividade_id."""
    __tablename__ = "atividades"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    titulo = Column(String)
    agendada_inicio = Column(String, nullable=True)
    agendada_fim = Column(String, nullable=True)
    criado_em = Column(String)


class RelatorioMensagemDB(Base):
    """Mensagem da conversa sobre um relatório (pessoa + dia) com um gestor."""
    __tablename__ = "relatorio_mensagens"
    id = Column(String, primary_key=True)
    autor_id = Column(String, index=True)   # quem escreveu o relatório
    data = Column(String, index=True)
    gestor_id = Column(String, index=True)
    de_user_id = Column(String)             # quem escreveu esta mensagem
    texto = Column(String)
    criado_em = Column(String)
    lida_em = Column(String, nullable=True)


class RelatorioAgendamentoDB(Base):
    """Envio de um relatório marcado para uma data e hora. status "vazio" =
    chegou a hora e não havia texto: fica na tela até a pessoa resolver."""
    __tablename__ = "relatorio_agendamentos"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    data = Column(String)
    para = Column(JSON, default=list)
    enviar_em = Column(String, index=True)
    status = Column(String, default="pendente")
    criado_em = Column(String)


class RelatorioAutomaticoDB(Base):
    """Envio automático do relatório do dia, nos dias da semana e hora escolhidos."""
    __tablename__ = "relatorio_automatico"
    user_id = Column(String, primary_key=True)
    ativo = Column(Boolean, default=False)
    dias = Column(JSON, default=list)       # 0 = segunda ... 6 = domingo
    hora = Column(String, default="18:00")
    para = Column(JSON, default=list)
    sem_texto = Column(String, default="nada")  # nada | resumo
    ultimo_envio = Column(String, nullable=True)
