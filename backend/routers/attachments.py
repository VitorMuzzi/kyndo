import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from audit import _mk_log
from database import get_db
from models import AttachmentDB, CardDB, UserDB
from rbac import get_user_permissions, get_visible_column_ids
from security import get_current_user

router = APIRouter()

# Overridable via env so tests can redirect uploads to an isolated temp dir —
# mirrors how conftest.py isolates DATABASE_URL.
UPLOAD_DIR = os.getenv("UPLOAD_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"
)
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — plenty for prints/PDFs, small enough to not silently fill the disk


def _assert_card_visible(db, current_user, db_card):
    """Mirrors the same guard in routers/cards.py — a card whose column is
    outside the caller's visible set doesn't exist for them."""
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None and db_card.status not in visible:
        raise HTTPException(status_code=404, detail="Card não encontrado")


def _serialize(a: AttachmentDB):
    return {
        "id": a.id, "card_id": a.card_id, "nome_original": a.nome_original,
        "content_type": a.content_type, "tamanho": a.tamanho,
        "enviado_por": a.enviado_por, "enviado_em": a.enviado_em,
    }


@router.get("/cards/{card_id}/attachments")
def list_attachments(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)
    rows = db.query(AttachmentDB).filter(AttachmentDB.card_id == card_id).order_by(AttachmentDB.enviado_em.asc()).all()
    return [_serialize(a) for a in rows]


@router.post("/cards/{card_id}/attachments")
async def upload_attachment(card_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # The name on disk is never the client-supplied filename — sidesteps path
    # traversal and collisions entirely. Only the extension is kept (capped,
    # in case of something absurd like a 300-char "extension").
    ext = os.path.splitext(file.filename or "")[1][:10]
    nome_arquivo = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, nome_arquivo)

    size = 0
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"Arquivo maior que {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
                out.write(chunk)
    except HTTPException:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise

    now_iso = datetime.now().isoformat()
    nova = AttachmentDB(
        id=f"anexo-{uuid.uuid4().hex[:10]}", card_id=card_id,
        nome_original=file.filename or nome_arquivo, nome_arquivo=nome_arquivo,
        content_type=file.content_type, tamanho=size,
        enviado_por=current_user.nome, enviado_em=now_iso,
    )
    db.add(nova)
    _mk_log(db, card_id, db_card.titulo, current_user.nome, "anexo_adicionado", detalhe=nova.nome_original)
    db.commit()
    db.refresh(nova)
    return _serialize(nova)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    a = db.query(AttachmentDB).filter(AttachmentDB.id == attachment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    db_card = db.query(CardDB).filter(CardDB.id == a.card_id).first()
    if db_card:
        _assert_card_visible(db, current_user, db_card)
    path = os.path.join(UPLOAD_DIR, a.nome_arquivo)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no servidor")
    return FileResponse(path, media_type=a.content_type or "application/octet-stream", filename=a.nome_original)


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    a = db.query(AttachmentDB).filter(AttachmentDB.id == attachment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    db_card = db.query(CardDB).filter(CardDB.id == a.card_id).first()
    if db_card:
        _assert_card_visible(db, current_user, db_card)
    perms = get_user_permissions(db, current_user.id)
    if a.enviado_por != current_user.nome and "editar_card" not in perms:
        raise HTTPException(status_code=403, detail="Sem permissão para excluir este anexo")

    path = os.path.join(UPLOAD_DIR, a.nome_arquivo)
    if os.path.isfile(path):
        os.remove(path)
    if db_card:
        _mk_log(db, a.card_id, db_card.titulo, current_user.nome, "anexo_removido", detalhe=a.nome_original)
    db.delete(a)
    db.commit()
    return {"ok": True}
