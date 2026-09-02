import routers.github as github_module
from tests.conftest import auth


def _create_card(client, token, autor, **overrides):
    payload = {"titulo": "Card com PR", "status": "col-1", "autor": autor, **overrides}
    r = client.post("/cards", json=payload, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


class _FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, responses):
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, headers=None, params=None):
        for key, resp in self._responses.items():
            if key in url:
                return resp
        raise AssertionError(f"Unexpected URL requested in test: {url}")


def _mock_github_api(monkeypatch, responses):
    monkeypatch.setattr(github_module, "GITHUB_TOKEN", "fake-token-for-tests")
    monkeypatch.setattr(github_module.httpx, "Client", lambda *a, **kw: _FakeClient(responses))


def test_card_without_pr_link_reports_not_linked(client, admin_token):
    card = _create_card(client, admin_token, "admin")
    r = client.get(f"/cards/{card['id']}/github", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json() == {"linked": False}


def test_pr_link_without_token_reports_unconfigured(client, admin_token, monkeypatch):
    monkeypatch.setattr(github_module, "GITHUB_TOKEN", "")
    card = _create_card(client, admin_token, "admin", github_url="https://github.com/acme/kyndo/pull/42")
    r = client.get(f"/cards/{card['id']}/github", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json() == {"linked": True, "configurado": False}


def test_pr_link_returns_state_checks_and_commits(client, admin_token, monkeypatch):
    responses = {
        "/repos/acme/kyndo/pulls/42/commits": _FakeResponse(200, [
            {"sha": "aaaaaaaaaaaa", "commit": {"message": "primeiro commit\n\ndetalhe", "author": {"name": "Fulano", "date": "2026-01-01T10:00:00Z"}}, "author": {"login": "fulano"}, "html_url": "https://github.com/acme/kyndo/commit/aaaaaaaaaaaa"},
            {"sha": "bbbbbbbbbbbb", "commit": {"message": "segundo commit", "author": {"name": "Fulano", "date": "2026-01-02T10:00:00Z"}}, "author": {"login": "fulano"}, "html_url": "https://github.com/acme/kyndo/commit/bbbbbbbbbbbb"},
        ]),
        "/repos/acme/kyndo/pulls/42": _FakeResponse(200, {
            "state": "open", "merged": False, "title": "Minha PR", "html_url": "https://github.com/acme/kyndo/pull/42",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z", "head": {"sha": "deadbeef"},
        }),
    }
    _mock_github_api(monkeypatch, responses)

    card = _create_card(client, admin_token, "admin", github_url="https://github.com/acme/kyndo/pull/42")
    r = client.get(f"/cards/{card['id']}/github", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["linked"] is True
    assert body["configurado"] is True
    assert body["estado"] == "aberta"
    assert "checks_status" not in body
    assert body["numero"] == 42
    assert [c["titulo"] for c in body["commits"]] == ["segundo commit", "primeiro commit"]  # most recent first


def test_pr_link_reports_merged_state(client, admin_token, monkeypatch):
    responses = {
        "/repos/acme/kyndo/pulls/7/commits": _FakeResponse(200, []),
        "/repos/acme/kyndo/pulls/7": _FakeResponse(200, {
            "state": "closed", "merged": True, "title": "PR mergeada", "html_url": "https://github.com/acme/kyndo/pull/7",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z", "head": {"sha": None},
        }),
    }
    _mock_github_api(monkeypatch, responses)

    card = _create_card(client, admin_token, "admin", github_url="https://github.com/acme/kyndo/pull/7")
    r = client.get(f"/cards/{card['id']}/github", headers=auth(admin_token))
    assert r.json()["estado"] == "mergeada"


def test_pr_not_found_on_github_reports_error(client, admin_token, monkeypatch):
    _mock_github_api(monkeypatch, {"/repos/acme/kyndo/pulls/999": _FakeResponse(404, {})})
    card = _create_card(client, admin_token, "admin", github_url="https://github.com/acme/kyndo/pull/999")
    r = client.get(f"/cards/{card['id']}/github", headers=auth(admin_token))
    body = r.json()
    assert body["linked"] is True
    assert "erro" in body
