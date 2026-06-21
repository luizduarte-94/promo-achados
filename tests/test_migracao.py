# -*- coding: utf-8 -*-
"""Testes da migração SQLite -> destino (TASK-03).

Usam SQLite como origem E destino (tipos genéricos do SQLAlchemy), então
rodam sem precisar de um Postgres no ar. Validam preservação de ID/FK,
conversão de tipos e idempotência (rerun não duplica).
"""

import datetime as dt
import sqlite3

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.models import Configuracao, Departamento, Oferta, Postagem
from backend.scripts.migrate_sqlite_to_pg import migrar


def _origem(tmp_path):
    """Cria um SQLite legado com schema parcial e algumas linhas."""
    caminho = tmp_path / "legacy.db"
    con = sqlite3.connect(caminho)
    con.executescript(
        """
        CREATE TABLE departamentos (id INTEGER PRIMARY KEY, nome TEXT, emoji TEXT,
                                    ativo INTEGER, criado_em TEXT);
        CREATE TABLE ofertas (id INTEGER PRIMARY KEY, titulo TEXT, preco REAL,
                              frete_gratis INTEGER, dados_extra TEXT,
                              departamento_id INTEGER, criado_em TEXT);
        CREATE TABLE postagens (id INTEGER PRIMARY KEY, oferta_id INTEGER, canal TEXT,
                                sucesso INTEGER, postado_em TEXT);
        CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT);
        """
    )
    con.execute("INSERT INTO departamentos VALUES (1,'Fitness','💪',1,'2026-06-01 10:00:00')")
    con.execute(
        "INSERT INTO ofertas VALUES (7,'Creatina 300g',49.9,1,'{\"cupom\":\"X10\"}',1,'2026-06-02 11:00:00')"
    )
    con.execute("INSERT INTO postagens VALUES (3,7,'telegram',1,'2026-06-02 12:00:00')")
    con.execute("INSERT INTO configuracoes VALUES ('ml_token','abc')")
    con.commit()
    con.close()
    return caminho


def _destino(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'target.db'}")


def test_migracao_simples_preserva_id_fk_e_tipos(tmp_path):
    contagem = migrar(_origem(tmp_path), _destino_engine := _destino(tmp_path))

    assert contagem["departamentos"] == 1
    assert contagem["ofertas"] == 1
    assert contagem["postagens"] == 1
    assert contagem["configuracoes"] == 1

    with Session(_destino_engine) as s:
        of = s.get(Oferta, 7)                 # ID preservado
        assert of is not None
        assert of.titulo == "Creatina 300g"
        assert of.preco == 49.9
        assert of.frete_gratis is True        # INTEGER 1 -> bool
        assert of.dados_extra == {"cupom": "X10"}  # TEXT JSON -> dict
        assert of.departamento_id == 1        # FK preservada
        assert isinstance(of.criado_em, dt.datetime)  # TEXT -> datetime
        assert s.get(Postagem, 3).oferta_id == 7
        assert s.get(Configuracao, "ml_token").valor == "abc"


def test_rerun_idempotente_nao_duplica(tmp_path):
    origem = _origem(tmp_path)
    destino = _destino(tmp_path)

    migrar(origem, destino)
    migrar(origem, destino)  # segunda passada

    with Session(destino) as s:
        assert s.scalar(select(func.count()).select_from(Oferta)) == 1
        assert s.scalar(select(func.count()).select_from(Departamento)) == 1
        assert s.scalar(select(func.count()).select_from(Postagem)) == 1
        assert s.scalar(select(func.count()).select_from(Configuracao)) == 1


def test_origem_sem_tabela_nao_quebra(tmp_path):
    # origem vazia (só um arquivo sqlite sem as tabelas) -> conta 0, sem erro
    vazio = tmp_path / "vazio.db"
    sqlite3.connect(vazio).close()
    contagem = migrar(vazio, _destino(tmp_path))
    assert all(v == 0 for v in contagem.values())
