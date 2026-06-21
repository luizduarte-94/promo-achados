# -*- coding: utf-8 -*-
"""Configuração dos testes: banco SQLite temporário e isolado.

Usa db.reconfigurar() (seam da TASK-06) para apontar a camada de dados a um
SQLite temporário ÚNICO por sessão — isolando os testes do banco real e do
Postgres, sem depender de config.DB_PATH/SQLITE_PATH. Mantém a suíte offline.
"""

import os
import pathlib
import shutil
import tempfile

os.environ.setdefault("USE_SQLITE", "true")

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _banco_de_teste():
    """Cria um SQLite temporário (schema ORM) p/ a sessão e remove no fim."""
    from backend import database as db

    tmpdir = tempfile.mkdtemp(prefix="promo_test_")
    caminho = pathlib.Path(tmpdir) / "test.db"
    db.reconfigurar(f"sqlite:///{caminho}")
    db.init_db()
    yield
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except OSError:
        pass
