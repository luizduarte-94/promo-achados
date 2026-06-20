# -*- coding: utf-8 -*-
"""
Acesso a dados — PostgreSQL por padrão, SQLite como fallback (TASK-04).

A "virada de chave": as operações agora rodam sobre a camada ORM
(backend/models.py), escolhendo o banco por DATABASE_URL (Postgres) ou, se
USE_SQLITE=true, o SQLite legado. As ASSINATURAS e os FORMATOS de retorno das
funções públicas continuam idênticos (mesmos dicts/chaves), para não quebrar
quem consome (routes, scheduler, precos).
"""

from __future__ import annotations

import re
from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine

from backend.config import config
from backend.models import (
    Base,
    Configuracao,
    Departamento,
    HistoricoBusca,
    HistoricoPreco,
    Oferta,
    Postagem,
    ProdutoRecorrente,
    criar_engine,
    criar_session_factory,
)


# =============================================
# ENGINE / SESSÃO (Postgres padrão; SQLite se USE_SQLITE=true)
# =============================================

def _db_url() -> str:
    if config.USE_SQLITE:
        return f"sqlite:///{config.DB_PATH}"
    return config.DATABASE_URL


_engine: Engine = criar_engine(_db_url())
_Session = criar_session_factory(_engine)


def get_engine() -> Engine:
    """Engine atual (Postgres ou SQLite conforme config)."""
    return _engine


def reconfigurar(url: str) -> None:
    """Reaponta o banco em runtime (usado por testes p/ alternar SQLite/Postgres)."""
    global _engine, _Session
    _engine = criar_engine(url)
    _Session = criar_session_factory(_engine)


def _get_conn():
    """Conexão DBAPI bruta (compat com scripts/testes). Prefira as funções públicas."""
    return _engine.raw_connection()


# =============================================
# HELPERS
# =============================================

def extrair_produto_id(link: str) -> str | None:
    """Extrai um ID canônico do produto a partir do link (para dedup robusto).

    Mercado Livre: MLB-123456789 ou MLB123456789  -> 'MLB123456789'
    Shopee:        ...-i.SHOPID.ITEMID             -> 'shopee.SHOPID.ITEMID'
    """
    if not link:
        return None
    m = re.search(r"MLB-?(\d+)", link, re.IGNORECASE)
    if m:
        return f"MLB{m.group(1)}"
    m = re.search(r"i\.(\d+)\.(\d+)", link)
    if m:
        return f"shopee.{m.group(1)}.{m.group(2)}"
    return None


