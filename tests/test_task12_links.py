# -*- coding: utf-8 -*-
"""Testes da TASK-12: canais consomem o link rastreado (gerar_link_afiliado).

Telegram e WhatsApp passam a usar o motor de monetização (TASK-10) com o NOME
do canal, em vez do link cru — cada clique vira atribuível. Os formatos das
mensagens são preservados. Usamos links de Mercado Livre (sem rede de shortlink).
"""

from urllib.parse import parse_qs, urlparse

from backend.config import config
from backend.channels.telegram import TelegramChannel
from backend.channels.whatsapp import WhatsAppChannel


def _query(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


OFERTA = {
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


def test_telegram_link_rastreado_usa_canal_telegram():
    link = TelegramChannel()._link_rastreado(OFERTA)
    q = _query(link)
    assert q["utm_source"] == "telegram"          # reescreve o utm_source (era site)
    assert q["sub_id"] == "telegram_mlb123456"     # canal + produto_id


def test_whatsapp_link_rastreado_usa_canal_whatsapp():
    link = WhatsAppChannel()._link_rastreado(OFERTA)
    q = _query(link)
    assert q["utm_source"] == "whatsapp"
    assert q["sub_id"] == "whatsapp_mlb123456"


def test_telegram_botao_aponta_para_link_rastreado(monkeypatch):
    """O reply_markup (botão COMPRAR) deve levar o link rastreado do canal."""
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")  # esta_configurado=ok p/ token
    canal = TelegramChannel()
    link = canal._link_rastreado(OFERTA)
    rm = canal._get_reply_markup(link)
    assert "utm_source=telegram" in rm
    assert "COMPRAR" in rm


def test_whatsapp_mensagem_preserva_formato_e_usa_link_rastreado(monkeypatch):
    monkeypatch.setattr(config, "USAR_IA_COPYWRITER", False)
    msg = WhatsAppChannel()._montar_mensagem(OFERTA)
    # formato preservado (markdown do grupo)
    assert "*Creatina 300g*" in msg
    assert "Compre em:" in msg
    # link usado é o rastreado do canal whatsapp
    assert "utm_source=whatsapp" in msg


def test_telegram_fallback_para_link_original_quando_sem_afiliado():
    o = {**OFERTA}
    o.pop("link_afiliado")
    link = TelegramChannel()._link_rastreado(o)
    assert link.startswith("https://www.mercadolivre.com.br/p/MLB-123456")
    assert _query(link)["utm_source"] == "telegram"


def test_link_rastreado_vazio_sem_url():
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
