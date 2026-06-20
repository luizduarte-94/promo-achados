# -*- coding: utf-8 -*-
"""Testes da camada ORM Postgres (TASK-02).

Rodam em SQLite in-memory (tipos genéricos do SQLAlchemy) — não exigem um
Postgres no ar. Validam que o schema existe e funciona ponta a ponta.
"""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.models import (
    Base,
    Oferta,
    Departamento,
    criar_engine,
    init_db_pg,
)

TABELAS_ESPERADAS = {
    "ofertas",
    "postagens",
    "configuracoes",
    "historico_buscas",
    "departamentos",
    "historico_precos",
    "produtos_recorrentes",
}


def test_metadata_tem_as_7_tabelas():
    assert set(Base.metadata.tables) == TABELAS_ESPERADAS


def test_create_all_em_sqlite_memoria():
    engine = create_engine("sqlite://")
    init_db_pg(engine)
    assert set(inspect(engine).get_table_names()) == TABELAS_ESPERADAS


def test_oferta_tem_colunas_chave():
    cols = {c.name for c in Base.metadata.tables["ofertas"].columns}
    assert {"id", "titulo", "preco", "departamento_id", "produto_id",
            "dados_extra", "frete_gratis", "criado_em"} <= cols


def test_tipagem_correta():
    of = Base.metadata.tables["ofertas"]
    assert of.c.frete_gratis.type.__class__.__name__ == "Boolean"
    assert of.c.criado_em.type.__class__.__name__ == "DateTime"
    assert of.c.preco.type.__class__.__name__ == "Float"


def test_engine_factory_sqlite_sem_pool_args():
    # SQLite não aceita pool_size; a fábrica deve devolver engine sem erro.
    assert criar_engine("sqlite://") is not None


def test_round_trip_insert_com_fk():
    engine = create_engine("sqlite://")
    init_db_pg(engine)
    with Session(engine) as s:
        dep = Departamento(nome="Fitness & Academia", emoji="💪")
        s.add(dep)
        s.commit()
        ofe = Oferta(titulo="Creatina 300g", preco=49.9, departamento_id=dep.id,
                     frete_gratis=True, dados_extra={"cupom": "X10"})
        s.add(ofe)
        s.commit()
        lido = s.get(Oferta, ofe.id)
        assert lido.preco == 49.9
        assert lido.frete_gratis is True
        assert lido.dados_extra == {"cupom": "X10"}
        assert lido.departamento_id == dep.id
