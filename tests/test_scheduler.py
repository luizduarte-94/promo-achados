# -*- coding: utf-8 -*-
"""Testes dos jobs do scheduler na nova arquitetura (TASK-07).

Rodam em SQLite (conftest), com scraper/canal mockados (sem rede). Validam que
os jobs gravam/publicam via a camada ORM (database.py), coerentes com o worker.
"""

from backend import database as db, precos, scheduler
from backend.config import config


def test_job_busca_automatica_grava_via_orm(monkeypatch):
    link = "https://x/MLB-5050501-job"
    fake = [{
        "titulo": "Whey Job 1kg",
        "preco": 120.0,
        "preco_original": None,
        "loja": "Mercado Livre",
        "link_original": link,
    }]
    monkeypatch.setattr(scheduler.ml_scraper, "buscar_todas_palavras", lambda: fake)
    monkeypatch.setattr(config, "ESPELHO_ENABLED", False)
    monkeypatch.setattr(config, "AUTO_POST_ENABLED", False)

    scheduler.tarefa_busca_automatica()
    try:
        assert db.oferta_existe(link) is True            # gravou via coletar_e_salvar (ORM)
    finally:
        for o in db.listar_ofertas(limite=1000):
            if o.get("link_original") == link:
                db.deletar_oferta(o["id"])


def test_auto_postar_publica_e_marca_postada(monkeypatch):
    oid = db.criar_oferta({
        "titulo": "Creatina Auto-Post",
        "preco": 49.9,
        "preco_original": 99.9,
        "desconto_pct": 50,
        "loja": "Mercado Livre",
        "link_original": "https://x/MLB-6060601-auto",
        "link_afiliado": "https://meli.la/a",
        "frete_gratis": True,
    })
    try:
        monkeypatch.setattr(config, "AUTO_POST_ENABLED", True)
        monkeypatch.setattr(config, "AUTO_POST_SCORE_MINIMO", 0)
        monkeypatch.setattr(scheduler.telegram, "esta_configurado", lambda: True)
        monkeypatch.setattr(precos, "revalidar_preco", lambda o: {"status": "ok"})

        enviadas = []

        def _fake_enviar(oferta):
            enviadas.append(oferta["id"])
            return {"sucesso": True, "resposta": "ok"}

        monkeypatch.setattr(scheduler.telegram, "enviar", _fake_enviar)

        scheduler.auto_postar()

        assert oid in enviadas                           # canal foi acionado
        assert db.obter_oferta(oid)["status"] == "postada"   # status via ORM
    finally:
        db.deletar_oferta(oid)
