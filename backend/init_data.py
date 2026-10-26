import os
import uuid

from database import SessionLocal
from models import ColumnDB, UserDB
from security import definir_senha, get_password_hash, verify_password

SENHA_PADRAO_ADMIN = "admin"


def init_db():
    db = SessionLocal()
    # SUPERADMIN_PASSWORD no .env é a senha do admin. Sem ela, o admin nasce
    # com "admin" marcada como temporária, então a tela obriga a troca no
    # primeiro login.
    senha_env = os.getenv("SUPERADMIN_PASSWORD") or ""
    admin = db.query(UserDB).filter(UserDB.nome == "admin").first()
    if not admin:
        db.add(UserDB(
            id=str(uuid.uuid4()), nome="admin", senha=get_password_hash(senha_env or SENHA_PADRAO_ADMIN),
            role="superadmin", senha_temporaria=not senha_env,
        ))
    else:
        if admin.role == "admin":
            admin.role = "superadmin"
        # Banco que já existia com admin/admin: o servidor escuta na rede
        # inteira, então essa senha não pode continuar valendo.
        if senha_env != SENHA_PADRAO_ADMIN and verify_password(SENHA_PADRAO_ADMIN, admin.senha):
            if senha_env:
                definir_senha(admin, senha_env)
                admin.senha_temporaria = False
            else:
                admin.senha_temporaria = True

    if db.query(ColumnDB).count() == 0:
        cols = [
            ColumnDB(id="col-1", titulo="IDEIAS DE PROJETOS", cor="#fef08a", ordem=0, publica=True),
            ColumnDB(id="col-2", titulo="PROJETOS A SEREM INICIADOS", cor="#bfdbfe", ordem=1),
            ColumnDB(id="col-3", titulo="EM ANDAMENTO", cor="#fecaca", ordem=2, auto_andamento=True),
            ColumnDB(id="col-4", titulo="CONCLUÍDO", cor="#bbf7d0", ordem=3, auto_concluido=True),
        ]
        db.add_all(cols)
    db.commit()
    db.close()
