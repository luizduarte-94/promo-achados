# -*- coding: utf-8 -*-
"""Testes do parser de preço do Mercado Livre (regressão do bug dos centavos)."""

import bs4

from backend.scrapers.mercadolivre import MercadoLivreScraper


def _el(html):
    return bs4.BeautifulSoup(html, "html.parser").select_one(".andes-money-amount")


def test_extrair_money_com_centavos():
    el = _el('<span class="andes-money-amount">'
             '<span class="andes-money-amount__fraction">44</span>'
             '<span class="andes-money-amount__cents">90</span></span>')
    assert MercadoLivreScraper._extrair_money(el) == 44.90


def test_extrair_money_sem_centavos():
    el = _el('<span class="andes-money-amount">'
             '<span class="andes-money-amount__fraction">129</span></span>')
    assert MercadoLivreScraper._extrair_money(el) == 129.0


def test_extrair_money_separador_de_milhar():
    el = _el('<span class="andes-money-amount">'
             '<span class="andes-money-amount__fraction">1.299</span>'
             '<span class="andes-money-amount__cents">90</span></span>')
    assert MercadoLivreScraper._extrair_money(el) == 1299.90


def test_extrair_money_none():
    assert MercadoLivreScraper._extrair_money(None) is None


def test_parsear_item_preco_e_desconto():
    """Item completo: preço atual 44,90, original 129,90 -> 65.4% OFF."""
    html = """
    <li class="ui-search-layout__item">
      <a class="poly-component__title" href="https://produto.mercadolivre.com.br/MLB-123-creatina">Creatina 300g</a>
      <div class="poly-price__current">
        <span class="andes-money-amount">
          <span class="andes-money-amount__fraction">44</span>
          <span class="andes-money-amount__cents">90</span>
        </span>
      </div>
      <span class="poly-price__installments">10x R$4,49 sem juros</span>
      <s class="andes-money-amount andes-money-amount--previous">
        <span class="andes-money-amount__fraction">129</span>
        <span class="andes-money-amount__cents">90</span>
      </s>
    </li>"""
    item = bs4.BeautifulSoup(html, "html.parser").select_one("li.ui-search-layout__item")
    oferta = MercadoLivreScraper()._parsear_item(item)
    assert oferta is not None
    assert oferta["preco"] == 44.90
    assert oferta["preco_original"] == 129.90
    assert oferta["desconto_pct"] == 65.4
    assert oferta["dados_extra"]["forma_pagamento"] == "10x R$4,49 sem juros"


def test_extrair_parcelamento_detalhe_em_ate_24x():
    html = '<p class="ui-pdp-media__title">Pague em até 24x sem juros !</p>'
    assert (
        MercadoLivreScraper._extrair_parcelamento_detalhe(html)
        == "Pague em até 24x sem juros"
    )


def test_extrair_parcelamento_detalhe_com_valor():
    html = '<p class="ui-pdp-price__subtitles">10x R$ 399,90 sem juros</p>'
    assert (
        MercadoLivreScraper._extrair_parcelamento_detalhe(html)
        == "10x de R$ 399,90 sem juros"
    )


def test_extrair_parcelamento_detalhe_sem_promessa_de_juros():
    html = '<p class="ui-pdp-price__subtitles">12x R$ 13 , 64</p>'
    assert (
        MercadoLivreScraper._extrair_parcelamento_detalhe(html)
        == "12x de R$ 13,64"
    )


def test_parcelamento_sem_juros_tem_prioridade_sobre_parcela_padrao():
    html = """
    <p class="ui-pdp-price__subtitles">12x R$ 387 , 70</p>
    <p class="ui-pdp-media__title">Pague em até 24x sem juros!</p>
    """
    assert (
        MercadoLivreScraper._extrair_parcelamento_detalhe(html)
        == "Pague em até 24x sem juros"
    )


def test_parsear_item_sem_preco_retorna_none():
    html = """
    <li class="ui-search-layout__item">
      <a class="poly-component__title" href="https://x/MLB-1-y">Produto Sem Preço</a>
    </li>"""
    item = bs4.BeautifulSoup(html, "html.parser").select_one("li.ui-search-layout__item")
    assert MercadoLivreScraper()._parsear_item(item) is None


def test_cupom_maior_que_preco_nao_e_divulgado():
    html = """
    <li>
      <a class="poly-component__title" href="https://x/MLB-1">Mochila</a>
      <div class="poly-price__current">
        <span class="andes-money-amount">
          <span class="andes-money-amount__fraction">40</span>
        </span>
      </div>
      <span class="poly-coupons__pill">Cupom R$200 OFF</span>
    </li>
    """
    item = bs4.BeautifulSoup(html, "html.parser").select_one("li")
    oferta = MercadoLivreScraper()._parsear_item(item)
    assert oferta["dados_extra"]["cupom"] == ""


def test_cupom_menor_que_preco_e_preservado():
    assert MercadoLivreScraper._cupom_coerente("Cupom R$10 OFF", 40.0) is True
