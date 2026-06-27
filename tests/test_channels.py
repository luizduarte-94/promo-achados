# -*- coding: utf-8 -*-
"""Testes dos canais na nova arquitetura (TASK-07).

Os canais recebem um dict `oferta` e publicam — não acessam banco. A persistência
do estado (status 'postada') é feita via db.registrar_postagem (ORM). Aqui
validamos a montagem das mensagens e o fluxo de publicação -> ORM.
"""

from backend import database as db
from backend.config import config
from backend.channels.instagram import InstagramChannel
from backend.channels.telegram import TelegramChannel
from backend.channels import telegram as tg_mod, whatsapp as wa_mod, instagram as ig_mod

OFERTA = {
    "titulo": "Fone <b>X</b> Bluetooth",
    "preco": 99.9,
    "preco_original": 199.9,
    "desconto_pct": 50,
    "loja": "Mercado Livre",
    "frete_gratis": True,
    "dados_extra": {"cupom": "C10"},
}


def test_telegram_montar_post_escapa_html(monkeypatch):
    monkeypatch.setattr(config, "USAR_IA_COPYWRITER", False)   # template, sem IA
    texto = TelegramChannel()._montar_post(OFERTA)
    assert "Fone &lt;b&gt;X&lt;/b&gt; Bluetooth" in texto      # título escapado
    assert "<b>" in texto                                       # HTML do template
    assert "50% OFF" in texto


def test_telegram_inclui_parcelamento_confirmado(monkeypatch):
    monkeypatch.setattr(config, "USAR_IA_COPYWRITER", False)
    oferta = {**OFERTA, "dados_extra": {"parcelamento_destaque": "Pague em até 24x sem juros"}}
    texto = TelegramChannel()._montar_post(oferta)
    assert "Pague em até 24x sem juros" in texto


def test_telegram_omite_parcelamento_ausente(monkeypatch):
    monkeypatch.setattr(config, "USAR_IA_COPYWRITER", False)
    texto = TelegramChannel()._montar_post(OFERTA)
    assert "24x" not in texto


def test_telegram_reply_markup_link():
    rm = TelegramChannel()._get_reply_markup("https://meli.la/abc")
    assert "meli.la/abc" in rm and "COMPRAR" in rm
    assert TelegramChannel()._get_reply_markup("") is None


def test_instagram_caption_tem_titulo_e_hashtags():
    cap = InstagramChannel()._montar_caption(OFERTA)
    assert "Fone" in cap
    assert "#promo" in cap.lower()


def test_canais_nao_acessam_banco():
    """Contrato: canais não importam database/sqlite (persistência fica fora)."""
    fontes = "".join(
        open(m.__file__, encoding="utf-8").read()
        for m in (tg_mod, wa_mod, ig_mod)
    )
    assert "database" not in fontes
    assert "sqlite3" not in fontes


def test_publicacao_marca_postada_via_orm(monkeypatch):
    """Canal.enviar (mock) + registrar_postagem -> status 'postada' no ORM."""
    oid = db.criar_oferta({
        "titulo": "Publicação Teste",
        "preco": 10.0,
        "loja": "Mercado Livre",
        "link_original": "https://x/MLB-4040401-pub",
    })
    try:
        canal = TelegramChannel()
        monkeypatch.setattr(canal, "enviar", lambda oferta: {"sucesso": True, "resposta": "ok"})
        resultado = canal.enviar(db.obter_oferta(oid))
        db.registrar_postagem(oid, "telegram", resultado["sucesso"], resultado["resposta"])
        assert db.obter_oferta(oid)["status"] == "postada"
    finally:
        db.deletar_oferta(oid)
