from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import ColumnDB, UserDB
from rbac import get_visible_column_ids, require_permission
from schemas import ColSchema
from security import get_current_user

router = APIRouter()


@router.get("/columns")
def get_columns(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    q = db.query(ColumnDB).filter(ColumnDB.arquivado == False)
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None:
        q = q.filter(ColumnDB.id.in_(visible))
    return q.order_by(ColumnDB.ordem).all()


@router.post("/columns")
def create_column(col: ColSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_colunas"))):
    nova = ColumnDB(**col.model_dump())
    db.add(nova)
    db.commit()
    return nova


@router.put("/columns/{col_id}")
def update_column(col_id: str, col: ColSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_colunas"))):
    db_col = db.query(ColumnDB).filter(ColumnDB.id == col_id).first()
    if db_col:
        for key, value in col.model_dump().items():
            setattr(db_col, key, value)
        db.commit()
    return {"msg": "atualizado"}
