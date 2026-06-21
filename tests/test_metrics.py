# -*- coding: utf-8 -*-
"""Testes das métricas / logs estruturados dos jobs (TASK-08).

Rodam em SQLite (conftest), sem rede. Validam que os jobs emitem eventos
estruturados (JSON) com job_name, status, duration_ms, contadores, etc.
"""

import json
import logging

from backend import database as db, precos, scheduler
from backend.config import config


def test_log_emite_json_valido_com_campos():
    capturado = []
    h = logging.Handler()
    h.emit = lambda record: capturado.append(record.getMessage())
    scheduler.logger.addHandler(h)
    try:
        scheduler._log(job_name="x", status="ok", fonte="mercadolivre", offer_id=7)
        d = json.loads(capturado[-1])
        assert d["job_name"] == "x"
        assert d["status"] == "ok"
        assert d["fonte"] == "mercadolivre"
        assert d["offer_id"] == 7
        assert "ts" in d
    finally:
        scheduler.logger.removeHandler(h)


def test_busca_automatica_emite_metricas(monkeypatch):
    eventos = []
    monkeypatch.setattr(scheduler, "_log", lambda **k: eventos.append(k))
    link = "https://x/MLB-7070701-met"
    fake = [{"titulo": "Whey Metric 1kg", "preco": 120.0, "preco_original": None,
             "loja": "Mercado Livre", "link_original": link}]
    monkeypatch.setattr(scheduler.ml_scraper, "buscar_todas_palavras", lambda: fake)
    monkeypatch.setattr(config, "ESPELHO_ENABLED", False)
    monkeypatch.setattr(config, "AUTO_POST_ENABLED", False)

    try:
        scheduler.tarefa_busca_automatica()
    finally:
        for o in db.listar_ofertas(limite=1000):
            if o.get("link_original") == link:
                db.deletar_oferta(o["id"])

    scrape = [e for e in eventos if e.get("evento") == "scrape" and e.get("fonte") == "mercadolivre"]
    assert scrape and scrape[0]["status"] == "ok" and scrape[0]["capturadas"] == 1

    final = [e for e in eventos if e.get("job_name") == "busca_automatica" and "duration_ms" in e]
    assert final and final[-1]["status"] == "ok"
    assert isinstance(final[-1]["duration_ms"], float)
    assert final[-1]["capturadas"] == 1


def test_auto_post_emite_metricas(monkeypatch):
    eventos = []
    monkeypatch.setattr(scheduler, "_log", lambda **k: eventos.append(k))
    oid = db.criar_oferta({
        "titulo": "Creatina Metric", "preco": 49.9, "preco_original": 99.9, "desconto_pct": 50,
        "loja": "Mercado Livre", "link_original": "https://x/MLB-7070702-ap",
        "link_afiliado": "https://meli.la/a", "frete_gratis": True,
    })
    try:
        monkeypatch.setattr(config, "AUTO_POST_ENABLED", True)
        monkeypatch.setattr(config, "AUTO_POST_SCORE_MINIMO", 0)
        monkeypatch.setattr(scheduler.telegram, "esta_configurado", lambda: True)
        monkeypatch.setattr(precos, "revalidar_preco", lambda o: {"status": "ok"})
        monkeypatch.setattr(scheduler.telegram, "enviar", lambda o: {"sucesso": True, "resposta": "ok"})

        scheduler.auto_postar()

        pub = [e for e in eventos if e.get("evento") == "publicacao" and e.get("offer_id") == oid]
        assert pub and pub[0]["canal"] == "telegram" and pub[0]["status"] == "ok"
        final = [e for e in eventos if e.get("job_name") == "auto_post" and "duration_ms" in e]
        assert final and final[-1]["publicadas"] >= 1
    finally:
        db.deletar_oferta(oid)
