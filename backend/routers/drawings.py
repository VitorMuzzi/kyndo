import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import CardDB, DrawingDB, UserDB
from permissions import check_share_fields_change, compute_permission
from schemas import DrawingSchema
from security import get_current_user

router = APIRouter()


def _serialize_drawing(d: DrawingDB, perm: str):
    return {
        "id": d.id, "user_id": d.user_id, "titulo": d.titulo, "data": d.data, "criado_em": d.criado_em,
        "card_id": d.card_id, "publico": d.publico, "compartilhado_com": d.compartilhado_com or [],
        "owner": perm == 'owner', "pode_editar": perm in ('owner', 'editar'),
    }


@router.get("/drawings")
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


@router.post("/drawings")
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


@router.put("/drawings/{drawing_id}")
def update_drawing(drawing_id: str, drawing: DrawingSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_drawing = db.query(DrawingDB).filter(DrawingDB.id == drawing_id).first()
    if not db_drawing:
        raise HTTPException(status_code=404, detail="Desenho não encontrado")
    cards_by_id = {c.id: c for c in db.query(CardDB).all()}
    perm = compute_permission(db_drawing, current_user, cards_by_id)
    if perm is None:
        raise HTTPException(status_code=403, detail="Sem acesso a este desenho")
    check_share_fields_change(drawing, db_drawing, perm)
    db_drawing.titulo = drawing.titulo
    db_drawing.data = drawing.data
    if perm == 'owner':
        db_drawing.card_id = drawing.card_id
        db_drawing.publico = drawing.publico
        db_drawing.compartilhado_com = [s.model_dump() for s in drawing.compartilhado_com]
    db.commit()
    return {"ok": True}


@router.delete("/drawings/{drawing_id}")
def delete_drawing(drawing_id: str, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_drawing = db.query(DrawingDB).filter(DrawingDB.id == drawing_id).first()
    if not db_drawing:
        raise HTTPException(status_code=404, detail="Desenho não encontrado")
    if db_drawing.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o dono pode deletar este desenho")
    db.delete(db_drawing)
    db.commit()
    return {"ok": True}
