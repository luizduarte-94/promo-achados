# -*- coding: utf-8 -*-
"""Testes de dedup (produto_id), score de ofertas, preço Shopee e casamento de recorrentes."""

from backend.database import extrair_produto_id
from backend.scoring import score_oferta
from backend.scrapers.shopee import ShopeeScraper
from backend import scheduler


# --- extrair_produto_id (dedup) ---

def test_id_mlb_com_traco():
    assert extrair_produto_id("https://produto.mercadolivre.com.br/MLB-123456-x") == "MLB123456"


def test_id_mlb_sem_traco():
    assert extrair_produto_id("https://www.mercadolivre.com.br/x/p/MLB987654") == "MLB987654"


def test_id_shopee():
    assert extrair_produto_id("https://shopee.com.br/prod-i.11.22") == "shopee.11.22"


def test_id_inexistente():
    assert extrair_produto_id("https://exemplo.com/sem-id") is None


# --- score_oferta ---

def test_score_alta_maior_que_baixa():
    alta = {"desconto_pct": 45, "frete_gratis": True, "vendedor": "Loja",
            "preco": 99, "dados_extra": {"cupom": "R$20 OFF"}}
    baixa = {"desconto_pct": 5, "frete_gratis": False, "vendedor": "",
             "preco": 480, "dados_extra": {}}
    assert score_oferta(alta) > score_oferta(baixa)


def test_score_dentro_do_range():
    alta = {"desconto_pct": 90, "frete_gratis": True, "vendedor": "X",
            "preco": 10, "dados_extra": {"cupom": "50%"}}
    vazia = {"desconto_pct": 0, "preco": 0, "dados_extra": {}}
    assert score_oferta(alta) <= 100
    assert 0 <= score_oferta(vazia) <= 100


# --- Shopee _preco_float ---

def test_shopee_preco_string():
    assert ShopeeScraper._preco_float("29.90") == 29.90


def test_shopee_preco_invalido():
    assert ShopeeScraper._preco_float(None) == 0.0
    assert ShopeeScraper._preco_float("") == 0.0
    assert ShopeeScraper._preco_float("abc") == 0.0


# --- _casar_recorrente (monitoramento) ---

def test_casar_por_id_prioriza():
    res = [{"preco": 100, "link_original": "x/MLB-1-a"},
           {"preco": 80, "link_original": "x/MLB-2-b"}]
    rec = {"link_original": "y/MLB-2-z"}
    assert scheduler._casar_recorrente(rec, res)["preco"] == 80


def test_casar_sem_id_pega_menor():
    res = [{"preco": 100, "link_original": "x/MLB-1-a"},
           {"preco": 80, "link_original": "x/MLB-9-b"}]
    rec = {"link_original": None}
    assert scheduler._casar_recorrente(rec, res)["preco"] == 80


def test_casar_id_sem_match_cai_pra_menor():
    res = [{"preco": 100, "link_original": "x/MLB-1-a"},
           {"preco": 70, "link_original": "x/MLB-2-b"}]
    rec = {"link_original": "y/MLB-999-z"}
    assert scheduler._casar_recorrente(rec, res)["preco"] == 70


def test_casar_lista_vazia():
    assert scheduler._casar_recorrente({"link_original": None}, []) is None
