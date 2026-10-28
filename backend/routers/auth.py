from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import UserDB
from rbac import get_user_permissions
from schemas import LoginRequest
from security import check_rate_limit, create_access_token, get_current_user, verify_password

router = APIRouter()


@router.post("/login")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    user = db.query(UserDB).filter(UserDB.nome == req.nome).first()
    if not user or not verify_password(req.senha, user.senha):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    return {
        "id": user.id,
        "nome": user.nome,
        "role": user.role,
        "permissions": sorted(get_user_permissions(db, user.id)),
        "senha_temporaria": user.senha_temporaria,
        "token": create_access_token(user),
    }


@router.get("/me/permissions")
def minhas_permissoes(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """O login entrega as permissões uma vez; a tela consulta isto na
    sincronização pra que um cargo dado ou tirado valha sem sair e entrar."""
    return {"permissions": sorted(get_user_permissions(db, current_user.id))}
