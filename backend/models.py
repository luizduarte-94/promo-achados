# -*- coding: utf-8 -*-
"""
Camada ORM (SQLAlchemy) — schema do PostgreSQL (TASK-02).

Espelha as tabelas do SQLite legado (backend/database.py), porém com tipagem
correta para Postgres (Boolean, DateTime, JSON). NÃO substitui o database.py
ainda — a "virada de chave" para o Postgres é a TASK-04. Por enquanto este
módulo só DEFINE o schema e sabe criá-lo (create_all) num engine com pool.

Tipos genéricos do SQLAlchemy: funcionam tanto no Postgres (produção) quanto
no SQLite (usado nos testes, sem precisar de um Postgres no ar).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.config import config


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos."""


class Departamento(Base):
    __tablename__ = "departamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    emoji: Mapped[str] = mapped_column(String(16), default="📦")
    palavras_chave: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Oferta(Base):
    __tablename__ = "ofertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(Text)
    preco: Mapped[float] = mapped_column(Float)
    preco_original: Mapped[float | None] = mapped_column(Float, nullable=True)
    desconto_pct: Mapped[float] = mapped_column(Float, default=0)
    loja: Mapped[str] = mapped_column(String(60), default="Mercado Livre")
    link_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_afiliado: Mapped[str | None] = mapped_column(Text, nullable=True)
    imagem_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vendedor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reputacao: Mapped[str | None] = mapped_column(String(60), nullable=True)
    frete_gratis: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    fonte: Mapped[str] = mapped_column(String(40), default="manual")
    dados_extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id"), nullable=True
    )
    # ID canônico do produto (MLB/Shopee) p/ dedup robusto — indexado.
    produto_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Postagem(Base):
    __tablename__ = "postagens"

    id: Mapped[int] = mapped_column(primary_key=True)
    oferta_id: Mapped[int] = mapped_column(ForeignKey("ofertas.id", ondelete="CASCADE"))
    canal: Mapped[str] = mapped_column(String(40))
    sucesso: Mapped[bool] = mapped_column(Boolean, default=False)
    resposta: Mapped[str | None] = mapped_column(Text, nullable=True)
    postado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Configuracao(Base):
    __tablename__ = "configuracoes"

    chave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)


class HistoricoBusca(Base):
    __tablename__ = "historico_buscas"

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[str] = mapped_column(String(40))
    palavra_chave: Mapped[str | None] = mapped_column(Text, nullable=True)
    qtd_resultados: Mapped[int] = mapped_column(Integer, default=0)
    buscado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(Text)
    link_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    loja: Mapped[str | None] = mapped_column(String(60), nullable=True)
    preco: Mapped[float] = mapped_column(Float)
    preco_original: Mapped[float | None] = mapped_column(Float, nullable=True)
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id"), nullable=True
    )
    registrado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProdutoRecorrente(Base):
    __tablename__ = "produtos_recorrentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(Text)
    link_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    loja: Mapped[str] = mapped_column(String(60), default="Mercado Livre")
    preco_alvo: Mapped[float | None] = mapped_column(Float, nullable=True)
    preco_atual: Mapped[float | None] = mapped_column(Float, nullable=True)
    preco_minimo: Mapped[float | None] = mapped_column(Float, nullable=True)
    departamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("departamentos.id"), nullable=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_check: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def criar_engine(url: str | None = None) -> Engine:
    """Cria o engine. Para Postgres usa pool com pre-ping; SQLite sem pool args."""
    url = url or config.DATABASE_URL
    if url.startswith("sqlite"):
        return create_engine(url, future=True)
    return create_engine(
        url,
        pool_pre_ping=True,   # evita conexão morta no pool
        pool_size=5,
        max_overflow=10,
        future=True,
    )


def criar_session_factory(engine: Engine) -> sessionmaker:
    """Fábrica de sessões ligada a um engine (uso futuro na TASK-04)."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db_pg(engine: Engine | None = None) -> Engine:
    """Cria todas as tabelas no banco apontado pelo engine (idempotente)."""
    engine = engine or criar_engine()
    Base.metadata.create_all(engine)
    return engine
