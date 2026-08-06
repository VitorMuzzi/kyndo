from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from init_data import init_db
from migrations import assign_default_user_roles, run_migrations
from routers import audit, auth, cards, columns, drawings, notes, roles, suggestions, users

run_migrations()
init_db()
assign_default_user_roles()

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
