# -*- coding: utf-8 -*-
"""Testes dos scrapers na nova arquitetura (TASK-07).

Os scrapers só raspam e devolvem list[dict] — não acessam banco. A persistência
acontece via db.coletar_e_salvar (ORM/Postgres). Aqui validamos o parsing e que
a SAÍDA do scraper grava corretamente pelo ORM (SQLite de teste via conftest).
"""

import inspect

from backend import database as db
from backend.config import config
from backend.scrapers.mercadolivre import MercadoLivreScraper
from backend.scrapers.shopee import ShopeeScraper


def test_shopee_sem_credencial_retorna_vazio(monkeypatch):
    monkeypatch.setattr(config, "SHOPEE_APP_ID", "")
    monkeypatch.setattr(config, "SHOPEE_APP_SECRET", "")
    assert ShopeeScraper().buscar("creatina") == []


def test_shopee_parsear_item_formato():
    node = {
        "productName": "Whey Protein 1kg",
        "priceMin": "99.90",
        "priceOriginal": "149.90",
        "productLink": "https://shopee.com.br/whey-i.11.22",
        "imageUrl": "http://img/x.jpg",
        "shopName": "Loja Oficial",
        "ratingStar": "4.8",
        "commissionRate": "0.1",
        "sales": 500,
        "categoryName": "Suplementos",
    }
    o = ShopeeScraper()._parsear_item(node)
    assert o["titulo"] == "Whey Protein 1kg"
    assert o["preco"] == 99.90
    assert o["preco_original"] == 149.90
    assert o["loja"] == "Shopee"
    assert o["fonte"] == "shopee_api"
    assert o["link_original"].endswith("i.11.22")


def test_ml_buscar_aceita_filtrar_qualidade():
    # o monitor/revalidação chamam buscar(filtrar_qualidade=False)
    assert "filtrar_qualidade" in inspect.signature(MercadoLivreScraper.buscar).parameters


def test_saida_do_scraper_grava_via_orm():
    """Saída típica do scraper (dicts) -> coletar_e_salvar -> banco (ORM)."""
    ofertas = [{
        "titulo": "Creatina Scraper ORM 300g",
        "preco": 59.9,
        "preco_original": 99.9,
        "loja": "Mercado Livre",
        "link_original": "https://x/MLB-3030301-creatina",
        "fonte": "mercadolivre_scraping",
        "dados_extra": {"cupom": "Z10"},
    }]
    novas = db.coletar_e_salvar(ofertas)
    try:
        assert len(novas) == 1
        o = db.obter_oferta(novas[0]["id"])
        assert o["titulo"] == "Creatina Scraper ORM 300g"
        assert o["fonte"] == "mercadolivre_scraping"
        assert o["dados_extra"] == {"cupom": "Z10"}
        assert o["departamento_nome"] == "Fitness & Academia"   # classificou
        assert o["produto_id"] == "MLB3030301"                  # ID estável (dedup)
    finally:
        db.deletar_oferta(novas[0]["id"])
