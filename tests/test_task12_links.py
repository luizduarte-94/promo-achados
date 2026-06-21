# -*- coding: utf-8 -*-
"""Testes dos links nos canais — TASK-12 (copy) + TASK-15 (redirect próprio).

A partir da TASK-15, os canais NÃO mandam mais o link de afiliado direto: mandam
o link curto do nosso redirecionador (`/r/{id}?c=<canal>`). A resolução do link
de afiliado real (UTMs/sub_id) passou a acontecer no servidor, na rota /r/.
Aqui validamos: link curto por canal, fallback sem id, formato preservado e a
flag de cupom relâmpago no copy.
"""

from backend.config import config
from backend.channels.telegram import TelegramChannel
from backend.channels.whatsapp import WhatsAppChannel


OFERTA = {
    "id": 42,
    "titulo": "Creatina 300g",
    "preco": 89.9,
    "preco_original": 149.9,
    "desconto_pct": 40,
    "loja": "Mercado Livre",
    "link_original": "https://www.mercadolivre.com.br/p/MLB-123456",
    "link_afiliado": "https://www.mercadolivre.com.br/p/MLB-123456?utm_source=site",
    "produto_id": "MLB123456",
    "frete_gratis": True,
}


def test_telegram_usa_link_redirect_proprio():
    link = TelegramChannel()._link_rastreado(OFERTA)
    assert "/r/42?c=telegram" in link


def test_whatsapp_usa_link_redirect_proprio():
    link = WhatsAppChannel()._link_rastreado(OFERTA)
    assert "/r/42?c=whatsapp" in link


def test_link_redirect_usa_base_configurada(monkeypatch):
    monkeypatch.setattr(config, "REDIRECT_BASE_URL", "https://api.promoachados.com")
    link = TelegramChannel()._link_rastreado(OFERTA)
    assert link == "https://api.promoachados.com/r/42?c=telegram"


def test_telegram_botao_aponta_para_redirect():
    canal = TelegramChannel()
    rm = canal._get_reply_markup(canal._link_rastreado(OFERTA))
    assert "/r/42?c=telegram" in rm
    assert "COMPRAR" in rm


def test_whatsapp_mensagem_preserva_formato_e_usa_redirect(monkeypatch):
    monkeypatch.setattr(config, "USAR_IA_COPYWRITER", False)
    msg = WhatsAppChannel()._montar_mensagem(OFERTA)
    assert "*Creatina 300g*" in msg          # formato (markdown do grupo) preservado
    assert "Compre em:" in msg
    assert "/r/42?c=whatsapp" in msg          # link do redirect próprio


def test_fallback_sem_id_usa_link_afiliado():
    o = {**OFERTA}
    o.pop("id")
    link = TelegramChannel()._link_rastreado(o)
    assert link == OFERTA["link_afiliado"]    # sem id, cai no afiliado existente


def test_link_vazio_sem_id_e_sem_url():
    assert TelegramChannel()._link_rastreado({"titulo": "x"}) == ""
    assert WhatsAppChannel()._link_rastreado({"titulo": "x"}) == ""


def test_telegram_cupom_relampago_no_post(monkeypatch):
    monkeypatch.setattr(config, "USAR_IA_COPYWRITER", False)
    o = {**OFERTA, "cupom": "RELAMPAGO10"}
    texto = TelegramChannel()._montar_post(o)
    assert "CUPOM RELÂMPAGO" in texto
    assert "RELAMPAGO10" in texto


def test_whatsapp_cupom_relampago_na_mensagem(monkeypatch):
    monkeypatch.setattr(config, "USAR_IA_COPYWRITER", False)
    o = {**OFERTA, "cupom": "RELAMPAGO10"}
    msg = WhatsAppChannel()._montar_mensagem(o)
    assert "CUPOM RELÂMPAGO" in msg
    assert "RELAMPAGO10" in msg
