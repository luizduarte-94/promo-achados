# -*- coding: utf-8 -*-
"""Barreiras contra divulgação de oferta do ML sem meli.la comissionado."""

import pytest
from fastapi.testclient import TestClient

import main
from backend import database as db
from backend.config import config


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "PANEL_USER", "admin")
    monkeypatch.setattr(config, "PANEL_PASSWORD", "segredo")
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def oferta_ml():
    oid = db.criar_oferta({
        "titulo": "Oferta ML sem comissão",
        "preco": 50.0,
        "loja": "Mercado Livre",
        "link_original": "https://x/MLB-7000001",
    })
    yield oid
    db.deletar_oferta(oid)


def test_api_rejeita_link_ml_que_nao_e_meli_la(client, oferta_ml):
    resp = client.put(
        f"/api/ofertas/{oferta_ml}",
        json={"link_afiliado": "https://x/MLB-7000001?utm_source=site"},
        auth=("admin", "segredo"),
    )
    assert resp.status_code == 400
    assert "meli.la" in resp.json()["detail"]


def test_api_aceita_meli_la_e_preserva_exatamente(client, oferta_ml):
    link = "https://meli.la/abc123"
    resp = client.put(
        f"/api/ofertas/{oferta_ml}",
        json={"link_afiliado": link},
        auth=("admin", "segredo"),
    )
    assert resp.status_code == 200
    assert db.obter_oferta(oferta_ml)["link_afiliado"] == link


def test_api_salva_preco_e_parcelamento_confirmados(client, oferta_ml):
    resp = client.put(
        f"/api/ofertas/{oferta_ml}",
        json={
            "link_afiliado": "https://meli.la/abc123",
            "preco_confirmado": 99.98,
            "parcelamento_confirmado": "12x de R$ 9,85",
        },
        auth=("admin", "segredo"),
    )
    assert resp.status_code == 200
    oferta = db.obter_oferta(oferta_ml)
    assert oferta["preco"] == 99.98
    assert oferta["dados_extra"]["preco_confirmado_manual"] == 99.98
    assert oferta["dados_extra"]["parcelamento_manual"] == "12x de R$ 9,85"
    assert oferta["dados_extra"]["cupom"] == ""


def test_postagem_bloqueia_ml_sem_meli_la_antes_de_enviar(client, oferta_ml, monkeypatch):
    enviado = False

    def _nao_enviar(*args, **kwargs):
        nonlocal enviado
        enviado = True

    from backend.api import routes
    monkeypatch.setattr(routes.canais["telegram"], "enviar", _nao_enviar)
    resp = client.post(
        f"/api/ofertas/{oferta_ml}/postar",
        json={"canais": ["telegram"]},
        auth=("admin", "segredo"),
    )
    assert resp.status_code == 400
    assert "meli.la" in resp.json()["detail"]
    assert enviado is False
