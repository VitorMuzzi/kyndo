import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import UserDB

# Security config — set SECRET_KEY env var in production
SECRET_KEY = os.getenv("SECRET_KEY", "coloque_sua_chave_secreta_aqui")
ALGORITHM = "HS256"

security = HTTPBearer()

# In-memory rate limiter for /login
_login_attempts: dict = defaultdict(list)
_RATE_WINDOW = 60  # seconds
_RATE_MAX = 10  # attempts per window


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


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {"sub": user_id, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


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
