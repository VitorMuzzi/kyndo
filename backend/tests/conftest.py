import os
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be set BEFORE importing main/database so the app binds to an isolated DB.
_db_path = os.path.join(tempfile.gettempdir(), f"kyndo_test_{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "t" * 64

import pytest
from fastapi.testclient import TestClient

import security
from main import app


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    security._login_attempts.clear()
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, nome, senha):
    r = client.post("/login", json={"nome": nome, "senha": senha})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def admin_token(client):
    return login(client, "admin", "admin")["token"]


def create_user(client, admin_token, nome, senha="senha123", role="usuario"):
    r = client.post("/users", json={"nome": nome, "senha": senha, "role": role}, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    return login(client, nome, senha)


@pytest.fixture(scope="session")
def maria(client, admin_token):
    return create_user(client, admin_token, "maria")


@pytest.fixture(scope="session")
def joao(client, admin_token):
    return create_user(client, admin_token, "joao")
