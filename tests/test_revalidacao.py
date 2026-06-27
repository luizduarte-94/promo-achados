# -*- coding: utf-8 -*-
"""Testes da revalidação de preço antes de postar/copiar (precos.revalidar_preco)."""

import pytest
from datetime import datetime, timedelta, timezone

from backend import precos
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
    assert precos.revalidar_preco(oferta_teste)["status"] == "indisponivel"


def test_preco_caiu_status_ok_e_atualiza(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    monkeypatch.setattr(precos.ml_scraper, "buscar", lambda *a, **k: _fake_resultado(250.0, 400.0))
    monkeypatch.setattr(precos.ml_scraper, "buscar_parcelamento", lambda link: "Pague em até 24x sem juros")
    rev = precos.revalidar_preco(oferta_teste)
    assert rev["status"] == "ok"
    assert rev["preco_novo"] == 250.0
    assert oferta_teste["preco"] == 250.0  # mutou em memória
    assert db.obter_oferta(oferta_teste["id"])["preco"] == 250.0  # persistiu
    assert oferta_teste["dados_extra"]["parcelamento_destaque"] == "Pague em até 24x sem juros"
    assert db.obter_oferta(oferta_teste["id"])["dados_extra"]["parcelamento_destaque"] == "Pague em até 24x sem juros"


def test_preco_subiu_acima_do_limite_status_subiu(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    monkeypatch.setattr(config, "REVALIDAR_BLOQUEIO_ALTA_PCT", 5)
    # 300 -> 360 = +20% (> 5%)
    monkeypatch.setattr(precos.ml_scraper, "buscar", lambda *a, **k: _fake_resultado(360.0, 400.0))
    rev = precos.revalidar_preco(oferta_teste)
    assert rev["status"] == "subiu"
    assert rev["variacao_pct"] == 20.0


def test_produto_sumiu_status_sumiu(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    # resultado sem o MLB-555 -> não casa
    monkeypatch.setattr(precos.ml_scraper, "buscar",
                        lambda *a, **k: _fake_resultado(250.0, link="https://x/MLB-999-outro"))
    assert precos.revalidar_preco(oferta_teste)["status"] == "sumiu"


def test_erro_de_rede_indisponivel(monkeypatch, oferta_teste):
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    def _boom(*a, **k):
        raise RuntimeError("rede caiu")
    monkeypatch.setattr(precos.ml_scraper, "buscar", _boom)
    assert precos.revalidar_preco(oferta_teste)["status"] == "indisponivel"


def test_casamento_ml_prioriza_wid_exato():
    origem = "https://mercadolivre.com.br/produto/p/MLB100#wid=MLB222"
    resultados = [
        {"link_original": "https://mercadolivre.com.br/produto/p/MLB100#wid=MLB111"},
        {"link_original": "https://mercadolivre.com.br/produto/p/MLB100#wid=MLB222"},
    ]
    assert precos.casar_por_produto_id(origem, resultados) is resultados[1]


def test_casamento_ml_nao_cai_para_outro_wid_do_catalogo():
    origem = "https://mercadolivre.com.br/produto/p/MLB100#wid=MLB222"
    resultados = [
        {"link_original": "https://mercadolivre.com.br/produto/p/MLB100#wid=MLB111"},
    ]
    assert precos.casar_por_produto_id(origem, resultados) is None


def test_preco_confirmado_manual_nao_e_sobrescrito_pelo_catalogo(monkeypatch, oferta_teste):
    extras = {
        "preco_confirmado_manual": 99.98,
        "preco_confirmado_em": datetime.now(timezone.utc).isoformat(),
        "parcelamento_manual": "12x de R$ 9,85",
    }
    db.atualizar_oferta(oferta_teste["id"], {"dados_extra": extras})
    oferta = db.obter_oferta(oferta_teste["id"])
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    monkeypatch.setattr(precos.ml_scraper, "buscar", lambda *a, **k: _fake_resultado(40.0, 99.98))

    rev = precos.revalidar_preco(oferta)

    assert rev["status"] == "ok"
    assert rev["fonte_preco"] == "confirmado_manual"
    assert oferta["preco"] == 99.98
    assert oferta["dados_extra"]["parcelamento_destaque"] == "12x de R$ 9,85"


def test_preco_confirmado_expirado_bloqueia_revalidacao(monkeypatch, oferta_teste):
    extras = {
        "preco_confirmado_manual": 99.98,
        "preco_confirmado_em": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
    }
    db.atualizar_oferta(oferta_teste["id"], {"dados_extra": extras})
    oferta = db.obter_oferta(oferta_teste["id"])
    monkeypatch.setattr(config, "REVALIDAR_PRECO_ENABLED", True)
    def _nao_buscar(*args, **kwargs):
        raise AssertionError("confirmação expirada deve bloquear antes da rede")
    monkeypatch.setattr(precos.ml_scraper, "buscar", _nao_buscar)

    assert precos.revalidar_preco(oferta)["status"] == "confirmacao_expirada"
