# -*- coding: utf-8 -*-
"""Testes da extração de produto do espelho (mensagens de grupo -> termo de busca)."""

from backend.espelho import extrair_produto


def test_corta_no_preco_e_remove_cupom():
    t = extrair_produto("🔥 Air Fryer Mondial 4L por R$ 299,90 só hoje! Use o cupom AIR20 e aproveite")
    assert t == "Air Fryer Mondial 4L"


def test_fone_sem_preco_mantem_nome():
    t = extrair_produto("‼️ Fone de Ouvido Bluetooth JBL Tune 520BT com desconto imperdível https://meli.la/x")
    assert t == "Fone de Ouvido Bluetooth JBL Tune"


def test_tv_remove_promo_e_corta_preco():
    t = extrair_produto("Promoção Smart TV Samsung 50 polegadas 4K frete grátis por apenas R$ 1999,00")
    assert t == "Smart TV Samsung 50 polegadas 4K"


def test_texto_vazio():
    assert extrair_produto("") == ""
    assert extrair_produto(None) == ""


def test_so_promo_vira_vazio_ou_curto():
    # só palavras de promoção/preço -> sem nome de produto
    t = extrair_produto("🔥 OFERTA imperdível! Aproveite, corre! R$ 9,99")
    assert "R$" not in t
    assert "imperdível" not in t.lower()


def test_max_6_palavras():
    t = extrair_produto("Liquidificador Philco Turbo Inox 12 Velocidades 1200W Potente Profissional")
    assert len(t.split()) <= 6
