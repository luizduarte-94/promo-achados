# -*- coding: utf-8 -*-
"""Testes do motor de afiliados / tracking (TASK-10).

Serviço puro (sem rede): valida injeção de UTMs, composição de sub_id, escolha de
canal e idempotência. Sem credencial Shopee, o shortlink degrada para o link
longo rastreado. Também cobre a integração com a ingestão (coletar_e_salvar).
"""

from urllib.parse import parse_qs, urlparse

from backend import database as db
from backend.config import config
from backend.monetization import (
    aplicar_utms,
    eh_link_afiliado_ml,
    gerar_link_afiliado,
    montar_sub_id,
    oferta_tem_link_afiliado_valido,
)


def _query(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_aplicar_utms_adiciona_parametros():
    url = aplicar_utms("https://x.com/p", utm_source="telegram", utm_medium="afiliados")
    q = _query(url)
    assert q["utm_source"] == "telegram"
    assert q["utm_medium"] == "afiliados"


def test_aplicar_utms_e_idempotente():
    """Reaplicar não duplica a chave (sobrescreve)."""
    u1 = aplicar_utms("https://x.com/p?a=1", utm_source="telegram")
    u2 = aplicar_utms(u1, utm_source="whatsapp")
    q = _query(u2)
    assert q["utm_source"] == "whatsapp"      # sobrescreveu
    assert q["a"] == "1"                        # preservou o que já existia
    assert u2.count("utm_source=") == 1         # sem duplicação


def test_aplicar_utms_ignora_vazios():
    url = aplicar_utms("https://x.com/p", utm_source="site", sub_id="")
    assert "sub_id" not in _query(url)


def test_montar_sub_id_normaliza():
    assert montar_sub_id("Telegram", "MLB-123") == "telegram_mlb123"
    assert montar_sub_id(None, None) == ""
    assert len(montar_sub_id("telegram", "x" * 80)) <= 50


def test_gerar_link_ml_adiciona_tracking(monkeypatch):
    monkeypatch.setattr(config, "UTM_CAMPAIGN", "promoachados")
    monkeypatch.setattr(config, "UTM_MEDIUM", "afiliados")
    url = gerar_link_afiliado(
        "https://www.mercadolivre.com.br/p/MLB-555",
        canal="telegram",
        produto_id="MLB555",
    )
    q = _query(url)
    assert q["utm_source"] == "telegram"
    assert q["utm_campaign"] == "promoachados"
    assert q["sub_id"] == "telegram_mlb555"


def test_gerar_link_usa_canal_padrao_quando_omitido(monkeypatch):
    monkeypatch.setattr(config, "AFILIADO_CANAL_PADRAO", "site")
    url = gerar_link_afiliado("https://x.com/p")
    assert _query(url)["utm_source"] == "site"


def test_gerar_shopee_sem_credencial_mantem_link_longo(monkeypatch):
    """Sem App ID/Secret, não encurta — devolve link longo já rastreado."""
    monkeypatch.setattr(config, "SHOPEE_APP_ID", "")
    monkeypatch.setattr(config, "SHOPEE_APP_SECRET", "")
    url = gerar_link_afiliado(
        "https://shopee.com.br/produto-i.11.22", canal="whatsapp", produto_id="shopee.11.22"
    )
    assert url.startswith("https://shopee.com.br/")
    q = _query(url)
    assert q["utm_source"] == "whatsapp"
    assert q["sub_id"] == "whatsapp_shopee1122"


def test_url_vazia_nao_quebra():
    assert gerar_link_afiliado("") == ""
    assert aplicar_utms("", utm_source="x") == ""


def test_ingestao_ml_nao_finge_link_afiliado_com_utm(monkeypatch):
    """UTM no link original do ML não é comissão; aguarda meli.la manual."""
    monkeypatch.setattr(config, "AFILIADO_CANAL_PADRAO", "site")
    ofertas = [{
        "titulo": "Mouse Gamer Monetiza",
        "preco": 80.0,
        "loja": "Mercado Livre",
        "link_original": "https://x/MLB-9090901-mouse",
    }]
    novas = db.coletar_e_salvar(ofertas)
    try:
        o = db.obter_oferta(novas[0]["id"])
        assert o["link_afiliado"] is None
    finally:
        db.deletar_oferta(novas[0]["id"])


def test_link_ml_valido_exige_https_meli_la():
    assert eh_link_afiliado_ml("https://meli.la/abc") is True
    assert eh_link_afiliado_ml("https://meli.la/") is False
    assert eh_link_afiliado_ml("http://meli.la/abc") is False
    assert eh_link_afiliado_ml("https://mercadolivre.com.br/produto?utm_source=site") is False
    assert oferta_tem_link_afiliado_valido({
        "loja": "Mercado Livre", "link_afiliado": "https://meli.la/abc",
    }) is True
    assert oferta_tem_link_afiliado_valido({
        "loja": "Mercado Livre", "link_afiliado": "https://x/MLB-1?utm_source=site",
    }) is False


def test_ingestao_preserva_link_afiliado_existente():
    """Se a oferta já traz link_afiliado, a ingestão não sobrescreve."""
    ofertas = [{
        "titulo": "Teclado Preserva Link",
        "preco": 120.0,
        "loja": "Shopee",
        "link_original": "https://shopee.com.br/teclado-i.33.44",
        "link_afiliado": "https://s.shopee.com.br/JAREADY",
    }]
    novas = db.coletar_e_salvar(ofertas)
    try:
        o = db.obter_oferta(novas[0]["id"])
        assert o["link_afiliado"] == "https://s.shopee.com.br/JAREADY"
    finally:
        db.deletar_oferta(novas[0]["id"])
