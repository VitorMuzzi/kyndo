from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, Boolean, Integer, JSON, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timedelta, timezone
import uuid
import jwt
import bcrypt
import os
import time
from collections import defaultdict

# Security config — set SECRET_KEY env var in production
SECRET_KEY = os.getenv("SECRET_KEY", "coloque_sua_chave_secreta_aqui")
ALGORITHM = "HS256"

security = HTTPBearer()

# In-memory rate limiter for /login
_login_attempts: dict = defaultdict(list)
_RATE_WINDOW = 60   # seconds
_RATE_MAX    = 10   # attempts per window

def check_rate_limit(ip: str):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_WINDOW]
    if len(_login_attempts[ip]) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 1 minuto.")
    _login_attempts[ip].append(now)

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# Database config — path anchored to this file's directory, never relative to cwd
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demandas.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
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
    card_id      = Column(String, primary_key=True, index=True)
    user_id      = Column(String, primary_key=True, index=True)
    visto_em     = Column(String, default="")
    visto_versao = Column(Integer, default=0)

class NoteDB(Base):
    __tablename__ = "notes"
    user_id  = Column(String, primary_key=True, index=True)
    conteudo = Column(String, default="")

class UserNoteDB(Base):
    __tablename__ = "user_notes"
    id        = Column(String, primary_key=True, index=True)
    user_id   = Column(String, index=True)
    titulo    = Column(String, default="Nova Nota")
    conteudo  = Column(String, default="")
    tipo      = Column(String, default="texto")
    canvas_data = Column(JSON, default=None)
    criado_em = Column(String, default="")
    card_id   = Column(String, nullable=True, default=None)
    publico   = Column(Boolean, default=False)
    compartilhado_com = Column(JSON, default=list)

class DrawingDB(Base):
    __tablename__ = "drawings"
    id        = Column(String, primary_key=True, index=True)
    user_id   = Column(String, index=True)
    titulo    = Column(String, default="Novo Desenho")
    data      = Column(String, default="")
    criado_em = Column(String, default="")
    card_id   = Column(String, nullable=True, default=None)
    publico   = Column(Boolean, default=False)
    compartilhado_com = Column(JSON, default=list)

def _migrate_drawings_table():
    """The old 'drawings' table was a singleton (user_id as PK, no id/titulo).
    create_all() never touches an existing table, so rename it out of the way
    first; the new schema gets created fresh below, then legacy rows get
    copied in by _copy_legacy_drawings(). Idempotent: no-ops once already migrated."""
    with engine.connect() as conn:
        exists = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drawings'"
        )).fetchone()
        if not exists:
            return
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(drawings)"))]
        if 'id' in cols:
            return
        conn.execute(text("ALTER TABLE drawings RENAME TO drawings_old_singleton"))
        # SQLite keeps index names attached across a table rename; drop it so
        # create_all() below can create a same-named index on the new table.
        conn.execute(text("DROP INDEX IF EXISTS ix_drawings_user_id"))
        conn.commit()

_migrate_drawings_table()

Base.metadata.create_all(bind=engine)

