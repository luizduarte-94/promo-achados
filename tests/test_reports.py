# -*- coding: utf-8 -*-
"""Testes do motor de relatórios e da rota /analytics/summary (TASK-16).

Roda em SQLite (conftest). Limpa click_events no início p/ tornar os agregados
GLOBAIS determinísticos. Valida cliques por canal, top ofertas, faturamento
estimado (só onde há commission_rate), EPC = faturamento/cliques e CTR honesto
(indisponível, sem impressões instrumentadas).
"""

import pytest
from sqlalchemy import delete

from backend import database as db
from backend.config import config
from backend.models import ClickEvent, criar_session_factory
from backend.analytics import registrar_clique
from backend.analytics.reports import gerar_resumo


def _purge_all_clicks():
    Session = criar_session_factory(db.get_engine())
    with Session() as s:
        s.execute(delete(ClickEvent))
        s.commit()


@pytest.fixture
def cenario():
    """2 ofertas (Shopee c/ comissão 10%, ML sem comissão) + cliques conhecidos."""
    _purge_all_clicks()
    shopee = db.criar_oferta({
        "titulo": "Whey Shopee", "preco": 100.0, "loja": "Shopee",
        "link_original": "https://shopee.com.br/whey-i.1.2",
        "dados_extra": {"commission_rate": "0.10"},
    })
    ml = db.criar_oferta({
        "titulo": "Notebook ML", "preco": 2000.0, "loja": "Mercado Livre",
        "link_original": "https://www.mercadolivre.com.br/MLB-999",
    })
    # Shopee: telegram x3, whatsapp x1 | ML: telegram x2
    for _ in range(3):
        registrar_clique(shopee, "telegram", "1.1.1.1")
    registrar_clique(shopee, "whatsapp", "2.2.2.2")
    for _ in range(2):
        registrar_clique(ml, "telegram", "3.3.3.3")
    yield {"shopee": shopee, "ml": ml}
    _purge_all_clicks()
    db.deletar_oferta(shopee)
    db.deletar_oferta(ml)


def test_cliques_por_canal_e_totais(cenario):
    r = gerar_resumo()
    assert r["cliques_por_canal"] == {"telegram": 5, "whatsapp": 1}
    assert r["totais"]["cliques"] == 6
    assert r["totais"]["ofertas_com_clique"] == 2
    assert r["totais"]["canais"] == 2


def test_top_ofertas_ordenado_por_cliques(cenario):
    r = gerar_resumo()
    top = r["top_ofertas"]
    assert top[0]["oferta_id"] == cenario["shopee"]
    assert top[0]["cliques"] == 4          # 3 telegram + 1 whatsapp
    assert top[0]["titulo"] == "Whey Shopee"
    assert top[1]["oferta_id"] == cenario["ml"]
    assert top[1]["cliques"] == 2


def test_faturamento_estimado_so_com_comissao(cenario):
    r = gerar_resumo()
    fat = r["faturamento_estimado_por_canal"]
    # telegram: 3 cliques Shopee * (100 * 0.10) = 30.0 ; ML sem comissão -> 0
    assert fat["telegram"]["comissao_estimada"] == 30.0
    assert fat["telegram"]["cliques"] == 5
    assert fat["telegram"]["cliques_com_comissao"] == 3
    assert fat["telegram"]["cobertura_comissao_pct"] == 60.0
    # whatsapp: 1 clique Shopee * 10 = 10.0 ; cobertura 100%
    assert fat["whatsapp"]["comissao_estimada"] == 10.0
    assert fat["whatsapp"]["cobertura_comissao_pct"] == 100.0


def test_epc_por_canal(cenario):
    r = gerar_resumo()
    assert r["epc_por_canal"]["telegram"] == round(30.0 / 5, 4)   # 6.0
    assert r["epc_por_canal"]["whatsapp"] == round(10.0 / 1, 4)   # 10.0


def test_ctr_indisponivel_sem_impressoes(cenario):
    r = gerar_resumo()
    assert r["ctr"]["disponivel"] is False
    assert r["ctr"]["valor"] is None
    assert "impress" in r["ctr"]["motivo"].lower()


def test_oferta_removida_aparece_marcada(cenario):
    db.deletar_oferta(cenario["ml"])       # cliques permanecem (sem FK/cascade)
    r = gerar_resumo()
    ml = [o for o in r["top_ofertas"] if o["oferta_id"] == cenario["ml"]][0]
    assert ml["removida"] is True
    assert ml["titulo"] is None
    assert ml["cliques"] == 2              # ainda contabilizado


def test_resumo_vazio_nao_quebra():
    _purge_all_clicks()
    r = gerar_resumo()
    assert r["totais"]["cliques"] == 0
    assert r["cliques_por_canal"] == {}
    assert r["top_ofertas"] == []
    assert r["epc_por_canal"] == {}


def test_limite_top_ofertas(cenario):
    r = gerar_resumo(limite=1)
    assert len(r["top_ofertas"]) == 1


# --- Rota /analytics/summary -------------------------------------------------

def _client():
    from fastapi.testclient import TestClient
    import main
    db.init_db()
    return TestClient(main.app)


def test_rota_summary_200_e_estrutura(cenario):
    with _client() as client:
        resp = client.get("/analytics/summary")
    assert resp.status_code == 200
    j = resp.json()
    for chave in ("cliques_por_canal", "top_ofertas", "faturamento_estimado_por_canal",
                  "epc_por_canal", "ctr", "metodologia", "totais"):
        assert chave in j
    assert j["ctr"]["disponivel"] is False


def test_rota_summary_protegida_por_auth(cenario, monkeypatch):
    monkeypatch.setattr(config, "PANEL_PASSWORD", "segredo")
    with _client() as client:
        sem = client.get("/analytics/summary")
        com = client.get("/analytics/summary", auth=("admin", "segredo"))
    assert sem.status_code == 401          # painel/admin exige auth
    assert com.status_code == 200
