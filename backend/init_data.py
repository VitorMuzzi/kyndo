import uuid

from database import SessionLocal
from models import ColumnDB, UserDB
from security import get_password_hash


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
            ColumnDB(id="col-4", titulo="CONCLUÍDO", cor="#bbf7d0", ordem=3, auto_concluido=True),
        ]
        db.add_all(cols)
    db.commit()
    db.close()
