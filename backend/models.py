from sqlalchemy import Column, String, Boolean, Integer, JSON

from database import Base


class UserDB(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    senha = Column(String)
    role = Column(String)
    senha_temporaria = Column(Boolean, default=False)


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
