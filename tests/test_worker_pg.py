# -*- coding: utf-8 -*-
"""Teste de integração: um job do agendador gravando no Postgres (TASK-06).

SEGURANÇA: roda SOMENTE contra um banco DESCARTÁVEL, indicado explicitamente em
`PROMO_TEST_PG_URL` (ex.: postgres de CI/teste). Sem essa variável o teste é
PULADO — assim `pytest` nunca escreve no banco real configurado em DATABASE_URL.
"""

import os

import pytest

from backend.config import config
from backend.models import criar_engine

_PG_TEST_URL = os.getenv("PROMO_TEST_PG_URL", "").strip()


def _pg_disponivel() -> bool:
    if not _PG_TEST_URL:
        return False
    try:
        with criar_engine(_PG_TEST_URL).connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_disponivel(),
    reason="Defina PROMO_TEST_PG_URL apontando p/ um Postgres DESCARTÁVEL para rodar (evita tocar no banco real).",
)


@pytest.fixture
def db_postgres():
    """Reaponta a camada de dados para o Postgres DESCARTÁVEL e restaura no fim."""
    from backend import database as db

    anterior = str(db.get_engine().url)   # SQLite de teste configurado no conftest
    db.reconfigurar(_PG_TEST_URL)
    db.init_db()
    yield db
    db.reconfigurar(anterior)             # restaura exatamente o que estava antes


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
