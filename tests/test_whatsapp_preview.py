# -*- coding: utf-8 -*-
"""Testes do preview de mensagem do WhatsApp (modo copiar manual)."""

from backend.channels.whatsapp import WhatsAppChannel

OFERTA = {
    "titulo": "Creatina Monohidratada 300g",
    "preco": 44.90,
    "preco_original": 129.90,
    "desconto_pct": 65,
    "loja": "Mercado Livre",
    "link_afiliado": "https://meli.la/abc",
    "frete_gratis": True,
    "dados_extra": {"cupom": "R$10 OFF"},
}


def test_preview_tem_titulo_preco_link():
    t = WhatsAppChannel().preview(OFERTA)
    assert "Creatina Monohidratada 300g" in t
    assert "meli.la/abc" in t
    assert "44,90" in t  # preço com centavos formatado pt-BR


def test_preview_usa_negrito_whatsapp():
    t = WhatsAppChannel().preview(OFERTA)
    assert "*Por:" in t          # linha do preço em negrito
    assert "% OFF*" in t         # desconto em negrito
    assert "~R$" in t            # preço original tachado


def test_preview_inclui_cupom():
    t = WhatsAppChannel().preview(OFERTA)
    assert "R$10 OFF" in t


def test_preview_sem_preco_original_nao_tem_de():
    o = dict(OFERTA)
    o.pop("preco_original")
    t = WhatsAppChannel().preview(o)
    assert "De:" not in t
    assert "*Por:" in t


def test_preview_sem_cupom_nao_quebra():
    o = dict(OFERTA)
    o["dados_extra"] = {}
    t = WhatsAppChannel().preview(o)
    assert "Cupom" not in t
    assert t  # não vazio
