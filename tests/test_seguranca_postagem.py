# -*- coding: utf-8 -*-
"""Camada de segurança das postagens — Fase 1 (canal de teste + guardas).

Banco SQLite temporário (conftest) e Telegram TOTALMENTE mockado: nenhum envio
real. Cobre o canal de teste (nunca usa o chat oficial), a instrução clara quando
não configurado, e o endpoint /testar via TestClient.
"""

from backend import database as db
from backend.config import config
from backend.channels import telegram as tg_mod
from backend.channels.telegram import TelegramChannel


class _FakeResp:
    ok = True

    @staticmethod
    def json():
        return {"ok": True, "result": {"message_id": 123, "chat": {"id": 999}}}


def _mock_post(monkeypatch):
    """Captura as chamadas a requests.post (sem rede). Retorna a lista de calls."""
    chamadas = []

    def fake_post(url, data=None, files=None, timeout=None, **kw):
        chamadas.append({"url": url, "data": data or {}})
        return _FakeResp()

    monkeypatch.setattr(tg_mod.requests, "post", fake_post)
    monkeypatch.setattr(tg_mod.requests, "get", lambda *a, **k: type("R", (), {"ok": False, "status_code": 404})())
    return chamadas


OFERTA = {
    "titulo": "Whey Teste", "preco": 99.9, "loja": "Mercado Livre",
    "link_afiliado": "https://meli.la/abc", "link_original": "https://x/MLB-1",
}


def test_enviar_teste_sem_chat_configurado_nao_envia(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(config, "TELEGRAM_TEST_CHAT_ID", "")
    chamadas = _mock_post(monkeypatch)
    r = TelegramChannel().enviar_teste(OFERTA)
    assert r["sucesso"] is False
    assert "TELEGRAM_TEST_CHAT_ID" in r["resposta"]
    assert chamadas == []          # nada foi enviado


def test_enviar_teste_usa_chat_de_teste_nunca_o_oficial(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "@canal_oficial")
    monkeypatch.setattr(config, "TELEGRAM_TEST_CHAT_ID", "-100777")
    chamadas = _mock_post(monkeypatch)
    r = TelegramChannel().enviar_teste(OFERTA)
    assert r["sucesso"] is True
    assert chamadas, "deveria ter enviado ao canal de teste"
    enviados = [str(c["data"].get("chat_id")) for c in chamadas]
    assert "-100777" in enviados                 # foi pro canal de TESTE
    assert "@canal_oficial" not in enviados       # NUNCA o oficial


def test_enviar_oficial_usa_chat_oficial(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "@canal_oficial")
    chamadas = _mock_post(monkeypatch)
    TelegramChannel().enviar({**OFERTA})
    assert any(str(c["data"].get("chat_id")) == "@canal_oficial" for c in chamadas)


def test_config_telegram_test_ok(monkeypatch):
    # telegram_test_ok é classmethod (lê atributos de classe) -> patch na classe.
    cls = type(config)
    monkeypatch.setattr(cls, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(cls, "TELEGRAM_TEST_CHAT_ID", "")
    assert config.telegram_test_ok() is False
    monkeypatch.setattr(cls, "TELEGRAM_TEST_CHAT_ID", "-100777")
    assert config.telegram_test_ok() is True


# --- Endpoint /api/ofertas/{id}/testar -------------------------------------

def _client():
    from fastapi.testclient import TestClient
    import main
    db.init_db()
    return TestClient(main.app)


def test_endpoint_testar_sem_chat_responde_400_sem_enviar(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(config, "TELEGRAM_TEST_CHAT_ID", "")
    chamadas = _mock_post(monkeypatch)
    oid = db.criar_oferta({"titulo": "X", "preco": 10.0, "loja": "Shopee",
                           "link_original": "https://shopee.com.br/x-i.1.2"})
    try:
        with _client() as client:
            resp = client.post(f"/api/ofertas/{oid}/testar")
        assert resp.status_code == 400
        assert "TELEGRAM_TEST_CHAT_ID" in resp.json()["detail"]
        assert chamadas == []
    finally:
        db.deletar_oferta(oid)


def test_endpoint_testar_envia_ao_canal_de_teste(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "@oficial")
    monkeypatch.setattr(config, "TELEGRAM_TEST_CHAT_ID", "-100777")
    chamadas = _mock_post(monkeypatch)
    oid = db.criar_oferta({"titulo": "Y", "preco": 20.0, "loja": "Shopee",
                           "link_original": "https://shopee.com.br/y-i.3.4"})
    try:
        with _client() as client:
            resp = client.post(f"/api/ofertas/{oid}/testar")
        assert resp.status_code == 200
        assert resp.json()["resultado"]["sucesso"] is True
        enviados = [str(c["data"].get("chat_id")) for c in chamadas]
        assert "-100777" in enviados and "@oficial" not in enviados
        # endpoint de teste NÃO registra postagem oficial
        assert db.listar_postagens(limite=50) == [] or all(
            p.get("titulo") != "Y" for p in db.listar_postagens(limite=50))
    finally:
        db.deletar_oferta(oid)
