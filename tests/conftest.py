# -*- coding: utf-8 -*-
"""Configuração dos testes: força SQLite num arquivo temporário e cria o schema.

Definido ANTES de qualquer import do backend para que backend.config leia as
variáveis. Mantém os testes offline (sem precisar de um Postgres no ar) e
isolados do banco real (promo_achados.db).
"""

import os
import pathlib
import tempfile

os.environ.setdefault("USE_SQLITE", "true")
os.environ.setdefault(
    "SQLITE_PATH", str(pathlib.Path(tempfile.gettempdir()) / "promo_achados_test.db")
)

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _preparar_banco_de_teste():
    """Cria um SQLite limpo (schema ORM) para a sessão de testes e remove no fim."""
    caminho = pathlib.Path(os.environ["SQLITE_PATH"])
    if caminho.exists():
        caminho.unlink()

    from backend import database as db

    db.init_db()
    yield
    try:
        caminho.unlink()
    except OSError:
        pass
