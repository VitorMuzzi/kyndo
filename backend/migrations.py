import uuid
from datetime import datetime

from sqlalchemy import text

from database import Base, engine, SessionLocal
from models import CardDB, ItemSeenDB, RoleDB, UserDB, UserRoleDB
from rbac import PERMISSIONS


def _migrate_drawings_table():
    """The old 'drawings' table was a singleton (user_id as PK, no id/titulo).
    create_all() never touches an existing table, so rename it out of the way
    first; the new schema gets created fresh below, then legacy rows get
    copied in by _copy_legacy_drawings(). Idempotent: no-ops once already migrated."""
    with engine.connect() as conn:
        exists = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drawings'"
        )).fetchone()
        if not exists:
            return
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(drawings)"))]
        if 'id' in cols:
            return
        conn.execute(text("ALTER TABLE drawings RENAME TO drawings_old_singleton"))
        # SQLite keeps index names attached across a table rename; drop it so
        # create_all() below can create a same-named index on the new table.
        conn.execute(text("DROP INDEX IF EXISTS ix_drawings_user_id"))
        conn.commit()


def _copy_legacy_drawings():
    with engine.connect() as conn:
        old = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='drawings_old_singleton'"
        )).fetchone()
        if not old:
            return
        rows = conn.execute(text("SELECT user_id, data FROM drawings_old_singleton")).fetchall()
        for user_id, data in rows:
            if not data:
                continue
            dup = conn.execute(
                text("SELECT 1 FROM drawings WHERE user_id=:uid LIMIT 1"), {"uid": user_id}
            ).fetchone()
            if dup:
                continue
            conn.execute(text(
                "INSERT INTO drawings (id, user_id, titulo, data, criado_em, card_id, publico, compartilhado_com) "
                "VALUES (:id, :uid, :titulo, :data, :criado_em, NULL, 0, '[]')"
            ), {
                "id": f"drawing-{uuid.uuid4().hex[:8]}",
                "uid": user_id,
                "titulo": "Meu Desenho",
                "data": data,
                "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            })
        conn.commit()


def _run_schema_migrations():
    for stmt in [
        "ALTER TABLE cards ADD COLUMN responsaveis TEXT",
        "ALTER TABLE cards ADD COLUMN github_url VARCHAR",
        "ALTER TABLE cards ADD COLUMN ordem INTEGER DEFAULT 0",
        "ALTER TABLE cards ADD COLUMN updated_em VARCHAR",
        "ALTER TABLE cards ADD COLUMN alteracoes INTEGER DEFAULT 0",
        "ALTER TABLE card_seen ADD COLUMN visto_versao INTEGER DEFAULT 0",
        "ALTER TABLE user_notes ADD COLUMN card_id VARCHAR",
        "ALTER TABLE user_notes ADD COLUMN publico BOOLEAN DEFAULT 0",
        "ALTER TABLE user_notes ADD COLUMN compartilhado_com TEXT DEFAULT '[]'",
        "ALTER TABLE roles ADD COLUMN colunas_visiveis TEXT",
    ]:
        with engine.connect() as conn:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass


def _backfill_card_notifications():
    """Cards created before the notification feature shipped have no
    updated_em/card_seen rows. Backfill both with the SAME timestamp so
    nobody gets a flood of false 'changed' badges on pre-existing cards —
    only edits made after this point should ever trigger a badge."""
    now_iso = datetime.now().isoformat()
    with engine.connect() as conn:
        conn.execute(text("UPDATE cards SET updated_em = :now WHERE updated_em IS NULL OR updated_em = ''"), {"now": now_iso})
        card_ids = [r[0] for r in conn.execute(text("SELECT id FROM cards"))]
        user_ids = [r[0] for r in conn.execute(text("SELECT id FROM users"))]
        for cid in card_ids:
            for uid in user_ids:
                exists = conn.execute(
                    text("SELECT 1 FROM card_seen WHERE card_id=:cid AND user_id=:uid"), {"cid": cid, "uid": uid}
                ).fetchone()
                if exists:
                    continue
                conn.execute(text(
                    "INSERT INTO card_seen (card_id, user_id, visto_em) VALUES (:cid, :uid, :now)"
                ), {"cid": cid, "uid": uid, "now": now_iso})
        conn.commit()


def _backfill_item_notifications():
    """Etapas (checklist items) criadas antes da badge por etapa não têm
    notas_versao. Para qualquer etapa que já tinha uma observação, ancora
    notas_versao=1 e marca como "vista" por todos os usuários já existentes —
    senão todo mundo veria uma badge falsa de observação nova em notas antigas."""
    db = SessionLocal()
    try:
        user_ids = [u.id for u in db.query(UserDB).all()]
        for card in db.query(CardDB).all():
            checklist = card.checklist or []
            changed = False
            new_checklist = []
            for item in checklist:
                item = dict(item)
                if "notas_versao" not in item:
                    item["notas_versao"] = 1 if (item.get("notas") or "").strip() else 0
                    changed = True
                new_checklist.append(item)
            if not changed:
                continue
            card.checklist = new_checklist
            for item in new_checklist:
                if not item.get("notas_versao"):
                    continue
                for uid in user_ids:
                    exists = db.query(ItemSeenDB).filter(
                        ItemSeenDB.card_id == card.id, ItemSeenDB.item_id == item["id"], ItemSeenDB.user_id == uid
                    ).first()
                    if not exists:
                        db.add(ItemSeenDB(card_id=card.id, item_id=item["id"], user_id=uid, visto_versao=item["notas_versao"]))
        db.commit()
    finally:
        db.close()


ADMIN_ROLE_PERMS = {
    "gerenciar_usuarios", "gerenciar_colunas", "reordenar_cards", "criar_card_coluna_privada",
    "editar_card", "excluir_card", "editar_prioridade", "editar_prazo",
    "gerenciar_etapas", "concluir_etapas", "decidir_sugestoes", "trocar_senha_outros",
}


def _seed_default_roles():
    """Seeds the 3 baseline cargos (idempotent). Doesn't touch users — the seed
    admin user doesn't exist yet at this point (init_data.py runs after
    run_migrations() in main.py), so assigning cargos to existing users has to
    happen separately, in assign_default_user_roles() below."""
    db = SessionLocal()
    try:
        if not db.query(RoleDB).filter(RoleDB.nome == "Superadmin").first():
            db.add(RoleDB(
                id="role-superadmin", nome="Superadmin", cor="#f97316", protegido=True,
                permissoes={k: True for k in PERMISSIONS}, ordem=0,
            ))
        if not db.query(RoleDB).filter(RoleDB.nome == "Admin").first():
            db.add(RoleDB(
                id="role-admin", nome="Admin", cor="#ea580c", protegido=False,
                permissoes={k: (k in ADMIN_ROLE_PERMS) for k in PERMISSIONS}, ordem=1,
            ))
        if not db.query(RoleDB).filter(RoleDB.nome == "Usuário").first():
            db.add(RoleDB(
                id="role-usuario", nome="Usuário", cor="#94a3b8", protegido=False,
                permissoes={k: False for k in PERMISSIONS}, ordem=2,
            ))
        db.commit()
    finally:
        db.close()


def assign_default_user_roles():
    """Assigns each existing user the cargo matching their legacy `role` value,
    once (idempotent) — must run AFTER init_data.py's init_db() has created the
    seed admin user, so it's called separately from main.py, not from
    run_migrations()."""
    db = SessionLocal()
    try:
        role_by_legacy = {
            "superadmin": db.query(RoleDB).filter(RoleDB.nome == "Superadmin").first(),
            "admin": db.query(RoleDB).filter(RoleDB.nome == "Admin").first(),
            "user": db.query(RoleDB).filter(RoleDB.nome == "Usuário").first(),
        }
        usuario = role_by_legacy["user"]
        for user in db.query(UserDB).all():
            if db.query(UserRoleDB).filter(UserRoleDB.user_id == user.id).first():
                continue
            target = role_by_legacy.get(user.role) or usuario
            if target:
                db.add(UserRoleDB(user_id=user.id, role_id=target.id))
        db.commit()
    finally:
        db.close()


def run_migrations():
    _migrate_drawings_table()
    Base.metadata.create_all(bind=engine)
    _copy_legacy_drawings()
    _run_schema_migrations()
    _backfill_card_notifications()
    _backfill_item_notifications()
    _seed_default_roles()
