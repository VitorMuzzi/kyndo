import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import CardDB, UserDB, UserNoteDB
from permissions import check_share_fields_change, compute_permission
from schemas import UserNoteSchema
from security import get_current_user

router = APIRouter()


def _serialize_note(n: UserNoteDB, perm: str):
    return {
        "id": n.id, "user_id": n.user_id, "titulo": n.titulo, "conteudo": n.conteudo,
        "tipo": n.tipo, "canvas_data": n.canvas_data, "criado_em": n.criado_em,
        "card_id": n.card_id, "publico": n.publico, "compartilhado_com": n.compartilhado_com or [],
        "owner": perm == 'owner', "pode_editar": perm in ('owner', 'editar'),
    }


@router.get("/notes")
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


@router.post("/notes")
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


@router.put("/notes/{note_id}")
def update_note(note_id: str, note: UserNoteSchema, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_note = db.query(UserNoteDB).filter(UserNoteDB.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    cards_by_id = {c.id: c for c in db.query(CardDB).all()}
    perm = compute_permission(db_note, current_user, cards_by_id)
    if perm is None:
        raise HTTPException(status_code=403, detail="Sem acesso a esta nota")
    check_share_fields_change(note, db_note, perm)
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


@router.delete("/notes/{note_id}")
def delete_note(note_id: str, current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db_note = db.query(UserNoteDB).filter(UserNoteDB.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    if db_note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o dono pode deletar esta nota")
    db.delete(db_note)
    db.commit()
    return {"ok": True}
