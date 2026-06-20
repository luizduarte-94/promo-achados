# -*- coding: utf-8 -*-
"""Testes da revalidação de preço antes de postar/copiar (routes.revalidar_preco)."""

import pytest

from backend.api import routes
from backend.config import config
from backend import database as db


@pytest.fixture
def oferta_teste():
    """Cria uma oferta real no banco (link MLB) e remove no fim."""
    oid = db.criar_oferta({
        "titulo": "__REVAL_TESTE__ Air Fryer 4L",
        "preco": 300.0,
        "preco_original": 400.0,
        "loja": "Mercado Livre",
        "link_original": "https://produto.mercadolivre.com.br/MLB-555-air-fryer",
        "fonte": "manual",
    })
    yield db.obter_oferta(oid)
    conn = db._get_conn()
    conn.execute("DELETE FROM ofertas WHERE id = ?", (oid,))
    conn.commit()
    conn.close()


def _fake_resultado(preco, preco_original=None, link="https://x/MLB-555-air-fryer"):
    return [{"titulo": "Air Fryer 4L", "preco": preco, "preco_original": preco_original,
             "loja": "Mercado Livre", "link_original": link}]


def test_flag_off_nao_revalida(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", False)
    assert routes.revalidar_preco(oferta_teste)["status"] == "indisponivel"


def test_preco_caiu_status_ok_e_atualiza(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    monkeypatch.setattr(routes.ml_scraper, "buscar", lambda *a, **k: _fake_resultado(250.0, 400.0))
    rev = routes.revalidar_preco(oferta_teste)
    assert rev["status"] == "ok"
    assert rev["preco_novo"] == 250.0
    assert oferta_teste["preco"] == 250.0  # mutou em memória
    assert db.obter_oferta(oferta_teste["id"])["preco"] == 250.0  # persistiu


def test_preco_subiu_acima_do_limite_status_subiu(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    monkeypatch.setattr(config, "REVALIDAR_BLOQUEIO_ALTA_PCT", 5)
    # 300 -> 360 = +20% (> 5%)
    monkeypatch.setattr(routes.ml_scraper, "buscar", lambda *a, **k: _fake_resultado(360.0, 400.0))
    rev = routes.revalidar_preco(oferta_teste)
    assert rev["status"] == "subiu"
    assert rev["variacao_pct"] == 20.0


def test_produto_sumiu_status_sumiu(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    # resultado sem o MLB-555 -> não casa
    monkeypatch.setattr(routes.ml_scraper, "buscar",
                        lambda *a, **k: _fake_resultado(250.0, link="https://x/MLB-999-outro"))
    assert routes.revalidar_preco(oferta_teste)["status"] == "sumiu"


def test_erro_de_rede_indisponivel(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    def _boom(*a, **k):
        raise RuntimeError("rede caiu")
    monkeypatch.setattr(routes.ml_scraper, "buscar", _boom)
    assert routes.revalidar_preco(oferta_teste)["status"] == "indisponivel"
