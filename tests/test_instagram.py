# -*- coding: utf-8 -*-
"""Testes do canal Instagram via Meta Graph API (TASK-11).

Sem rede: `requests.post` é mockado e inspecionamos os payloads (image_url,
caption, media_type, children, link). O fluxo é container -> media_publish.
"""

import pytest

from backend.config import config
from backend.channels import instagram as ig_mod
from backend.channels.instagram import InstagramChannel
from backend.templates.instagram_captions import caption_feed, caption_carrossel


class FakeResp:
    def __init__(self, ok=True, payload=None, text=""):
        self.ok = ok
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def ig(monkeypatch):
    """Canal configurado + sem espera real + gravador de chamadas à Graph API."""
    monkeypatch.setattr(config, "INSTAGRAM_ACCESS_TOKEN", "TOKEN_X")
    monkeypatch.setattr(config, "INSTAGRAM_USER_ID", "1784")
    # instagram_ok é classmethod (lê atributos de classe); mockamos direto.
    monkeypatch.setattr(config, "instagram_ok", lambda: True)
    monkeypatch.setattr(ig_mod.time, "sleep", lambda *_: None)

    chamadas = []
    contador = {"n": 0}

    def fake_post(url, data=None, timeout=None, **kw):
        chamadas.append({"url": url, "data": data})
        if url.endswith("/media"):
            contador["n"] += 1
            return FakeResp(ok=True, payload={"id": f"CID{contador['n']}"})
        if url.endswith("/media_publish"):
            return FakeResp(ok=True, payload={"id": "PUBLISHED"})
        return FakeResp(ok=False, text="rota inesperada")

    monkeypatch.setattr(ig_mod.requests, "post", fake_post)
    return InstagramChannel(), chamadas


OFERTA = {
    "id": 77,
    "titulo": "Fone Bluetooth Pro",
    "preco": 99.9,
    "preco_original": 199.9,
    "desconto_pct": 50,
    "loja": "Shopee",
    "frete_gratis": True,
    "imagem_url": "https://img/x.jpg",
    "link_original": "https://shopee.com.br/fone-i.11.22",
    "produto_id": "shopee.11.22",
}


def test_publicar_feed_fluxo_container_publish(ig):
    canal, chamadas = ig
    res = canal.publicar_feed(OFERTA)
    assert res["sucesso"] is True
    # 1 container (/media) + 1 publish (/media_publish)
    assert chamadas[0]["url"].endswith("/media")
    assert chamadas[0]["data"]["image_url"] == OFERTA["imagem_url"]
    assert "Fone Bluetooth Pro" in chamadas[0]["data"]["caption"]
    assert chamadas[1]["url"].endswith("/media_publish")
    assert chamadas[1]["data"]["creation_id"] == "CID1"
    # token vem do .env (config), nunca hardcode
    assert chamadas[0]["data"]["access_token"] == "TOKEN_X"


def test_enviar_delega_para_feed(ig):
    canal, chamadas = ig
    res = canal.enviar(OFERTA)
    assert res["sucesso"] is True
    assert any(c["url"].endswith("/media_publish") for c in chamadas)


def test_publicar_story_anexa_link_redirect(ig):
    canal, chamadas = ig
    res = canal.publicar_story(OFERTA)
    assert res["sucesso"] is True
    container = chamadas[0]["data"]
    assert container["media_type"] == "STORIES"
    # link sticker -> redirecionador próprio /r/{id}?c=instagram (TASK-15)
    assert "/r/77?c=instagram" in container["link"]
    assert res["link_afiliado"] == container["link"]


def test_publicar_carrossel_filhos_e_pai(ig):
    canal, chamadas = ig
    ofertas = [
        {**OFERTA, "titulo": "Produto 1", "imagem_url": "https://img/1.jpg"},
        {**OFERTA, "titulo": "Produto 2", "imagem_url": "https://img/2.jpg"},
        {**OFERTA, "titulo": "Produto 3", "imagem_url": "https://img/3.jpg"},
    ]
    res = canal.publicar_carrossel(ofertas)
    assert res["sucesso"] is True
    assert res["itens"] == 3

    filhos = [c for c in chamadas if c["url"].endswith("/media") and c["data"].get("is_carousel_item")]
    assert len(filhos) == 3
    pai = [c for c in chamadas if c["data"].get("media_type") == "CAROUSEL"]
    assert len(pai) == 1
    assert pai[0]["data"]["children"] == "CID1,CID2,CID3"
    assert "TOP" in pai[0]["data"]["caption"].upper()


def test_carrossel_exige_2_ofertas_com_imagem(ig):
    canal, _ = ig
    res = canal.publicar_carrossel([{**OFERTA, "imagem_url": None}])
    assert res["sucesso"] is False
    assert "2 ofertas" in res["resposta"]


def test_carrossel_respeita_limite_top5(ig):
    canal, chamadas = ig
    ofertas = [{**OFERTA, "titulo": f"P{i}", "imagem_url": f"https://img/{i}.jpg"} for i in range(8)]
    res = canal.publicar_carrossel(ofertas)
    assert res["itens"] == InstagramChannel.MAX_CARROSSEL  # 5


def test_nao_configurado_retorna_erro(monkeypatch):
    monkeypatch.setattr(config, "INSTAGRAM_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "INSTAGRAM_USER_ID", "")
    res = InstagramChannel().publicar_feed(OFERTA)
    assert res["sucesso"] is False
    assert "não configurado" in res["resposta"]


def test_feed_sem_imagem_retorna_erro(ig):
    canal, _ = ig
    res = canal.publicar_feed({**OFERTA, "imagem_url": None})
    assert res["sucesso"] is False
    assert "imagem" in res["resposta"].lower()


def test_caption_carrossel_lista_ofertas():
    cap = caption_carrossel([
        {"titulo": "Whey", "preco": 99.0, "desconto_pct": 30},
        {"titulo": "Creatina", "preco": 49.0, "desconto_pct": 0},
    ])
    assert "1. Whey" in cap
    assert "2. Creatina" in cap
    assert "30% OFF" in cap
    assert "#promoachados" in cap


def test_caption_feed_tem_cta_e_hashtags():
    cap = caption_feed(OFERTA)
    assert "Fone Bluetooth Pro" in cap
    assert "50% OFF" in cap
    assert "#promo" in cap.lower()
