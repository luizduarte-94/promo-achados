# -*- coding: utf-8 -*-
"""Proteção CSRF do OAuth Mercado Livre via state de uso único."""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import main
from backend.api import routes
from backend.config import config


class _TokenResponse:
    ok = True

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "access_token": "access-test",
            "refresh_token": "refresh-test",
            "expires_in": 3600,
        }


@pytest.fixture(autouse=True)
def oauth_config(monkeypatch):
    monkeypatch.setattr(config, "PANEL_USER", "admin")
    monkeypatch.setattr(config, "PANEL_PASSWORD", "segredo")
    monkeypatch.setattr(config, "ML_CLIENT_ID", "client-test")
    monkeypatch.setattr(config, "ML_CLIENT_SECRET", "secret-test")
    monkeypatch.setattr(config, "REDIRECT_BASE_URL", "https://promo.example.com")
    with routes._ml_oauth_states_lock:
        routes._ml_oauth_states.clear()
    yield
    with routes._ml_oauth_states_lock:
        routes._ml_oauth_states.clear()


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def _novo_state(client) -> str:
    resp = client.get("/api/ml/auth_url", auth=("admin", "segredo"))
    assert resp.status_code == 200
    query = parse_qs(urlparse(resp.json()["url"]).query)
    assert query["redirect_uri"] == ["https://promo.example.com/api/ml/callback"]
    return query["state"][0]


def test_callback_aceita_state_valido_uma_vez(client, monkeypatch):
    state = _novo_state(client)
    gravados = {}
    monkeypatch.setattr(routes.requests, "post", lambda *args, **kwargs: _TokenResponse())
    monkeypatch.setattr(routes.db, "definir_configuracao", gravados.__setitem__)

    resp = client.get(
        "/api/ml/callback",
        params={"code": "code-test", "state": state},
        follow_redirects=False,
    )

    assert resp.status_code == 307
    assert resp.headers["location"] == "/?ml_connected=true"
    assert gravados["ml_access_token"] == "access-test"

    replay = client.get(
        "/api/ml/callback",
        params={"code": "code-test", "state": state},
        follow_redirects=False,
    )
    assert replay.headers["location"].endswith("error=invalid_state")


def test_callback_rejeita_state_ausente(client, monkeypatch):
    chamado = False

    def _nao_chamar(*args, **kwargs):
        nonlocal chamado
        chamado = True

    monkeypatch.setattr(routes.requests, "post", _nao_chamar)
    resp = client.get("/api/ml/callback?code=code-test", follow_redirects=False)
    assert resp.headers["location"].endswith("error=invalid_state")
    assert chamado is False


def test_callback_rejeita_state_invalido(client):
    resp = client.get(
        "/api/ml/callback?code=code-test&state=state-invalido",
        follow_redirects=False,
    )
    assert resp.headers["location"].endswith("error=invalid_state")


def test_callback_rejeita_state_expirado(client):
    state = _novo_state(client)
    with routes._ml_oauth_states_lock:
        routes._ml_oauth_states[state] = time_expirado = routes.time.time() - 1
    assert time_expirado < routes.time.time()

    resp = client.get(
        "/api/ml/callback",
        params={"code": "code-test", "state": state},
        follow_redirects=False,
    )
    assert resp.headers["location"].endswith("error=invalid_state")
