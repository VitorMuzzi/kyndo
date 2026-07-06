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

class DrawingDB(Base):
    __tablename__ = "drawings"
    user_id = Column(String, primary_key=True, index=True)
    data    = Column(String, default="")

Base.metadata.create_all(bind=engine)

# Migrations
for stmt in [
    "ALTER TABLE cards ADD COLUMN responsaveis TEXT",
    "ALTER TABLE cards ADD COLUMN github_url VARCHAR",
    "ALTER TABLE cards ADD COLUMN ordem INTEGER DEFAULT 0",
]:
    with engine.connect() as conn:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except Exception:
            pass

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

class UserNoteSchema(BaseModel):
    titulo: str = "Nova Nota"
    conteudo: str = ""
    tipo: str = "texto"
    canvas_data: Optional[Dict[str, Any]] = None

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

@app.get("/cards")
def get_cards(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return db.query(CardDB).all()

@app.post("/cards")
def create_card(card: CardSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    data_atual = datetime.now().strftime("%d/%m/%Y")
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
    )
    db.add(novo)
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
        db.commit()
    return {"msg": "atualizado"}

@app.delete("/cards/{card_id}")
def delete_card(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if db_card:
        db.delete(db_card)
        db.commit()
    return {"msg": "deletado"}

@app.get("/notes")
def list_notes(current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(UserNoteDB).filter(UserNoteDB.user_id == current_user.id).order_by(UserNoteDB.criado_em.desc()).all()

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
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova

@app.put("/notes/{note_id}")
def update_note(note_id: str, note: UserNoteSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_note = db.query(UserNoteDB).filter(UserNoteDB.id == note_id, UserNoteDB.user_id == current_user.id).first()
    if db_note:
        db_note.titulo = note.titulo
        db_note.conteudo = note.conteudo
        db_note.tipo = note.tipo
        db_note.canvas_data = note.canvas_data
        db.commit()
    return {"ok": True}

@app.delete("/notes/{note_id}")
def delete_note(note_id: str, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_note = db.query(UserNoteDB).filter(UserNoteDB.id == note_id, UserNoteDB.user_id == current_user.id).first()
    if db_note:
        db.delete(db_note)
        db.commit()
    return {"ok": True}

class DrawingSchema(BaseModel):
    data: str = ""

@app.get("/drawing/me")
def get_drawing(current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(DrawingDB).filter(DrawingDB.user_id == current_user.id).first()
    return {"data": d.data if d else ""}

@app.put("/drawing/me")
def save_drawing(body: DrawingSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(DrawingDB).filter(DrawingDB.user_id == current_user.id).first()
    if d:
        d.data = body.data
    else:
        db.add(DrawingDB(user_id=current_user.id, data=body.data))
    db.commit()
    return {"ok": True}

