# -*- coding: utf-8 -*-
"""Contratos de autenticação pública/admin e cache dos assets."""

import re

import pytest
from fastapi.testclient import TestClient

import main
from backend import database as db
from backend.config import config


@pytest.fixture
def client_protegido(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "PANEL_USER", "admin")
    monkeypatch.setattr(config, "PANEL_PASSWORD", "segredo")
    with TestClient(main.app) as client:
        yield client


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/", 200),
        ("/css/style.css", 200),
        ("/js/app.js", 200),
        ("/api/ofertas", 200),
        ("/r/99999999", 404),
    ],
)
def test_rotas_publicas_sem_auth_com_painel_protegido(client_protegido, path, status):
    resp = client_protegido.get(path, follow_redirects=False)
    assert resp.status_code == status
    assert resp.status_code != 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/ofertas/1",
        "/api/ofertas/1/mensagem",
        "/api/dashboard/stats",
        "/api/historico",
        "/api/configuracoes",
        "/api/ml/auth_url",
        "/api/departamentos",
        "/api/historico-precos",
        "/api/historico-precos/menor",
        "/api/produtos-recorrentes",
        "/analytics/summary",
    ],
)
def test_gets_administrativos_exigem_auth(client_protegido, path):
    assert client_protegido.get(path).status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/ofertas"),
        ("PUT", "/api/ofertas/1"),
        ("DELETE", "/api/ofertas/1"),
        ("POST", "/api/ofertas/1/postar"),
        ("POST", "/api/ofertas/postar-lote"),
        ("POST", "/api/buscar"),
        ("POST", "/api/departamentos"),
        ("PUT", "/api/departamentos/1"),
        ("POST", "/api/produtos-recorrentes"),
        ("PUT", "/api/produtos-recorrentes/1"),
        ("DELETE", "/api/produtos-recorrentes/1"),
    ],
)
def test_todas_as_mutacoes_exigem_auth(client_protegido, method, path):
    resp = client_protegido.request(method, path, json={})
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].startswith("Basic ")


def test_admin_aceita_credencial_valida(client_protegido):
    resp = client_protegido.get("/api/dashboard/stats", auth=("admin", "segredo"))
    assert resp.status_code == 200


def test_index_injeta_versao_e_revalida(client_protegido, monkeypatch):
    monkeypatch.setattr(main, "_asset_version", lambda: "123456")
    resp = client_protegido.get("/")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
    assert re.findall(r'(?:style\.css|app\.js)\?v=([^"\']+)', resp.text) == [
        "123456",
        "123456",
    ]


@pytest.mark.parametrize("path", ["/css/style.css", "/js/app.js"])
def test_asset_versionado_tem_cache_longo_e_validadores(client_protegido, path):
    resp = client_protegido.get(f"{path}?v=123456")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resp.headers.get("etag")
    assert resp.headers.get("last-modified")


@pytest.mark.parametrize("path", ["/css/style.css", "/js/app.js"])
def test_asset_sem_versao_revalida_e_preserva_validadores(client_protegido, path):
    resp = client_protegido.get(path)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers.get("etag")
    assert resp.headers.get("last-modified")
