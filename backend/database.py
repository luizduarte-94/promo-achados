# -*- coding: utf-8 -*-
"""
Banco de dados SQLite — modelos e operações.
"""

import sqlite3
import json
import re
from datetime import datetime
from backend.config import config


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


def _get_conn() -> sqlite3.Connection:
    """Retorna conexão com row_factory configurada."""
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Cria as tabelas se não existirem."""
    conn = _get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ofertas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo          TEXT NOT NULL,
            preco           REAL NOT NULL,
            preco_original  REAL,
            desconto_pct    REAL DEFAULT 0,
            loja            TEXT NOT NULL DEFAULT 'Mercado Livre',
            link_original   TEXT,
            link_afiliado   TEXT,
            imagem_url      TEXT,
            categoria       TEXT,
            vendedor        TEXT,
            reputacao       TEXT,
            frete_gratis    INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'pendente',
            fonte           TEXT DEFAULT 'manual',
            dados_extra     TEXT,
            departamento_id INTEGER,
            criado_em       TEXT DEFAULT (datetime('now', 'localtime')),
            atualizado_em   TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (departamento_id) REFERENCES departamentos(id)
        );

        CREATE TABLE IF NOT EXISTS postagens (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            oferta_id   INTEGER NOT NULL,
            canal       TEXT NOT NULL,
            sucesso     INTEGER DEFAULT 0,
            resposta    TEXT,
            postado_em  TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (oferta_id) REFERENCES ofertas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS configuracoes (
            chave   TEXT PRIMARY KEY,
            valor   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS historico_buscas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fonte           TEXT NOT NULL,
            palavra_chave   TEXT,
            qtd_resultados  INTEGER DEFAULT 0,
            buscado_em      TEXT DEFAULT (datetime('now', 'localtime'))
        );

        -- NOVOS: Departamentos
        CREATE TABLE IF NOT EXISTS departamentos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome            TEXT NOT NULL UNIQUE,
            emoji           TEXT DEFAULT '📦',
            palavras_chave  TEXT,
            ativo           INTEGER DEFAULT 1,
            criado_em       TEXT DEFAULT (datetime('now', 'localtime'))
        );

        -- NOVOS: Histórico de Preços (rastreamento ao longo do tempo)
        CREATE TABLE IF NOT EXISTS historico_precos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo          TEXT NOT NULL,
            link_original   TEXT,
            loja            TEXT,
            preco           REAL NOT NULL,
            preco_original  REAL,
            departamento_id INTEGER,
            registrado_em   TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (departamento_id) REFERENCES departamentos(id)
        );

        -- NOVOS: Produtos Recorrentes (monitoramento contínuo de best sellers)
        CREATE TABLE IF NOT EXISTS produtos_recorrentes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo          TEXT NOT NULL,
            link_original   TEXT,
            loja            TEXT DEFAULT 'Mercado Livre',
            preco_alvo      REAL,
            preco_atual     REAL,
            preco_minimo    REAL,
            departamento_id INTEGER,
            ativo           INTEGER DEFAULT 1,
            ultimo_check    TEXT,
            criado_em       TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (departamento_id) REFERENCES departamentos(id)
        );
    """
    )

    # Migração: adicionar coluna departamento_id se não existir
    try:
        conn.execute("SELECT departamento_id FROM ofertas LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE ofertas ADD COLUMN departamento_id INTEGER")

    # Migração: adicionar coluna produto_id (ID canônico para dedup robusto)
    try:
        conn.execute("SELECT produto_id FROM ofertas LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE ofertas ADD COLUMN produto_id TEXT")

    # Inserir departamentos padrão se a tabela estiver vazia
    count = conn.execute("SELECT COUNT(*) FROM departamentos").fetchone()[0]
    if count == 0:
        departamentos_padrao = [
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
        conn.executemany(
            "INSERT INTO departamentos (nome, emoji, palavras_chave) VALUES (?, ?, ?)",
            departamentos_padrao,
        )

    conn.commit()
    conn.close()


# =============================================
# OFERTAS
# =============================================


def criar_oferta(dados: dict) -> int:
    """Insere uma oferta e retorna o ID."""
    # Classificação automática de departamento se não informado
    if not dados.get("departamento_id") and dados.get("titulo"):
        dados = {**dados, "departamento_id": classificar_departamento(dados["titulo"])}

    conn = _get_conn()
    cur = conn.execute(
        """
        INSERT INTO ofertas (titulo, preco, preco_original, desconto_pct, loja,
                             link_original, link_afiliado, imagem_url, categoria,
                             vendedor, reputacao, frete_gratis, status, fonte, dados_extra,
                             departamento_id, produto_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            dados.get("titulo", ""),
            dados.get("preco", 0),
            dados.get("preco_original"),
            dados.get("desconto_pct", 0),
            dados.get("loja", "Mercado Livre"),
            dados.get("link_original"),
            dados.get("link_afiliado"),
            dados.get("imagem_url"),
            dados.get("categoria"),
            dados.get("vendedor"),
            dados.get("reputacao"),
            dados.get("frete_gratis", 0),
            dados.get("status", "pendente"),
            dados.get("fonte", "manual"),
            json.dumps(dados.get("dados_extra")) if dados.get("dados_extra") else None,
            dados.get("departamento_id"),
            extrair_produto_id(dados.get("link_original")),
        ),
    )
    conn.commit()
    oferta_id = cur.lastrowid
    conn.close()
    return oferta_id


def _parse_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("dados_extra"):
        try:
            d["dados_extra"] = json.loads(d["dados_extra"])
        except json.JSONDecodeError:
            d["dados_extra"] = {}
    else:
        d["dados_extra"] = {}
    return d


def listar_ofertas(
    status: str = None, loja: str = None, limite: int = 100
) -> list[dict]:
    """Lista ofertas com filtros opcionais."""
    conn = _get_conn()
    query = """
        SELECT o.*, d.nome AS departamento_nome, d.emoji AS departamento_emoji
        FROM ofertas o
        LEFT JOIN departamentos d ON o.departamento_id = d.id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND o.status = ?"
        params.append(status)
    if loja:
        query += " AND o.loja = ?"
        params.append(loja)

    query += " ORDER BY o.criado_em DESC LIMIT ?"
    params.append(limite)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_parse_row(r) for r in rows]


def obter_oferta(oferta_id: int) -> dict | None:
    """Retorna uma oferta pelo ID."""
    conn = _get_conn()
    row = conn.execute(
        """
        SELECT o.*, d.nome AS departamento_nome, d.emoji AS departamento_emoji
        FROM ofertas o
        LEFT JOIN departamentos d ON o.departamento_id = d.id
        WHERE o.id = ?
    """,
        (oferta_id,),
    ).fetchone()
    conn.close()
    return _parse_row(row) if row else None


def atualizar_oferta(oferta_id: int, dados: dict) -> bool:
    """Atualiza campos de uma oferta."""
    conn = _get_conn()
    campos = []
    valores = []
    for chave in (
        "titulo",
        "preco",
        "preco_original",
        "desconto_pct",
        "loja",
        "link_original",
        "link_afiliado",
        "imagem_url",
        "categoria",
        "vendedor",
        "reputacao",
        "frete_gratis",
        "status",
        "departamento_id",
    ):
        if chave in dados:
            campos.append(f"{chave} = ?")
            valores.append(dados[chave])

    if not campos:
        conn.close()
        return False

    campos.append("atualizado_em = datetime('now', 'localtime')")
    valores.append(oferta_id)

    conn.execute(f"UPDATE ofertas SET {', '.join(campos)} WHERE id = ?", valores)
    conn.commit()
    conn.close()
    return True


def deletar_oferta(oferta_id: int) -> bool:
    """Remove uma oferta."""
    conn = _get_conn()
    cur = conn.execute("DELETE FROM ofertas WHERE id = ?", (oferta_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def oferta_existe(link_original: str) -> bool:
    """Verifica se já existe oferta com este produto (evita duplicatas).

    Usa o ID canônico do produto quando extraível (robusto a variações de URL);
    cai para comparação de link exato quando não há ID.
    """
    conn = _get_conn()
    produto_id = extrair_produto_id(link_original)
    if produto_id:
        row = conn.execute(
            "SELECT id FROM ofertas WHERE produto_id = ?", (produto_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM ofertas WHERE link_original = ?", (link_original,)
        ).fetchone()
    conn.close()
    return row is not None


def coletar_e_salvar(ofertas: list[dict], fonte: str | None = None) -> list[dict]:
    """Salva uma leva de ofertas brutas (de scraper) com o mesmo pipeline em todo lugar.

    Para cada oferta: pula duplicata, classifica departamento, cria no banco e
    registra o preço no histórico. Usado por busca manual, busca automática e
    espelho — fonte única para não divergir (ex.: Shopee esquecer o histórico).

    Args:
        ofertas: lista de dicts no formato do scraper.
        fonte: se informado, sobrescreve o campo 'fonte' de cada oferta.

    Returns:
        Lista das ofertas novas criadas (com 'id' e 'departamento_id' preenchidos).
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
    """Registra uma postagem feita."""
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO postagens (oferta_id, canal, sucesso, resposta)
        VALUES (?, ?, ?, ?)
    """,
        (oferta_id, canal, int(sucesso), resposta),
    )

    if sucesso:
        conn.execute(
            "UPDATE ofertas SET status = 'postada', atualizado_em = datetime('now', 'localtime') WHERE id = ?",
            (oferta_id,),
        )

    conn.commit()
    conn.close()


def listar_postagens(limite: int = 50) -> list[dict]:
    """Lista postagens recentes com dados da oferta."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT p.*, o.titulo, o.loja, o.preco
        FROM postagens p
        JOIN ofertas o ON p.oferta_id = o.id
        ORDER BY p.postado_em DESC
        LIMIT ?
    """,
        (limite,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =============================================
# ESTATÍSTICAS
# =============================================


def obter_stats() -> dict:
    """Estatísticas para o dashboard."""
    conn = _get_conn()

    total = conn.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0]
    pendentes = conn.execute(
        "SELECT COUNT(*) FROM ofertas WHERE status = 'pendente'"
    ).fetchone()[0]
    postadas = conn.execute(
        "SELECT COUNT(*) FROM ofertas WHERE status = 'postada'"
    ).fetchone()[0]

    hoje = datetime.now().strftime("%Y-%m-%d")
    postadas_hoje = conn.execute(
        "SELECT COUNT(*) FROM postagens WHERE postado_em LIKE ?", (f"{hoje}%",)
    ).fetchone()[0]

    desconto_medio = conn.execute(
        "SELECT COALESCE(AVG(desconto_pct), 0) FROM ofertas WHERE desconto_pct > 0"
    ).fetchone()[0]

    buscas_hoje = conn.execute(
        "SELECT COUNT(*) FROM historico_buscas WHERE buscado_em LIKE ?", (f"{hoje}%",)
    ).fetchone()[0]

    conn.close()
    return {
        "total_ofertas": total,
        "pendentes": pendentes,
        "postadas": postadas,
        "postadas_hoje": postadas_hoje,
        "desconto_medio": round(desconto_medio, 1),
        "buscas_hoje": buscas_hoje,
    }


# =============================================
# HISTÓRICO DE BUSCAS
# =============================================


def registrar_busca(fonte: str, palavra_chave: str, qtd: int):
    """Registra uma busca realizada."""
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO historico_buscas (fonte, palavra_chave, qtd_resultados)
        VALUES (?, ?, ?)
    """,
        (fonte, palavra_chave, qtd),
    )
    conn.commit()
    conn.close()


# =============================================
# CONFIGURAÇÕES ADICIONAIS
# =============================================


def obter_configuracao(chave: str) -> str | None:
    """Retorna o valor de uma chave na tabela configuracoes."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT valor FROM configuracoes WHERE chave = ?", (chave,)
    ).fetchone()
    conn.close()
    return row["valor"] if row else None


def definir_configuracao(chave: str, valor: str):
    """Define ou atualiza o valor de uma chave na tabela configuracoes."""
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO configuracoes (chave, valor)
        VALUES (?, ?)
        ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor
    """,
        (chave, valor),
    )
    conn.commit()
    conn.close()


# =============================================
# DEPARTAMENTOS
# =============================================


def listar_departamentos(apenas_ativos: bool = True) -> list[dict]:
    """Lista todos os departamentos."""
    conn = _get_conn()
    query = "SELECT * FROM departamentos"
    if apenas_ativos:
        query += " WHERE ativo = 1"
    query += " ORDER BY nome"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obter_departamento(dep_id: int) -> dict | None:
    """Retorna um departamento pelo ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM departamentos WHERE id = ?", (dep_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def criar_departamento(nome: str, emoji: str = "📦", palavras_chave: str = "") -> int:
    """Cria um departamento e retorna o ID."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO departamentos (nome, emoji, palavras_chave) VALUES (?, ?, ?)",
        (nome, emoji, palavras_chave),
    )
    conn.commit()
    dep_id = cur.lastrowid
    conn.close()
    return dep_id


def atualizar_departamento(dep_id: int, dados: dict) -> bool:
    """Atualiza um departamento."""
    conn = _get_conn()
    campos = []
    valores = []
    for chave in ("nome", "emoji", "palavras_chave", "ativo"):
        if chave in dados:
            campos.append(f"{chave} = ?")
            valores.append(dados[chave])
    if not campos:
        conn.close()
        return False
    valores.append(dep_id)
    conn.execute(f"UPDATE departamentos SET {', '.join(campos)} WHERE id = ?", valores)
    conn.commit()
    conn.close()
    return True


def melhor_departamento(titulo: str, deps: list[dict]) -> int | None:
    """Escolhe o melhor departamento para um título (função pura, sem I/O).

    Casa por PALAVRAS (não substring contíguo): uma keyword de várias palavras
    (ex "fone bluetooth") casa quando todas as suas palavras aparecem no título,
    mesmo separadas ("Fone De Ouvido Sem Fio Bluetooth"). Keyword de palavra
    única casa por token exato (evita "tv" dentro de outra palavra).
    Score = soma do tamanho das keywords que casaram (mais longa = mais específica).
    """
    tokens = set(re.findall(r"[a-z0-9]+", titulo.lower()))
    if not tokens:
        return None

    melhor_score = 0
    melhor_dep_id = None
    for dep in deps:
        keywords = [
            k.strip().lower()
            for k in dep.get("palavras_chave", "").split(",")
            if k.strip()
        ]
        score = 0
        for kw in keywords:
            palavras_kw = kw.split()
            if all(p in tokens for p in palavras_kw):
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
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO historico_precos (titulo, preco, link_original, loja,
                                      preco_original, departamento_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (titulo, preco, link_original, loja, preco_original, departamento_id),
    )
    conn.commit()
    conn.close()


def obter_historico_precos(
    link_original: str = None, titulo: str = None, limite: int = 180
) -> list[dict]:
    """Retorna histórico de preços de um produto (por link ou título parcial)."""
    conn = _get_conn()
    if link_original:
        rows = conn.execute(
            "SELECT * FROM historico_precos WHERE link_original = ? ORDER BY registrado_em DESC LIMIT ?",
            (link_original, limite),
        ).fetchall()
    elif titulo:
        rows = conn.execute(
            "SELECT * FROM historico_precos WHERE titulo LIKE ? ORDER BY registrado_em DESC LIMIT ?",
            (f"%{titulo}%", limite),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM historico_precos ORDER BY registrado_em DESC LIMIT ?",
            (limite,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obter_menor_preco(link_original: str) -> float | None:
    """Retorna o menor preço histórico de um produto."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT MIN(preco) as menor FROM historico_precos WHERE link_original = ?",
        (link_original,),
    ).fetchone()
    conn.close()
    return row["menor"] if row and row["menor"] else None


# =============================================
# PRODUTOS RECORRENTES
# =============================================


def listar_produtos_recorrentes(apenas_ativos: bool = True) -> list[dict]:
    """Lista produtos recorrentes (best sellers monitorados)."""
    conn = _get_conn()
    query = """
        SELECT pr.*, d.nome as departamento_nome, d.emoji as departamento_emoji
        FROM produtos_recorrentes pr
        LEFT JOIN departamentos d ON pr.departamento_id = d.id
    """
    if apenas_ativos:
        query += " WHERE pr.ativo = 1"
    query += " ORDER BY pr.criado_em DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def criar_produto_recorrente(dados: dict) -> int:
    """Cadastra um produto recorrente para monitoramento."""
    conn = _get_conn()
    cur = conn.execute(
        """
        INSERT INTO produtos_recorrentes (titulo, link_original, loja, preco_alvo,
                                           preco_atual, departamento_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            dados.get("titulo", ""),
            dados.get("link_original"),
            dados.get("loja", "Mercado Livre"),
            dados.get("preco_alvo"),
            dados.get("preco_atual"),
            dados.get("departamento_id"),
        ),
    )
    conn.commit()
    prod_id = cur.lastrowid
    conn.close()
    return prod_id


def atualizar_produto_recorrente(prod_id: int, dados: dict) -> bool:
    """Atualiza dados de um produto recorrente."""
    conn = _get_conn()
    campos = []
    valores = []
    for chave in (
        "titulo",
        "link_original",
        "loja",
        "preco_alvo",
        "preco_atual",
        "preco_minimo",
        "departamento_id",
        "ativo",
        "ultimo_check",
    ):
        if chave in dados:
            campos.append(f"{chave} = ?")
            valores.append(dados[chave])
    if not campos:
        conn.close()
        return False
    valores.append(prod_id)
    conn.execute(
        f"UPDATE produtos_recorrentes SET {', '.join(campos)} WHERE id = ?", valores
    )
    conn.commit()
    conn.close()
    return True


def deletar_produto_recorrente(prod_id: int) -> bool:
    """Remove um produto recorrente."""
    conn = _get_conn()
    cur = conn.execute("DELETE FROM produtos_recorrentes WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0
