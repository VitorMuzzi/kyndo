import os

from dotenv import load_dotenv

# Ancorado no diretório deste arquivo, nunca relativo ao cwd — mesmo motivo do
# path do banco em database.py. load_dotenv() sem argumento procura o .env a
# partir do diretório de trabalho do processo, então subir o uvicorn de
# qualquer lugar que não seja backend/ fazia o SECRET_KEY cair no fallback e o
# GITHUB_TOKEN ficar vazio, o que a tela reporta como "integração não
# configurada no servidor".
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from init_data import init_db
from migrations import assign_default_user_roles, run_migrations
from routers import atividades, attachments, audit, auth, cards, columns, drawings, emails, gestao, github, metrics, notes, relatorios, roles, suggestions, tempo, users

run_migrations()
init_db()
assign_default_user_roles()


def _purgar_lixeira_na_subida():
    from database import SessionLocal
    from lixeira import purgar_lixeira
    db = SessionLocal()
    try:
        purgar_lixeira(db)
    finally:
        db.close()


_purgar_lixeira_na_subida()

if os.getenv("KYNDO_AGENDADOR", "1") != "0":
    # Resumo diário de prazos por e-mail (não faz nada sem SMTP configurado).
    from database import SessionLocal
    from notificacoes import iniciar_agendador
    iniciar_agendador(SessionLocal)

app = FastAPI(title="Kyndo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(columns.router)
app.include_router(cards.router)
app.include_router(notes.router)
app.include_router(drawings.router)
app.include_router(audit.router)
app.include_router(suggestions.router)
app.include_router(roles.router)
app.include_router(attachments.router)
app.include_router(metrics.router)
app.include_router(github.router)
app.include_router(tempo.router)
app.include_router(gestao.router)
app.include_router(emails.router)
app.include_router(relatorios.router)
app.include_router(atividades.router)
