from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from audit import _mk_log
from database import get_db
from models import ColumnDB, UserDB
from rbac import get_visible_column_ids, require_permission
from schemas import ColSchema
from security import get_current_user

router = APIRouter()

# `ordem` fica de fora: arrastar colunas é arrumação de tela, não alteração —
# senão cada arrasto encheria a auditoria com uma linha por coluna.
CAMPOS_COLUNA = ("titulo", "cor", "publica", "auto_andamento", "auto_concluido", "arquivado")


def coluna_de(c: ColumnDB):
    return {k: getattr(c, k) for k in CAMPOS_COLUNA}


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
    _mk_log(db, None, nova.titulo, current_user.nome, "coluna_criada", alvo_tipo="coluna", alvo_id=nova.id,
            reversao={"col_id": nova.id, "depois": coluna_de(nova)})
    db.commit()
    return nova


@router.put("/columns/{col_id}")
def update_column(col_id: str, col: ColSchema, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_colunas"))):
    db_col = db.query(ColumnDB).filter(ColumnDB.id == col_id).first()
    if db_col:
        # O id vem no corpo só porque o ColSchema é compartilhado com o POST.
        # Deixar ele passar aqui trocaria a chave primária da coluna e órfãria
        # todo card cujo `status` aponta pra ela — não há FK que segure isso.
        antes = coluna_de(db_col)
        for key, value in col.model_dump(exclude={"id"}).items():
            setattr(db_col, key, value)
        depois = coluna_de(db_col)
        if depois != antes:
            acao = "coluna_arquivada" if depois["arquivado"] and not antes["arquivado"] else "coluna_alterada"
            _mk_log(db, None, db_col.titulo, current_user.nome, acao, alvo_tipo="coluna", alvo_id=db_col.id,
                    reversao={"col_id": db_col.id, "antes": antes, "depois": depois})
        db.commit()
    return {"msg": "atualizado"}
