# -*- coding: utf-8 -*-
"""Testes de Analytics: tabela click_events, serviço de tracking e rota /r/.

Cobre TASK-13 (modelo/migração), TASK-14 (tracking + redirect 302 com persistência
em background) e o emissor montar_link_redirect (TASK-15). Roda em SQLite (conftest)
e usa o TestClient do FastAPI para a rota — sem rede externa.
"""

from sqlalchemy import delete, select

from backend import database as db
from backend.config import config
from backend.models import Base, ClickEvent, criar_session_factory
from backend.analytics import (
    hash_ip,
    montar_link_redirect,
    registrar_clique,
    resolver_destino,
)


def _contar_cliques(oferta_id: int) -> list[ClickEvent]:
    Session = criar_session_factory(db.get_engine())
    with Session() as s:
        return list(s.scalars(select(ClickEvent).where(ClickEvent.oferta_id == oferta_id)))


def _limpar_cliques(oferta_id: int) -> None:
    """Remove cliques do oferta_id (click_events não tem cascade; ids são reusados)."""
    Session = criar_session_factory(db.get_engine())
    with Session() as s:
        s.execute(delete(ClickEvent).where(ClickEvent.oferta_id == oferta_id))
        s.commit()


# --- TASK-13: modelo/migração -------------------------------------------------

def test_click_events_no_schema():
    assert "click_events" in Base.metadata.tables
    cols = {c.name for c in Base.metadata.tables["click_events"].columns}
    assert {"id", "oferta_id", "canal", "ip_hash", "created_at"} <= cols


# --- montar_link_redirect (emissor, TASK-15) ---------------------------------

def test_montar_link_redirect(monkeypatch):
    monkeypatch.setattr(config, "REDIRECT_BASE_URL", "https://api.promoachados.com")
    assert montar_link_redirect(7, "telegram") == "https://api.promoachados.com/r/7?c=telegram"


# --- hash_ip ------------------------------------------------------------------

def test_hash_ip_estavel_e_anonimo():
    h = hash_ip("1.2.3.4")
    assert h and len(h) == 64 and "1.2.3.4" not in h
    assert hash_ip("1.2.3.4") == h          # estável (dedup)
    assert hash_ip("1.2.3.5") != h          # IPs diferentes -> hashes diferentes
    assert hash_ip(None) is None


# --- resolver_destino ---------------------------------------------------------

def test_resolver_destino_usa_monetizacao(monkeypatch):
    monkeypatch.setattr(config, "AFILIADO_ENCURTAR_SHOPEE", False)
    oferta = {
        "link_afiliado": "https://shopee.com.br/x-i.1.2",
        "produto_id": "shopee.1.2",
    }
    destino = resolver_destino(oferta, "telegram")
    assert "utm_source=telegram" in destino
    assert "sub_id=telegram_shopee12" in destino


def test_resolver_destino_vazio_sem_link():
    assert resolver_destino({"titulo": "x"}, "telegram") == ""


def test_resolver_destino_ml_preserva_meli_la_sem_query_extra():
    oferta = {
        "loja": "Mercado Livre",
        "link_afiliado": "https://meli.la/abc",
        "link_original": "https://www.mercadolivre.com.br/p/MLB-1",
    }
    assert resolver_destino(oferta, "telegram") == "https://meli.la/abc"


# --- registrar_clique (persistência) -----------------------------------------

def test_registrar_clique_persiste():
    oid = db.criar_oferta({"titulo": "Click Persist", "preco": 10.0,
                           "loja": "Shopee", "link_original": "https://shopee.com.br/y-i.9.9"})
    _limpar_cliques(oid)
    try:
        registrar_clique(oid, "telegram", "8.8.8.8")
        eventos = _contar_cliques(oid)
        assert len(eventos) == 1
        assert eventos[0].canal == "telegram"
        assert eventos[0].ip_hash == hash_ip("8.8.8.8")
    finally:
        db.deletar_oferta(oid)


# --- Rota GET /r/{oferta_id} (TASK-14) ---------------------------------------

def _client():
    from fastapi.testclient import TestClient
    import main
    # TestClient não dispara o lifespan por padrão em chamadas simples; garantimos
    # o schema no banco de teste (conftest já chamou init_db, mas reforçamos).
    db.init_db()
    return TestClient(main.app)


def test_redirect_302_e_registra_clique():
    oid = db.criar_oferta({"titulo": "Redirect OK", "preco": 20.0, "loja": "Shopee",
                           "link_original": "https://shopee.com.br/z-i.3.4",
                           "link_afiliado": "https://shopee.com.br/z-i.3.4?utm_source=site"})
    _limpar_cliques(oid)
    config_backup = config.AFILIADO_ENCURTAR_SHOPEE
    config.AFILIADO_ENCURTAR_SHOPEE = False
    try:
        with _client() as client:
            resp = client.get(f"/r/{oid}?c=telegram", follow_redirects=False)
        assert resp.status_code == 302
        assert "utm_source=telegram" in resp.headers["location"]
        # background task persistiu o clique
        eventos = _contar_cliques(oid)
        assert len(eventos) == 1 and eventos[0].canal == "telegram"
    finally:
        config.AFILIADO_ENCURTAR_SHOPEE = config_backup
        db.deletar_oferta(oid)


def test_redirect_canal_padrao_site():
    oid = db.criar_oferta({"titulo": "Redirect Default", "preco": 20.0, "loja": "Shopee",
                           "link_original": "https://shopee.com.br/w-i.5.6"})
    _limpar_cliques(oid)
    try:
        with _client() as client:
            resp = client.get(f"/r/{oid}", follow_redirects=False)
        assert resp.status_code == 302
        eventos = _contar_cliques(oid)
        assert eventos and eventos[0].canal == "site"   # default ?c -> site
    finally:
        db.deletar_oferta(oid)


def test_redirect_404_oferta_inexistente():
    with _client() as client:
        resp = client.get("/r/99999999?c=telegram", follow_redirects=False)
    assert resp.status_code == 404


def test_redirect_e_publico_mesmo_com_painel_protegido(monkeypatch):
    """/r/ deve ignorar o Basic Auth do painel (clique do usuário final)."""
    oid = db.criar_oferta({"titulo": "Redirect Publico", "preco": 20.0, "loja": "Shopee",
                           "link_original": "https://shopee.com.br/p-i.7.8"})
    try:
        monkeypatch.setattr(config, "PANEL_PASSWORD", "segredo")
        with _client() as client:
            resp = client.get(f"/r/{oid}?c=whatsapp", follow_redirects=False)
        assert resp.status_code == 302   # não 401
    finally:
        db.deletar_oferta(oid)
