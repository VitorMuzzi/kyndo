import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from audit import _mk_log
from database import get_db
from lixeira import excluir_cargo
from models import RoleDB, UserDB, UserRoleDB
from rbac import PERMISSIONS, get_user_permissions, get_visible_column_ids, is_superadmin, require_permission
from schemas import RoleCreate, RoleUpdate, UserRolesUpdate
from security import get_current_user

router = APIRouter()


CAMPOS_CARGO = ("nome", "cor", "permissoes", "colunas_visiveis")


def cargo_de(r: RoleDB):
    return {c: getattr(r, c) for c in CAMPOS_CARGO}


# ------------------------------------------------------------------
# Quem gerencia cargos não pode usar isso pra subir o próprio acesso:
#  1. não mexe em cargo que tem, nem nos próprios cargos;
#  2. só concede (ou retira) permissão e coluna que ele mesmo tem.
# Assim o máximo que alguém consegue é repassar o que já tem. O Superadmin
# fica de fora das duas regras — ele já tem tudo. Usadas também ao desfazer
# pela auditoria (reversao.py), pra que desfazer não vire atalho.

def _ligadas(permissoes):
    return {k for k, v in (permissoes or {}).items() if v}


def _negar(detalhe):
    raise HTTPException(status_code=403, detail=detalhe)


def checar_cargo_proprio(db, actor, role_id):
    if is_superadmin(db, actor):
        return
    if db.query(UserRoleDB).filter(UserRoleDB.user_id == actor.id, UserRoleDB.role_id == role_id).first():
        _negar("Você não pode alterar um cargo que você mesmo tem — peça a outra pessoa.")


def checar_concessao(db, actor, novas, antigas=None):
    """Toda permissão que muda de estado (ligada ou desligada) tem que ser
    uma que o actor tem."""
    if is_superadmin(db, actor):
        return
    fora = sorted((_ligadas(novas) ^ _ligadas(antigas)) - get_user_permissions(db, actor.id))
    if fora:
        nomes = ", ".join(f'"{PERMISSIONS.get(k, k)}"' for k in fora)
        _negar(f"Você não pode conceder nem retirar permissões que você não tem: {nomes}.")


def checar_colunas(db, actor, colunas_visiveis):
    """Quem só enxerga algumas colunas não cria cargo que enxergue mais que ele."""
    if is_superadmin(db, actor):
        return
    minhas = get_visible_column_ids(db, actor.id)
    if minhas is None:
        return
    if colunas_visiveis is None or set(colunas_visiveis) - minhas:
        _negar("Você não pode dar acesso a colunas que você mesmo não vê.")


def checar_atribuicao(db, actor, user_id, novos_ids):
    if is_superadmin(db, actor):
        return
    if user_id == actor.id:
        _negar("Você não pode alterar os próprios cargos — peça a outra pessoa.")
    atuais = {v.role_id for v in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all()}
    for role in db.query(RoleDB).filter(RoleDB.id.in_(atuais ^ set(novos_ids))).all():
        try:
            checar_concessao(db, actor, role.permissoes)
            checar_colunas(db, actor, role.colunas_visiveis)
        except HTTPException:
            _negar(f'O cargo "{role.nome}" tem permissões ou colunas que você não tem — '
                   "você não pode dar nem tirar esse cargo de ninguém.")


def validar_troca_de_cargos(db, actor, user_id, novos_ids):
    """Regras do Superadmin: só quem já é concede ou revoga, e o último nunca
    sai. Usada aqui e ao desfazer uma troca de cargos pela auditoria."""
    superadmin_role = db.query(RoleDB).filter(RoleDB.protegido == True).first()  # noqa: E712
    if not superadmin_role:
        return
    current_role_ids = {r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all()}
    had_super = superadmin_role.id in current_role_ids
    will_have_super = superadmin_role.id in novos_ids

    if had_super != will_have_super:
        actor_role_ids = {r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == actor.id).all()}
        if superadmin_role.id not in actor_role_ids:
            raise HTTPException(status_code=400, detail="Só quem já é Superadmin pode conceder ou revogar esse cargo")

    if had_super and not will_have_super:
        holders = db.query(UserRoleDB).filter(UserRoleDB.role_id == superadmin_role.id).count()
        if holders <= 1:
            raise HTTPException(status_code=400, detail="Não é possível remover o único Superadmin do sistema")


