import os
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import CardDB, UserDB
from rbac import get_visible_column_ids
from security import get_current_user

router = APIRouter()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
PR_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$")

# No CI/checks status here on purpose — the Checks API (what GitHub Actions
# reports to) is only readable by GitHub Apps, never by a personal access
# token (fine-grained or classic). The older Commit Statuses API a PAT *can*
# read doesn't reflect Actions results, so it would just show nothing for
# most repos — worse than not having the field at all.


def _assert_card_visible(db, current_user, db_card):
    visible = get_visible_column_ids(db, current_user.id)
    if visible is not None and db_card.status not in visible:
        raise HTTPException(status_code=404, detail="Card não encontrado")


def _headers():
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


@router.get("/cards/{card_id}/github")
def get_github_info(card_id: str, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    db_card = db.query(CardDB).filter(CardDB.id == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card não encontrado")
    _assert_card_visible(db, current_user, db_card)

    match = PR_URL_RE.match((db_card.github_url or "").strip())
    if not match:
        return {"linked": False}
    if not GITHUB_TOKEN:
        return {"linked": True, "configurado": False}

    owner, repo, numero = match.group(1), match.group(2), int(match.group(3))
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            r = client.get(f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{numero}", headers=_headers())
            if r.status_code == 404:
                return {"linked": True, "configurado": True, "erro": "Pull request não encontrada (verifique o link ou as permissões do token)"}
            if r.status_code != 200:
                return {"linked": True, "configurado": True, "erro": f"GitHub retornou {r.status_code}"}
            pr = r.json()

            estado = "mergeada" if pr.get("merged") else ("fechada" if pr.get("state") == "closed" else "aberta")

            r_commits = client.get(f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{numero}/commits", headers=_headers(), params={"per_page": 100})
            commits_raw = r_commits.json() if r_commits.status_code == 200 else []
            commits = [
                {
                    "sha": c["sha"][:7],
                    "titulo": (c.get("commit", {}).get("message") or "").split("\n")[0],
                    "autor": (c.get("author") or {}).get("login") or c.get("commit", {}).get("author", {}).get("name") or "?",
                    "data": c.get("commit", {}).get("author", {}).get("date"),
                    "url": c.get("html_url"),
                }
                for c in reversed(commits_raw)  # most recent first
            ]

            return {
                "linked": True, "configurado": True,
                "owner": owner, "repo": repo, "numero": numero,
                "titulo": pr.get("title"), "estado": estado,
                "url": pr.get("html_url"),
                "criado_em": pr.get("created_at"), "atualizado_em": pr.get("updated_at"),
                "commits": commits,
            }
    except httpx.HTTPError:
        return {"linked": True, "configurado": True, "erro": "Não foi possível conectar ao GitHub"}
