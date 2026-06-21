# -*- coding: utf-8 -*-
"""
Migração de dados SQLite -> PostgreSQL (TASK-03).

Lê o banco legado (promo_achados.db) e insere no destino (Postgres, via
backend/models.py), preservando IDs e integridade referencial.

Características:
- **Idempotente**: usa session.merge() (insere-ou-atualiza por PK). Rodar N
  vezes não duplica dados.
- **Preserva IDs**: o id do SQLite vira o id no destino; ao final, ajusta as
  sequences do Postgres para o MAX(id) (evita colisão em inserts futuros).
- **Integridade referencial**: tabelas migradas em ordem de dependência
  (departamentos -> ofertas -> postagens -> ...).
- **Não toca** no código de leitura/escrita principal (database.py). Só prepara
  a migração.

Uso:
    python -m backend.scripts.migrate_sqlite_to_pg
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.config import config
from backend.models import (
    Configuracao,
    Departamento,
    HistoricoBusca,
    HistoricoPreco,
    Oferta,
    Postagem,
    ProdutoRecorrente,
    criar_engine,
    criar_session_factory,
    init_db_pg,
)

# Ordem de migração respeitando as foreign keys (pai antes do filho).
TABELAS_ORDEM = [
    ("departamentos", Departamento),
    ("ofertas", Oferta),
    ("postagens", Postagem),
    ("configuracoes", Configuracao),
    ("historico_buscas", HistoricoBusca),
    ("historico_precos", HistoricoPreco),
    ("produtos_recorrentes", ProdutoRecorrente),
]


def _converter(coluna, valor):
    """Converte o valor do SQLite para o tipo do modelo (bool/datetime/json)."""
    if valor is None:
        return None
    tipo = coluna.type.__class__.__name__
    if tipo == "Boolean":
        return bool(valor)
    if tipo == "DateTime":
        if isinstance(valor, str):
            try:
                return dt.datetime.fromisoformat(valor)
            except ValueError:
                return None
        return valor
    if tipo == "JSON":
        if isinstance(valor, str):
            try:
                return json.loads(valor)
            except (ValueError, TypeError):
                return None
        return valor
    return valor


def _corrigir_sequences(engine: Engine) -> None:
    """Ajusta as sequences do Postgres para o MAX(id) (só no Postgres)."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for tabela, model in TABELAS_ORDEM:
            if "id" not in {c.name for c in model.__table__.columns}:
                continue  # ex.: configuracoes (PK = chave)
            conn.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{tabela}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {tabela}), 1))"
                )
            )


def migrar(origem: str | None = None, destino: Engine | None = None) -> dict[str, int]:
    """Migra todas as tabelas do SQLite de origem para o engine de destino.

    Args:
        origem: caminho do .db SQLite (default: config.DB_PATH).
        destino: Engine SQLAlchemy de destino (default: criar_engine() = Postgres).

    Returns:
        dict {tabela: linhas processadas}.
    """
    origem = str(origem or config.DB_PATH)
    destino = destino or criar_engine()
    init_db_pg(destino)  # garante o schema no destino (idempotente)

    src = sqlite3.connect(origem)
    src.row_factory = sqlite3.Row
    sessao_factory = criar_session_factory(destino)

    contagem: dict[str, int] = {}
    with sessao_factory() as sessao:
        for tabela, model in TABELAS_ORDEM:
            try:
                linhas = src.execute(f"SELECT * FROM {tabela}").fetchall()
            except sqlite3.OperationalError:
                contagem[tabela] = 0
                print(f"[MIGRA] {tabela}: tabela ausente na origem, pulando.")
                continue

            colunas = {c.name: c for c in model.__table__.columns}
            n = 0
            for linha in linhas:
                presentes = set(linha.keys())
                dados = {
                    nome: _converter(col, linha[nome])
                    for nome, col in colunas.items()
                    if nome in presentes
                }
                sessao.merge(model(**dados))  # insere-ou-atualiza por PK (idempotente)
                n += 1
            sessao.commit()
            contagem[tabela] = n
            print(f"[MIGRA] {tabela}: {n} linha(s) migrada(s).")

    src.close()
    _corrigir_sequences(destino)
    return contagem


def main() -> None:
    print(f"[MIGRA] Origem (SQLite): {config.DB_PATH}")
    print(f"[MIGRA] Destino: {config.DATABASE_URL}")
    contagem = migrar()
    total = sum(contagem.values())
    print(f"[MIGRA] Concluído. {total} linha(s) no total: {contagem}")


if __name__ == "__main__":
    main()
