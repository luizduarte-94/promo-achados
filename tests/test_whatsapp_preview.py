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
    assert "Compre em: https://meli.la/abc" in t
    assert "44,90" in t  # preço com centavos formatado pt-BR


def test_preview_formato_grupo():
    t = WhatsAppChannel().preview(OFERTA)
    assert "*Por: R$ 44,90 à vista*" in t   # preço em negrito + "à vista"
    assert "% OFF*" in t                     # desconto em negrito
    assert "~R$" in t                        # preço original tachado
    assert "Adicione esse contato na sua agenda." in t  # truque do contato


def test_preview_inclui_cupom():
    t = WhatsAppChannel().preview(OFERTA)
    assert "Utilize o cupom: R$10 OFF" in t


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
    assert "cupom" not in t.lower()
    assert t  # não vazio


def test_preview_linktree_so_quando_configurado(monkeypatch):
    from backend import config as cfgmod
    monkeypatch.setattr(cfgmod.config, "LINKTREE_URL", "")
    assert "Economize também" not in WhatsAppChannel().preview(OFERTA)
    monkeypatch.setattr(cfgmod.config, "LINKTREE_URL", "https://linktr.ee/teste")
    t = WhatsAppChannel().preview(OFERTA)
    assert "Economize também em outras categorias:" in t
    assert "https://linktr.ee/teste" in t
