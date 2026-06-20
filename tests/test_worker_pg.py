# -*- coding: utf-8 -*-
"""Teste de integração: um job do agendador gravando no Postgres REAL (TASK-06).

Pula automaticamente se não houver Postgres disponível (mantém a suíte verde
offline). O resto dos testes continua em SQLite via conftest.
"""

import pytest

from backend.config import config
from backend.models import criar_engine


def _pg_disponivel() -> bool:
    try:
        with criar_engine(config.DATABASE_URL).connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pg_disponivel(), reason="Postgres indisponível")


@pytest.fixture
def db_postgres():
    """Reaponta a camada de dados para o Postgres real e restaura no fim."""
    from backend import database as db

    db.reconfigurar(config.DATABASE_URL)
    db.init_db()
    yield db
    db.reconfigurar(f"sqlite:///{config.DB_PATH}")  # volta para o SQLite de teste


def test_job_busca_automatica_grava_no_postgres(db_postgres, monkeypatch):
    from backend import scheduler

    db = db_postgres
    link = "https://x/MLB-6020304-workerpg"
    fake = [{
        "titulo": "Produto Worker PG",
        "preco": 42.0,
        "preco_original": None,
        "loja": "Mercado Livre",
        "link_original": link,
    }]

    # Mocka o scraper (sem rede) e desliga espelho/auto-post p/ isolar o job.
    monkeypatch.setattr(scheduler.ml_scraper, "buscar_todas_palavras", lambda: fake)
    monkeypatch.setattr(config, "ESPELHO_ENABLED", False)
    monkeypatch.setattr(config, "AUTO_POST_ENABLED", False)

    # roda o JOB real do agendador -> deve gravar no Postgres via coletar_e_salvar
    scheduler.tarefa_busca_automatica()
    try:
        assert db.oferta_existe(link) is True
    finally:
        for o in db.listar_ofertas(limite=1000):
            if o.get("link_original") == link:
                db.deletar_oferta(o["id"])