def _to_dict(obj) -> dict:
    """Modelo -> dict com todas as colunas (mesmas chaves do schema)."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _oferta_dict(oferta: Oferta, dep_nome=None, dep_emoji=None) -> dict:
    """Serializa Oferta preservando o contrato antigo (dados_extra dict + dep_*)."""
    d = _to_dict(oferta)
    d["dados_extra"] = oferta.dados_extra if isinstance(oferta.dados_extra, dict) else {}
    d["departamento_nome"] = dep_nome
    d["departamento_emoji"] = dep_emoji
    return d


_DEPARTAMENTOS_PADRAO = [
    (
        "Fitness & Academia",
        "💪",
        "creatina,whey,whey protein,proteina,albumina,bcaa,glutamina,pre treino,barra proteica,academia,suplemento,maltodextrina,amendoim,pasta de amendoim,dr peanut",
    ),
    (
        "Bebê & Fraldas",
        "🍼",
        "fralda,fraldas,pampers,huggies,lenco umedecido,pomada assadura,bebe,mamadeira,infantil",
    ),
    (
        "Saúde & Beleza",
        "💄",
        "Hidratantes,oleo,oleo corporal,protetor solar,shampoo,condicionador,perfume,maquiagem,skincare,hidratante,creme,cabelo,desodorante,sabonete,serum,hidratantes",
    ),
    (
        "Eletrônicos",
        "📱",
        "notebook,fone,fone de ouvido,fone bluetooth,buds,airpods,headphone,headset,smart tv,tv,qled,oled,tablet,smartwatch,celular,smartphone,monitor,ssd,mouse,teclado,carregador,powerbank,caixa de som",
    ),
    (
        "Casa & Limpeza",
        "🏠",
        "detergente,amaciante,papel higienico,aspirador,panela,limpeza,organizador,vassoura,esponja",
    ),
    (
        "Games",
        "🎮",
        "playstation,xbox,nintendo,controle,jogo,headset gamer,cadeira gamer,console,gamer",
    ),
    (
        "Moda & Acessórios",
        "👗",
        "tenis,roupa,camisa,camiseta,relogio,bolsa,oculos,jaqueta,calca,vestido",
    ),
    (
        "Alimentos & Bebidas",
        "🍕",
        "cafe,chocolate,biscoito,cerveja,vinho,leite,cereal,tahine,manteiga,azeite,achocolatado",
    ),
]


def init_db():
    """Cria as tabelas (create_all) e semeia os departamentos padrão se vazio."""
    Base.metadata.create_all(_engine)
    with _Session() as s:
        if s.scalar(select(func.count()).select_from(Departamento)) == 0:
            s.add_all(
                Departamento(nome=n, emoji=e, palavras_chave=k)
                for n, e, k in _DEPARTAMENTOS_PADRAO
            )
            s.commit()


# =============================================
# OFERTAS
# =============================================

def criar_oferta(dados: dict) -> int:
    """Insere uma oferta e retorna o ID."""
    if not dados.get("departamento_id") and dados.get("titulo"):
        dados = {**dados, "departamento_id": classificar_departamento(dados["titulo"])}

    with _Session() as s:
        oferta = Oferta(
            titulo=dados.get("titulo", ""),
            preco=dados.get("preco", 0),
            preco_original=dados.get("preco_original"),
            desconto_pct=dados.get("desconto_pct", 0),
            loja=dados.get("loja", "Mercado Livre"),
            link_original=dados.get("link_original"),
            link_afiliado=dados.get("link_afiliado"),
            imagem_url=dados.get("imagem_url"),
            categoria=dados.get("categoria"),
            vendedor=dados.get("vendedor"),
            reputacao=dados.get("reputacao"),
            frete_gratis=bool(dados.get("frete_gratis", False)),
            status=dados.get("status", "pendente"),
            fonte=dados.get("fonte", "manual"),
            dados_extra=dados.get("dados_extra") or None,
            departamento_id=dados.get("departamento_id"),
            produto_id=extrair_produto_id(dados.get("link_original")),
        )
        s.add(oferta)
        s.commit()
        return oferta.id


def listar_ofertas(status: str = None, loja: str = None, limite: int = 100) -> list[dict]:
    """Lista ofertas com filtros opcionais (inclui nome/emoji do departamento)."""
    with _Session() as s:
        stmt = select(Oferta, Departamento.nome, Departamento.emoji).join(
            Departamento, Oferta.departamento_id == Departamento.id, isouter=True
        )
        if status:
            stmt = stmt.where(Oferta.status == status)
        if loja:
            stmt = stmt.where(Oferta.loja == loja)
        stmt = stmt.order_by(Oferta.criado_em.desc()).limit(limite)
        return [_oferta_dict(o, nome, emoji) for o, nome, emoji in s.execute(stmt).all()]


def obter_oferta(oferta_id: int) -> dict | None:
    """Retorna uma oferta pelo ID (com nome/emoji do departamento)."""
    with _Session() as s:
        stmt = (
            select(Oferta, Departamento.nome, Departamento.emoji)
            .join(Departamento, Oferta.departamento_id == Departamento.id, isouter=True)
            .where(Oferta.id == oferta_id)
        )
        linha = s.execute(stmt).first()
        if not linha:
            return None
        oferta, nome, emoji = linha
        return _oferta_dict(oferta, nome, emoji)


_CAMPOS_OFERTA = (
    "titulo", "preco", "preco_original", "desconto_pct", "loja", "link_original",
    "link_afiliado", "imagem_url", "categoria", "vendedor", "reputacao",
    "frete_gratis", "status", "departamento_id",
)


def atualizar_oferta(oferta_id: int, dados: dict) -> bool:
    """Atualiza campos de uma oferta. Retorna False se não houver campos válidos."""
    campos = {k: dados[k] for k in _CAMPOS_OFERTA if k in dados}
    if not campos:
        return False
    if "frete_gratis" in campos:
        campos["frete_gratis"] = bool(campos["frete_gratis"])
    with _Session() as s:
        oferta = s.get(Oferta, oferta_id)
        if oferta:
            for chave, valor in campos.items():
                setattr(oferta, chave, valor)
            oferta.atualizado_em = datetime.now()
            s.commit()
    return True


def deletar_oferta(oferta_id: int) -> bool:
    """Remove uma oferta (e suas postagens)."""
    with _Session() as s:
        oferta = s.get(Oferta, oferta_id)
        if not oferta:
            return False
        s.execute(delete(Postagem).where(Postagem.oferta_id == oferta_id))
        s.delete(oferta)
        s.commit()
        return True


def oferta_existe(link_original: str) -> bool:
    """Verifica se já existe oferta com este produto (dedup por ID canônico)."""
    produto_id = extrair_produto_id(link_original)
    with _Session() as s:
        if produto_id:
            stmt = select(Oferta.id).where(Oferta.produto_id == produto_id).limit(1)
        else:
            stmt = select(Oferta.id).where(Oferta.link_original == link_original).limit(1)
        return s.scalar(stmt) is not None


def coletar_e_salvar(ofertas: list[dict], fonte: str | None = None) -> list[dict]:
    """Salva uma leva de ofertas brutas com o mesmo pipeline em todo lugar.

    Para cada oferta: pula duplicata, classifica departamento, cria no banco e
    registra o preço no histórico. Fonte única usada por busca manual,
    automática e espelho.
    """
    novas: list[dict] = []
    for oferta in ofertas:
        if oferta_existe(oferta.get("link_original")):
            continue
        if fonte:
            oferta["fonte"] = fonte
        dep_id = classificar_departamento(oferta.get("titulo", ""))
        if dep_id:
            oferta["departamento_id"] = dep_id
        oferta["id"] = criar_oferta(oferta)
        registrar_preco(
            titulo=oferta.get("titulo", ""),
            preco=oferta.get("preco", 0),
            link_original=oferta.get("link_original"),
            loja=oferta.get("loja"),
            preco_original=oferta.get("preco_original"),
            departamento_id=dep_id,
        )
        novas.append(oferta)
    return novas


# =============================================
# POSTAGENS
# =============================================

def registrar_postagem(oferta_id: int, canal: str, sucesso: bool, resposta: str = None):
    """Registra uma postagem feita; marca a oferta como 'postada' se sucesso."""
    with _Session() as s:
        s.add(Postagem(oferta_id=oferta_id, canal=canal, sucesso=bool(sucesso), resposta=resposta))
        if sucesso:
            oferta = s.get(Oferta, oferta_id)
            if oferta:
                oferta.status = "postada"
                oferta.atualizado_em = datetime.now()
        s.commit()


def listar_postagens(limite: int = 50) -> list[dict]:
    """Lista postagens recentes com dados da oferta (titulo/loja/preco)."""
    with _Session() as s:
        stmt = (
            select(Postagem, Oferta.titulo, Oferta.loja, Oferta.preco)
            .join(Oferta, Postagem.oferta_id == Oferta.id)
            .order_by(Postagem.postado_em.desc())
            .limit(limite)
        )
        saida = []
        for postagem, titulo, loja, preco in s.execute(stmt).all():
            d = _to_dict(postagem)
            d["titulo"] = titulo
            d["loja"] = loja
            d["preco"] = preco
            saida.append(d)
        return saida


# =============================================
# ESTATÍSTICAS
# =============================================

def obter_stats() -> dict:
    """Estatísticas para o dashboard."""
    inicio_hoje = datetime.combine(date.today(), datetime.min.time())
    with _Session() as s:
        total = s.scalar(select(func.count()).select_from(Oferta))
        pendentes = s.scalar(
            select(func.count()).select_from(Oferta).where(Oferta.status == "pendente")
        )
        postadas = s.scalar(
            select(func.count()).select_from(Oferta).where(Oferta.status == "postada")
        )
        postadas_hoje = s.scalar(
            select(func.count()).select_from(Postagem).where(Postagem.postado_em >= inicio_hoje)
        )
        desconto_medio = s.scalar(
            select(func.coalesce(func.avg(Oferta.desconto_pct), 0)).where(Oferta.desconto_pct > 0)
        )
        buscas_hoje = s.scalar(
            select(func.count()).select_from(HistoricoBusca).where(
                HistoricoBusca.buscado_em >= inicio_hoje
            )
        )
    return {
        "total_ofertas": total or 0,
        "pendentes": pendentes or 0,
        "postadas": postadas or 0,
        "postadas_hoje": postadas_hoje or 0,
        "desconto_medio": round(float(desconto_medio or 0), 1),
        "buscas_hoje": buscas_hoje or 0,
    }


# =============================================
# HISTÓRICO DE BUSCAS
# =============================================

def registrar_busca(fonte: str, palavra_chave: str, qtd: int):
    """Registra uma busca realizada."""
    with _Session() as s:
        s.add(HistoricoBusca(fonte=fonte, palavra_chave=palavra_chave, qtd_resultados=qtd))
        s.commit()


# =============================================
# CONFIGURAÇÕES
# =============================================

def obter_configuracao(chave: str) -> str | None:
    """Retorna o valor de uma chave na tabela configuracoes."""
    with _Session() as s:
        cfg = s.get(Configuracao, chave)
        return cfg.valor if cfg else None


def definir_configuracao(chave: str, valor: str):
    """Define ou atualiza o valor de uma chave (upsert)."""
    with _Session() as s:
        cfg = s.get(Configuracao, chave)
        if cfg:
            cfg.valor = valor
        else:
            s.add(Configuracao(chave=chave, valor=valor))
        s.commit()


# =============================================
# DEPARTAMENTOS
# =============================================

def listar_departamentos(apenas_ativos: bool = True) -> list[dict]:
    """Lista todos os departamentos (ordenados por nome)."""
    with _Session() as s:
        stmt = select(Departamento)
        if apenas_ativos:
            stmt = stmt.where(Departamento.ativo.is_(True))
        stmt = stmt.order_by(Departamento.nome)
        return [_to_dict(d) for d in s.scalars(stmt).all()]


def obter_departamento(dep_id: int) -> dict | None:
    """Retorna um departamento pelo ID."""
    with _Session() as s:
        dep = s.get(Departamento, dep_id)
        return _to_dict(dep) if dep else None


def criar_departamento(nome: str, emoji: str = "📦", palavras_chave: str = "") -> int:
    """Cria um departamento e retorna o ID."""
    with _Session() as s:
        dep = Departamento(nome=nome, emoji=emoji, palavras_chave=palavras_chave)
        s.add(dep)
        s.commit()
        return dep.id


def atualizar_departamento(dep_id: int, dados: dict) -> bool:
    """Atualiza um departamento. False se não houver campos válidos."""
    campos = {k: dados[k] for k in ("nome", "emoji", "palavras_chave", "ativo") if k in dados}
    if not campos:
        return False
    if "ativo" in campos:
        campos["ativo"] = bool(campos["ativo"])
    with _Session() as s:
        dep = s.get(Departamento, dep_id)
        if dep:
            for chave, valor in campos.items():
                setattr(dep, chave, valor)
            s.commit()
    return True


def melhor_departamento(titulo: str, deps: list[dict]) -> int | None:
    """Escolhe o melhor departamento para um título (função pura, sem I/O).

    Casa por PALAVRAS: keyword de várias palavras casa quando todas aparecem
    no título; keyword de palavra única casa por token exato.
    """
    tokens = set(re.findall(r"[a-z0-9]+", titulo.lower()))
    if not tokens:
        return None

    melhor_score = 0
    melhor_dep_id = None
    for dep in deps:
        keywords = [
            k.strip().lower()
            for k in (dep.get("palavras_chave") or "").split(",")
            if k.strip()
        ]
        score = 0
        for kw in keywords:
            if all(p in tokens for p in kw.split()):
                score += len(kw)
        if score > melhor_score:
            melhor_score = score
            melhor_dep_id = dep["id"]
    return melhor_dep_id


def classificar_departamento(titulo: str) -> int | None:
    """Classifica uma oferta no melhor departamento com base no título."""
    return melhor_departamento(titulo, listar_departamentos())


# =============================================
# HISTÓRICO DE PREÇOS
# =============================================

def registrar_preco(
    titulo: str,
    preco: float,
    link_original: str = None,
    loja: str = None,
    preco_original: float = None,
    departamento_id: int = None,
):
    """Registra um snapshot de preço no histórico."""
    with _Session() as s:
        s.add(
            HistoricoPreco(
                titulo=titulo,
                preco=preco,
                link_original=link_original,
                loja=loja,
                preco_original=preco_original,
                departamento_id=departamento_id,
            )
        )
        s.commit()


def obter_historico_precos(
    link_original: str = None, titulo: str = None, limite: int = 180
) -> list[dict]:
    """Retorna histórico de preços (por link, ou por título parcial, ou tudo)."""
    with _Session() as s:
        stmt = select(HistoricoPreco)
        if link_original:
            stmt = stmt.where(HistoricoPreco.link_original == link_original)
        elif titulo:
            stmt = stmt.where(HistoricoPreco.titulo.like(f"%{titulo}%"))
        stmt = stmt.order_by(HistoricoPreco.registrado_em.desc()).limit(limite)
        return [_to_dict(h) for h in s.scalars(stmt).all()]


def obter_menor_preco(link_original: str) -> float | None:
    """Retorna o menor preço histórico de um produto."""
    with _Session() as s:
        menor = s.scalar(
            select(func.min(HistoricoPreco.preco)).where(
                HistoricoPreco.link_original == link_original
            )
        )
        return menor if menor else None


# =============================================
# PRODUTOS RECORRENTES
# =============================================

def listar_produtos_recorrentes(apenas_ativos: bool = True) -> list[dict]:
    """Lista produtos recorrentes (com nome/emoji do departamento)."""
    with _Session() as s:
        stmt = select(ProdutoRecorrente, Departamento.nome, Departamento.emoji).join(
            Departamento, ProdutoRecorrente.departamento_id == Departamento.id, isouter=True
        )
        if apenas_ativos:
            stmt = stmt.where(ProdutoRecorrente.ativo.is_(True))
        stmt = stmt.order_by(ProdutoRecorrente.criado_em.desc())
        saida = []
        for prod, nome, emoji in s.execute(stmt).all():
            d = _to_dict(prod)
            d["departamento_nome"] = nome
            d["departamento_emoji"] = emoji
            saida.append(d)
        return saida


def criar_produto_recorrente(dados: dict) -> int:
    """Cadastra um produto recorrente para monitoramento."""
    with _Session() as s:
        prod = ProdutoRecorrente(
            titulo=dados.get("titulo", ""),
            link_original=dados.get("link_original"),
            loja=dados.get("loja", "Mercado Livre"),
            preco_alvo=dados.get("preco_alvo"),
            preco_atual=dados.get("preco_atual"),
            departamento_id=dados.get("departamento_id"),
        )
        s.add(prod)
        s.commit()
        return prod.id


_CAMPOS_RECORRENTE = (
    "titulo", "link_original", "loja", "preco_alvo", "preco_atual",
    "preco_minimo", "departamento_id", "ativo", "ultimo_check",
)


def atualizar_produto_recorrente(prod_id: int, dados: dict) -> bool:
    """Atualiza dados de um produto recorrente. False se não houver campos."""
    campos = {k: dados[k] for k in _CAMPOS_RECORRENTE if k in dados}
    if not campos:
        return False
    if "ativo" in campos:
        campos["ativo"] = bool(campos["ativo"])
    with _Session() as s:
        prod = s.get(ProdutoRecorrente, prod_id)
        if prod:
            for chave, valor in campos.items():
                setattr(prod, chave, valor)
            s.commit()
    return True


def deletar_produto_recorrente(prod_id: int) -> bool:
    """Remove um produto recorrente."""
    with _Session() as s:
        prod = s.get(ProdutoRecorrente, prod_id)
        if not prod:
            return False
        s.delete(prod)
        s.commit()
        return True
