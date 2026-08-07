from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class LoginRequest(BaseModel):
    nome: str
    senha: str


class UserCreate(BaseModel):
    nome: str
    senha: str
    role: str = "user"  # vestigial — kept only for request-shape backward compatibility, ignored by permission logic


class PasswordUpdate(BaseModel):
    nova_senha: str


class ColSchema(BaseModel):
    id: str
    titulo: str
    cor: str
    ordem: int
    publica: bool = False
    auto_andamento: bool = False
    auto_concluido: bool = False
    arquivado: bool = False


class CardSchema(BaseModel):
    id: Optional[str] = None
    titulo: str
    descricao: Optional[str] = ""
    status: str
    prioridade: str = "Normal"
    autor: str
    prazo: Optional[str] = ""
    checklist: List[Dict[str, Any]] = []
    comentarios: List[Dict[str, Any]] = []
    responsaveis: List[str] = []
    github_url: Optional[str] = ""
    ordem: int = 0


class CardReorderItem(BaseModel):
    id: str
    ordem: int


class ShareEntry(BaseModel):
    user_id: str
    nivel: str  # 'ver' | 'editar'


class UserNoteSchema(BaseModel):
    titulo: str = "Nova Nota"
    conteudo: str = ""
    tipo: str = "texto"
    canvas_data: Optional[Dict[str, Any]] = None
    card_id: Optional[str] = None
    publico: bool = False
    compartilhado_com: List[ShareEntry] = []


class DrawingSchema(BaseModel):
    titulo: str = "Novo Desenho"
    data: str = ""
    card_id: Optional[str] = None
    publico: bool = False
    compartilhado_com: List[ShareEntry] = []


class SuggestionCreate(BaseModel):
    texto: str
    identificacao: str  # nome de quem está escrevendo — obrigatório pois a conta pode ser compartilhada
    campo_alvo: Optional[str] = None
    valor_proposto: Optional[str] = None


class SuggestionDecision(BaseModel):
    status: str  # 'aceita' | 'rejeitada'
    prazo_entrega: Optional[str] = None  # obrigatório quando status == 'aceita'
    motivo_recusa: Optional[str] = None  # obrigatório quando status == 'rejeitada'


class RoleCreate(BaseModel):
    nome: str
    cor: str = "#94a3b8"
    permissoes: Dict[str, bool] = {}
    colunas_restritas: bool = False
    colunas_visiveis: List[str] = []


class RoleUpdate(BaseModel):
    nome: Optional[str] = None
    cor: Optional[str] = None
    permissoes: Optional[Dict[str, bool]] = None
    # colunas_visiveis itself can't use the "None = don't touch" convention the
    # other fields use, because None is the valid target value ("no
    # restriction") — colunas_restritas disambiguates the caller's intent:
    # None = leave alone, True = apply colunas_visiveis below, False = clear it.
    colunas_restritas: Optional[bool] = None
    colunas_visiveis: Optional[List[str]] = None


class UserRolesUpdate(BaseModel):
    role_ids: List[str] = []