def _copy_legacy_drawings():
    with engine.connect() as conn:
        old = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drawings_old_singleton'"
        )).fetchone()
        if not old:
            return
        rows = conn.execute(text("SELECT user_id, data FROM drawings_old_singleton")).fetchall()
        for user_id, data in rows:
            if not data:
                continue
            dup = conn.execute(
                text("SELECT 1 FROM drawings WHERE user_id=:uid LIMIT 1"), {"uid": user_id}
            ).fetchone()
            if dup:
                continue
            conn.execute(text(
                "INSERT INTO drawings (id, user_id, titulo, data, criado_em, card_id, publico, compartilhado_com) "
                "VALUES (:id, :uid, :titulo, :data, :criado_em, NULL, 0, '[]')"
            ), {
                "id": f"drawing-{uuid.uuid4().hex[:8]}",
                "uid": user_id,
                "titulo": "Meu Desenho",
                "data": data,
                "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            })
        conn.commit()

_copy_legacy_drawings()

# Migrations
for stmt in [
    "ALTER TABLE cards ADD COLUMN responsaveis TEXT",
    "ALTER TABLE cards ADD COLUMN github_url VARCHAR",
    "ALTER TABLE cards ADD COLUMN ordem INTEGER DEFAULT 0",
    "ALTER TABLE cards ADD COLUMN updated_em VARCHAR",
    "ALTER TABLE cards ADD COLUMN alteracoes INTEGER DEFAULT 0",
    "ALTER TABLE card_seen ADD COLUMN visto_versao INTEGER DEFAULT 0",
    "ALTER TABLE user_notes ADD COLUMN card_id VARCHAR",
    "ALTER TABLE user_notes ADD COLUMN publico BOOLEAN DEFAULT 0",
    "ALTER TABLE user_notes ADD COLUMN compartilhado_com TEXT DEFAULT '[]'",
]:
    with engine.connect() as conn:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except Exception:
            pass

def _backfill_card_notifications():
    """Cards created before the notification feature shipped have no
    updated_em/card_seen rows. Backfill both with the SAME timestamp so
    nobody gets a flood of false 'changed' badges on pre-existing cards —
    only edits made after this point should ever trigger a badge."""
    now_iso = datetime.now().isoformat()
    with engine.connect() as conn:
        conn.execute(text("UPDATE cards SET updated_em = :now WHERE updated_em IS NULL OR updated_em = ''"), {"now": now_iso})
        card_ids = [r[0] for r in conn.execute(text("SELECT id FROM cards"))]
        user_ids = [r[0] for r in conn.execute(text("SELECT id FROM users"))]
        for cid in card_ids:
            for uid in user_ids:
                exists = conn.execute(
                    text("SELECT 1 FROM card_seen WHERE card_id=:cid AND user_id=:uid"), {"cid": cid, "uid": uid}
                ).fetchone()
                if exists:
                    continue
                conn.execute(text(
                    "INSERT INTO card_seen (card_id, user_id, visto_em) VALUES (:cid, :uid, :now)"
                ), {"cid": cid, "uid": uid, "now": now_iso})
        conn.commit()

_backfill_card_notifications()

app = FastAPI(title="Kyndo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth dependencies
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user

def require_admin(current_user: UserDB = Depends(get_current_user)):
    if current_user.role not in ('admin', 'superadmin'):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user

def require_superadmin(current_user: UserDB = Depends(get_current_user)):
    if current_user.role != 'superadmin':
        raise HTTPException(status_code=403, detail="Acesso restrito ao superadmin")
    return current_user

# DB Initialization
def init_db():
    db = SessionLocal()
    admin = db.query(UserDB).filter(UserDB.nome == "admin").first()
    if not admin:
        hashed_pw = get_password_hash("admin")
        db.add(UserDB(id=str(uuid.uuid4()), nome="admin", senha=hashed_pw, role="superadmin", senha_temporaria=False))
    elif admin.role == "admin":
        admin.role = "superadmin"

    if db.query(ColumnDB).count() == 0:
        cols = [
            ColumnDB(id="col-1", titulo="IDEIAS DE PROJETOS", cor="#fef08a", ordem=0, publica=True),
            ColumnDB(id="col-2", titulo="PROJETOS A SEREM INICIADOS", cor="#bfdbfe", ordem=1),
            ColumnDB(id="col-3", titulo="EM ANDAMENTO", cor="#fecaca", ordem=2, auto_andamento=True),
            ColumnDB(id="col-4", titulo="CONCLUÍDO", cor="#bbf7d0", ordem=3, auto_concluido=True)
        ]
        db.add_all(cols)
    db.commit()
    db.close()

init_db()

# Pydantic Schemas
class LoginRequest(BaseModel):
    nome: str
    senha: str

class UserCreate(BaseModel):
    nome: str
    senha: str
    role: str

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

# API Routes
@app.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    user = db.query(UserDB).filter(UserDB.nome == req.nome).first()
    if not user or not verify_password(req.senha, user.senha):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {"sub": user.id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "id": user.id,
        "nome": user.nome,
        "role": user.role,
        "senha_temporaria": user.senha_temporaria,
        "token": encoded_jwt
    }

@app.get("/users")
def get_users(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return db.query(UserDB).all()

@app.post("/users")
def create_user(req: UserCreate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_admin)):
    if db.query(UserDB).filter(UserDB.nome == req.nome).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    hashed_pw = get_password_hash(req.senha)
    novo = UserDB(id=str(uuid.uuid4()), nome=req.nome, senha=hashed_pw, role=req.role, senha_temporaria=True)
    db.add(novo)
    db.commit()
    return {"msg": "criado"}

@app.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(require_superadmin)):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user and user.nome != "admin":
        db.delete(user)
        db.commit()
    return {"msg": "deletado"}

@app.put("/users/{user_id}/password")
def update_password(user_id: str, req: PasswordUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    if current_user.id != user_id and current_user.role not in ('admin', 'superadmin'):
        raise HTTPException(status_code=403, detail="Sem permissão para alterar senha de outro usuário")
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.senha = get_password_hash(req.nova_senha)
    user.senha_temporaria = False
    db.commit()
    return {"msg": "senha atualizada"}

@app.get("/columns")
def get_columns(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return db.query(ColumnDB).filter(ColumnDB.arquivado == False).order_by(ColumnDB.ordem).all()

@app.post("/columns")
def create_column(col: ColSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(require_admin)):
    nova = ColumnDB(**col.model_dump())
    db.add(nova)
    db.commit()
    return nova

@app.put("/columns/{col_id}")
def update_column(col_id: str, col: ColSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(require_admin)):
    db_col = db.query(ColumnDB).filter(ColumnDB.id == col_id).first()
    if db_col:
        for key, value in col.model_dump().items():
            setattr(db_col, key, value)
        db.commit()
    return {"msg": "atualizado"}

def _serialize_card(c: CardDB, visto_versao):
    alteracoes_nao_vistas = max(0, (c.alteracoes or 0) - (visto_versao or 0))
    return {
        "id": c.id, "titulo": c.titulo, "descricao": c.descricao, "status": c.status,
        "prioridade": c.prioridade, "autor": c.autor, "prazo": c.prazo,
        "data_criacao": c.data_criacao, "checklist": c.checklist, "comentarios": c.comentarios,
        "responsaveis": c.responsaveis, "github_url": c.github_url, "ordem": c.ordem,
        "updated_em": c.updated_em,
        "alteracoes_nao_vistas": alteracoes_nao_vistas,
        "nao_visto": alteracoes_nao_vistas > 0,
    }

@app.get("/cards")
def get_cards(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    all_cards = db.query(CardDB).all()
    seen_map = {s.card_id: s.visto_versao for s in db.query(CardSeenDB).filter(CardSeenDB.user_id == current_user.id).all()}
    return [_serialize_card(c, seen_map.get(c.id)) for c in all_cards]

@app.post("/cards")
def create_card(card: CardSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    now = datetime.now()
    data_atual = now.strftime("%d/%m/%Y")
    now_iso = now.isoformat()
    max_ordem = db.query(CardDB).filter(CardDB.status == card.status).count()
    novo = CardDB(
        id=f"card-{uuid.uuid4().hex[:8]}",
        titulo=card.titulo,
        descricao=card.descricao,
        status=card.status,
        prioridade=card.prioridade,
        autor=card.autor,
        prazo=card.prazo,
        data_criacao=data_atual,
        checklist=card.checklist,
        comentarios=card.comentarios,
        responsaveis=card.responsaveis if card.responsaveis else [card.autor],
        github_url=card.github_url or None,
        ordem=max_ordem,
        updated_em=now_iso,
    )
    db.add(novo)
    # The creator has obviously "seen" the card they just made — everyone else has no
    # seen row yet, so it naturally shows up as a new/unseen card for them.
    db.add(CardSeenDB(card_id=novo.id, user_id=current_user.id, visto_em=now_iso, visto_versao=0))
    db.commit()
    db.refresh(novo)
    return novo

@app.put("/cards/reorder")
def reorder_cards(reorders: List[CardReorderItem], db: Session = Depends(get_db), current_user: UserDB = Depends(require_admin)):
    for r in reorders:
        card = db.query(CardDB).filter(CardDB.id == r.id).first()
        if card:
            card.ordem = r.ordem
    db.commit()
    return {"ok": True}

@app.put("/cards/{card_id}")
def update_card(card_id: str, card: CardSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if db_card:
        db_card.titulo = card.titulo
        db_card.descricao = card.descricao
        db_card.status = card.status
        db_card.prioridade = card.prioridade
        db_card.prazo = card.prazo
        db_card.checklist = card.checklist
        db_card.comentarios = card.comentarios
        db_card.responsaveis = card.responsaveis if card.responsaveis else [card.autor]
        db_card.github_url = card.github_url or None
        db_card.ordem = card.ordem
        now_iso = datetime.now().isoformat()
        db_card.updated_em = now_iso
        db_card.alteracoes = (db_card.alteracoes or 0) + 1
        # The editor made this change themselves — it shouldn't show up as "unseen" for them.
        seen_row = db.query(CardSeenDB).filter(CardSeenDB.card_id == card_id, CardSeenDB.user_id == current_user.id).first()
        if seen_row:
            seen_row.visto_em = now_iso
            seen_row.visto_versao = db_card.alteracoes
        else:
            db.add(CardSeenDB(card_id=card_id, user_id=current_user.id, visto_em=now_iso, visto_versao=db_card.alteracoes))
        db.commit()
    return {"msg": "atualizado"}

@app.delete("/cards/{card_id}")
def delete_card(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if db_card:
        db.delete(db_card)
        db.query(CardSeenDB).filter(CardSeenDB.card_id == card_id).delete()
        db.commit()
    return {"msg": "deletado"}

@app.post("/cards/{card_id}/seen")
def mark_card_seen(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    now_iso = datetime.now().isoformat()
    row = db.query(CardSeenDB).filter(CardSeenDB.card_id == card_id, CardSeenDB.user_id == current_user.id).first()
    if row:
        row.visto_em = now_iso
        row.visto_versao = db_card.alteracoes
    else:
        db.add(CardSeenDB(card_id=card_id, user_id=current_user.id, visto_em=now_iso, visto_versao=db_card.alteracoes))
    db.commit()
    return {"ok": True}

def compute_permission(item, current_user: UserDB, cards_by_id: dict):
    """Owner > explicit share > public-via-linked-card's responsáveis > no access."""
    if item.user_id == current_user.id:
        return 'owner'
    for share in (item.compartilhado_com or []):
        if share.get('user_id') == current_user.id:
            return share.get('nivel')
    if item.publico and item.card_id:
        card = cards_by_id.get(item.card_id)
        if card and current_user.nome in (card.responsaveis or []):
            return 'editar'
    return None

def _serialize_note(n: UserNoteDB, perm: str):
    return {
        "id": n.id, "user_id": n.user_id, "titulo": n.titulo, "conteudo": n.conteudo,
        "tipo": n.tipo, "canvas_data": n.canvas_data, "criado_em": n.criado_em,
        "card_id": n.card_id, "publico": n.publico, "compartilhado_com": n.compartilhado_com or [],
        "owner": perm == 'owner', "pode_editar": perm in ('owner', 'editar'),
    }

def _serialize_drawing(d: DrawingDB, perm: str):
    return {
        "id": d.id, "user_id": d.user_id, "titulo": d.titulo, "data": d.data, "criado_em": d.criado_em,
        "card_id": d.card_id, "publico": d.publico, "compartilhado_com": d.compartilhado_com or [],
        "owner": perm == 'owner', "pode_editar": perm in ('owner', 'editar'),
    }

def _check_share_fields_change(payload, db_item, perm: str):
    if perm == 'owner':
        return
    if perm != 'editar':
        raise HTTPException(status_code=403, detail="Você só tem permissão de visualização neste item")
    novo_compartilhado = [s.model_dump() for s in payload.compartilhado_com]
    if (payload.card_id != db_item.card_id or payload.publico != db_item.publico or
            novo_compartilhado != (db_item.compartilhado_com or [])):
        raise HTTPException(status_code=403, detail="Apenas o dono pode alterar compartilhamento, público ou tarefa vinculada")

@app.get("/notes")
def list_notes(card_id: Optional[str] = None, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    cards_by_id = {c.id: c for c in db.query(CardDB).all()}
    notes = db.query(UserNoteDB).order_by(UserNoteDB.criado_em.desc()).all()
    result = []
    for n in notes:
        perm = compute_permission(n, current_user, cards_by_id)
        if perm is None or (card_id and n.card_id != card_id):
            continue
        result.append(_serialize_note(n, perm))
    return result

@app.post("/notes")
def create_note(note: UserNoteSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    nova = UserNoteDB(
        id=f"note-{uuid.uuid4().hex[:8]}",
        user_id=current_user.id,
        titulo=note.titulo,
        conteudo=note.conteudo,
        tipo=note.tipo,
        canvas_data=note.canvas_data,
        criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
        card_id=note.card_id,
        publico=note.publico,
        compartilhado_com=[s.model_dump() for s in note.compartilhado_com],
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return _serialize_note(nova, 'owner')

@app.put("/notes/{note_id}")
def update_note(note_id: str, note: UserNoteSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_note = db.query(UserNoteDB).filter(UserNoteDB.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    cards_by_id = {c.id: c for c in db.query(CardDB).all()}
    perm = compute_permission(db_note, current_user, cards_by_id)
    if perm is None:
        raise HTTPException(status_code=403, detail="Sem acesso a esta nota")
    _check_share_fields_change(note, db_note, perm)
    db_note.titulo = note.titulo
    db_note.conteudo = note.conteudo
    db_note.tipo = note.tipo
    db_note.canvas_data = note.canvas_data
    if perm == 'owner':
        db_note.card_id = note.card_id
        db_note.publico = note.publico
        db_note.compartilhado_com = [s.model_dump() for s in note.compartilhado_com]
    db.commit()
    return {"ok": True}

@app.delete("/notes/{note_id}")
def delete_note(note_id: str, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_note = db.query(UserNoteDB).filter(UserNoteDB.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    if db_note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o dono pode deletar esta nota")
    db.delete(db_note)
    db.commit()
    return {"ok": True}

@app.get("/drawings")
def list_drawings(card_id: Optional[str] = None, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    cards_by_id = {c.id: c for c in db.query(CardDB).all()}
    drawings = db.query(DrawingDB).order_by(DrawingDB.criado_em.desc()).all()
    result = []
    for d in drawings:
        perm = compute_permission(d, current_user, cards_by_id)
        if perm is None or (card_id and d.card_id != card_id):
            continue
        result.append(_serialize_drawing(d, perm))
    return result

@app.post("/drawings")
def create_drawing(drawing: DrawingSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    novo = DrawingDB(
        id=f"drawing-{uuid.uuid4().hex[:8]}",
        user_id=current_user.id,
        titulo=drawing.titulo,
        data=drawing.data,
        criado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
        card_id=drawing.card_id,
        publico=drawing.publico,
        compartilhado_com=[s.model_dump() for s in drawing.compartilhado_com],
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return _serialize_drawing(novo, 'owner')

@app.put("/drawings/{drawing_id}")
def update_drawing(drawing_id: str, drawing: DrawingSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_drawing = db.query(DrawingDB).filter(DrawingDB.id == drawing_id).first()
    if not db_drawing:
        raise HTTPException(status_code=404, detail="Desenho não encontrado")
    cards_by_id = {c.id: c for c in db.query(CardDB).all()}
    perm = compute_permission(db_drawing, current_user, cards_by_id)
    if perm is None:
        raise HTTPException(status_code=403, detail="Sem acesso a este desenho")
    _check_share_fields_change(drawing, db_drawing, perm)
    db_drawing.titulo = drawing.titulo
    db_drawing.data = drawing.data
    if perm == 'owner':
        db_drawing.card_id = drawing.card_id
        db_drawing.publico = drawing.publico
        db_drawing.compartilhado_com = [s.model_dump() for s in drawing.compartilhado_com]
    db.commit()
    return {"ok": True}

@app.delete("/drawings/{drawing_id}")
def delete_drawing(drawing_id: str, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_drawing = db.query(DrawingDB).filter(DrawingDB.id == drawing_id).first()
    if not db_drawing:
        raise HTTPException(status_code=404, detail="Desenho não encontrado")
    if db_drawing.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o dono pode deletar este desenho")
    db.delete(db_drawing)
    db.commit()
    return {"ok": True}