def _serialize_role(r: RoleDB):
    return {
        "id": r.id, "nome": r.nome, "cor": r.cor, "protegido": r.protegido,
        "permissoes": r.permissoes or {}, "ordem": r.ordem,
        "colunas_visiveis": r.colunas_visiveis,
    }


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    return [_serialize_role(r) for r in db.query(RoleDB).order_by(RoleDB.ordem).all()]


@router.get("/permissions")
def list_permissions(current_user: UserDB = Depends(get_current_user)):
    return [{"key": k, "label": v} for k, v in PERMISSIONS.items()]


@router.post("/roles")
def create_role(body: RoleCreate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    checar_concessao(db, current_user, body.permissoes)
    checar_colunas(db, current_user, body.colunas_visiveis if body.colunas_restritas else None)
    novo = RoleDB(
        id=f"role-{uuid.uuid4().hex[:8]}", nome=body.nome, cor=body.cor,
        permissoes=body.permissoes, protegido=False, ordem=db.query(RoleDB).count(),
        colunas_visiveis=(body.colunas_visiveis if body.colunas_restritas else None),
    )
    db.add(novo)
    _mk_log(db, None, novo.nome, current_user.nome, "cargo_criado", alvo_tipo="cargo", alvo_id=novo.id,
            reversao={"role_id": novo.id})
    db.commit()
    db.refresh(novo)
    return _serialize_role(novo)


@router.put("/roles/{role_id}")
def update_role(role_id: str, body: RoleUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    role = db.query(RoleDB).filter(RoleDB.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    if role.protegido:
        raise HTTPException(status_code=400, detail="Este cargo é protegido e não pode ser editado")
    checar_cargo_proprio(db, current_user, role.id)
    if body.permissoes is not None:
        checar_concessao(db, current_user, body.permissoes, role.permissoes)
    if body.colunas_restritas is not None:
        checar_colunas(db, current_user, (body.colunas_visiveis or []) if body.colunas_restritas else None)
    antes = cargo_de(role)
    if body.nome is not None:
        role.nome = body.nome
    if body.cor is not None:
        role.cor = body.cor
    if body.permissoes is not None:
        role.permissoes = body.permissoes
    if body.colunas_restritas is True:
        role.colunas_visiveis = body.colunas_visiveis or []
    elif body.colunas_restritas is False:
        role.colunas_visiveis = None
    depois = cargo_de(role)
    if depois != antes:
        _mk_log(db, None, role.nome, current_user.nome, "cargo_alterado", alvo_tipo="cargo", alvo_id=role.id,
                reversao={"role_id": role.id, "antes": antes, "depois": depois})
    db.commit()
    return _serialize_role(role)


@router.delete("/roles/{role_id}")
def delete_role(role_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    role = db.query(RoleDB).filter(RoleDB.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    if role.protegido:
        raise HTTPException(status_code=400, detail="Este cargo é protegido e não pode ser excluído")
    checar_cargo_proprio(db, current_user, role.id)
    # Excluir tira as permissões de quem tem o cargo — vale a mesma regra de concessão.
    checar_concessao(db, current_user, {}, role.permissoes)
    lixeira_id = excluir_cargo(db, role, current_user.nome)
    _mk_log(db, None, role.nome, current_user.nome, "cargo_excluido", alvo_tipo="cargo", alvo_id=role.id,
            lixeira_id=lixeira_id, reversao={"lixeira_id": lixeira_id})
    db.commit()
    return {"ok": True}


@router.put("/users/{user_id}/roles")
def set_user_roles(user_id: str, body: UserRolesUpdate, db: Session = Depends(get_db), current_user: UserDB = Depends(require_permission("gerenciar_cargos"))):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    new_role_ids = set(body.role_ids)
    checar_atribuicao(db, current_user, user_id, new_role_ids)
    validar_troca_de_cargos(db, current_user, user_id, new_role_ids)

    antes = sorted(r.role_id for r in db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).all())
    db.query(UserRoleDB).filter(UserRoleDB.user_id == user_id).delete()
    for role_id in new_role_ids:
        db.add(UserRoleDB(user_id=user_id, role_id=role_id))
    if sorted(new_role_ids) != antes:
        nomes = {r.id: r.nome for r in db.query(RoleDB).all()}
        _mk_log(db, None, user.nome, current_user.nome, "cargos_do_usuario_alterados", alvo_tipo="usuario", alvo_id=user.id,
                valor_antigo=", ".join(nomes.get(i, i) for i in antes) or None,
                valor_novo=", ".join(nomes.get(i, i) for i in sorted(new_role_ids)) or None,
                reversao={"user_id": user.id, "antes": antes, "depois": sorted(new_role_ids)})
    db.commit()
    return {"ok": True}
