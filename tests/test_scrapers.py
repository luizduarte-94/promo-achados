# -*- coding: utf-8 -*-
"""Testes dos scrapers na nova arquitetura (TASK-07).

Os scrapers só raspam e devolvem list[dict] — não acessam banco. A persistência
acontece via db.coletar_e_salvar (ORM/Postgres). Aqui validamos o parsing e que
a SAÍDA do scraper grava corretamente pelo ORM (SQLite de teste via conftest).
"""

import datetime as dt
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


def test_shopee_high_commission_acima_do_limiar(monkeypatch):
    """Comissão >= limiar marca high_commission (fila VIP); abaixo, não."""
    monkeypatch.setattr(config, "SHOPEE_HIGH_COMMISSION_PCT", 0.10)
    alta = ShopeeScraper()._parsear_item({
        "productName": "Fone Alta Comissão", "priceMin": "50.00",
        "productLink": "https://shopee.com.br/x-i.1.2", "commissionRate": "0.15",
    })
    baixa = ShopeeScraper()._parsear_item({
        "productName": "Fone Baixa Comissão", "priceMin": "50.00",
        "productLink": "https://shopee.com.br/y-i.3.4", "commissionRate": "0.05",
    })
    assert alta["high_commission"] is True
    assert baixa["high_commission"] is False


def test_shopee_oferta_loja_parseia_validade_e_cupom():
    """shopeeOfferV2: extrai expira_em (epoch->datetime) e cupom da oferta relâmpago."""
    fim = int(dt.datetime(2030, 1, 1, 12, 0).timestamp())
    o = ShopeeScraper()._parsear_oferta_loja({
        "offerName": "Cupom Relâmpago 20%",
        "originalLink": "https://shopee.com.br/oferta",
        "offerLink": "https://s.shopee.com.br/ABC",
        "commissionRate": "0.18",
        "periodEndTime": fim,
        "couponCode": "SHOPEE20",
    })
    assert o["titulo"] == "Cupom Relâmpago 20%"
    assert o["fonte"] == "shopee_oferta"
    assert o["cupom"] == "SHOPEE20"
    assert isinstance(o["expira_em"], dt.datetime)
    assert o["expira_em"].year == 2030
    assert o["high_commission"] is True


def test_shopee_epoch_invalido_vira_none():
    assert ShopeeScraper()._epoch_para_dt(None) is None
    assert ShopeeScraper()._epoch_para_dt(0) is None
    assert ShopeeScraper()._epoch_para_dt("lixo") is None


def test_shopee_high_commission_persiste_via_orm():
    """Saída do scraper (high_commission/cupom/expira_em) grava na ORM."""
    expira = dt.datetime(2031, 6, 1, 9, 0)
    ofertas = [{
        "titulo": "Whey Alta Comissao ORM",
        "preco": 70.0, "preco_original": 140.0,
        "loja": "Shopee",
        "link_original": "https://shopee.com.br/whey-i.55.66",
        "high_commission": True, "cupom": "WHEY10", "expira_em": expira,
    }]
    novas = db.coletar_e_salvar(ofertas)
    try:
        o = db.obter_oferta(novas[0]["id"])
        assert o["high_commission"] is True
        assert o["cupom"] == "WHEY10"
        assert o["expira_em"] is not None
    finally:
        db.deletar_oferta(novas[0]["id"])


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
