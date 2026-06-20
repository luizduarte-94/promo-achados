# -*- coding: utf-8 -*-
"""Testes das funções públicas de database.py após a virada p/ ORM (TASK-04).

Rodam no SQLite de teste (conftest). Travam os contratos (chaves de retorno,
tipos, JOINs, dedup, upsert) pra garantir que a migração não mudou comportamento.
"""

from backend import database as db


def _nova_oferta(**extra):
    base = {
        "titulo": "Creatina Monohidratada 300g",
        "preco": 49.9,
        "preco_original": 99.9,
        "desconto_pct": 50,
        "loja": "Mercado Livre",
        "link_original": "https://produto.mercadolivre.com.br/MLB-1234567-creatina",
        "frete_gratis": True,
        "dados_extra": {"cupom": "X10"},
    }
    base.update(extra)
    return base


def test_criar_e_obter_oferta_contrato():
    oid = db.criar_oferta(_nova_oferta())
    try:
        o = db.obter_oferta(oid)
        assert o is not None
        # chaves esperadas pelo frontend/rotas
        for chave in ("id", "titulo", "preco", "dados_extra", "departamento_id",
                      "produto_id", "departamento_nome", "departamento_emoji"):
            assert chave in o
        assert o["preco"] == 49.9
        assert o["frete_gratis"] in (True, 1)            # boolean
        assert o["dados_extra"] == {"cupom": "X10"}      # JSON -> dict
        assert o["produto_id"] == "MLB1234567"
        # classificação automática: creatina -> Fitness & Academia
        assert o["departamento_nome"] == "Fitness & Academia"
        assert o["departamento_emoji"] == "💪"
    finally:
        db.deletar_oferta(oid)
    assert db.obter_oferta(oid) is None                  # deletou


def test_oferta_existe_dedup_por_produto_id():
    oid = db.criar_oferta(_nova_oferta())
    try:
        # mesmo MLB (1234567), URL diferente -> dedup acusa existência
        assert db.oferta_existe("https://outro.com/MLB-1234567-variante") is True
        assert db.oferta_existe("https://x/MLB-7654321-outro") is False
    finally:
        db.deletar_oferta(oid)


def test_listar_ofertas_filtros():
    oid = db.criar_oferta(_nova_oferta(status="pendente", loja="Mercado Livre"))
    try:
        ids_pend = [o["id"] for o in db.listar_ofertas(status="pendente", limite=500)]
        assert oid in ids_pend
        ids_post = [o["id"] for o in db.listar_ofertas(status="postada", limite=500)]
        assert oid not in ids_post
        ids_loja = [o["id"] for o in db.listar_ofertas(loja="Shopee", limite=500)]
        assert oid not in ids_loja
    finally:
        db.deletar_oferta(oid)


def test_atualizar_oferta_retorno():
    oid = db.criar_oferta(_nova_oferta())
    try:
        assert db.atualizar_oferta(oid, {}) is False          # sem campos
        assert db.atualizar_oferta(oid, {"preco": 39.9}) is True
        assert db.obter_oferta(oid)["preco"] == 39.9
    finally:
        db.deletar_oferta(oid)


def test_postagem_marca_postada_e_listar_join():
    oid = db.criar_oferta(_nova_oferta())
    try:
        db.registrar_postagem(oid, "telegram", True, "ok")
        assert db.obter_oferta(oid)["status"] == "postada"
        post = [p for p in db.listar_postagens(limite=500) if p["oferta_id"] == oid]
        assert post and post[0]["titulo"] == "Creatina Monohidratada 300g"
        assert "loja" in post[0] and "preco" in post[0]      # JOIN
    finally:
        db.deletar_oferta(oid)


def test_configuracoes_upsert():
    db.definir_configuracao("__t_cfg__", "a")
    assert db.obter_configuracao("__t_cfg__") == "a"
    db.definir_configuracao("__t_cfg__", "b")               # update
    assert db.obter_configuracao("__t_cfg__") == "b"
    assert db.obter_configuracao("__nao_existe__") is None


def test_departamentos_seed_e_crud():
    deps = db.listar_departamentos()
    assert len(deps) >= 8                                    # seed
    assert {"id", "nome", "emoji", "palavras_chave", "ativo"} <= set(deps[0])
    novo = db.criar_departamento("__Teste Dep__", "🧪", "xyz")
    try:
        assert db.obter_departamento(novo)["nome"] == "__Teste Dep__"
        assert db.atualizar_departamento(novo, {"emoji": "🔬"}) is True
        assert db.obter_departamento(novo)["emoji"] == "🔬"
        assert db.atualizar_departamento(novo, {}) is False
    finally:
        # desativa (não há delete de dep) p/ não poluir
        db.atualizar_departamento(novo, {"ativo": False})


def test_historico_precos_e_menor():
    link = "https://x/MLB-9000001-hist"
    db.registrar_preco("Produto Hist", 100.0, link_original=link)
    db.registrar_preco("Produto Hist", 80.0, link_original=link)
    h = db.obter_historico_precos(link_original=link)
    assert len(h) >= 2
    assert {"titulo", "preco", "link_original", "registrado_em"} <= set(h[0])
    assert db.obter_menor_preco(link) == 80.0


def test_recorrentes_crud():
    rid = db.criar_produto_recorrente({"titulo": "__Rec Teste__", "preco_alvo": 50})
    try:
        achados = [r for r in db.listar_produtos_recorrentes() if r["id"] == rid]
        assert achados and "departamento_nome" in achados[0]
        assert db.atualizar_produto_recorrente(rid, {"preco_atual": 45.5}) is True
        assert db.atualizar_produto_recorrente(rid, {}) is False
    finally:
        assert db.deletar_produto_recorrente(rid) is True
        assert db.deletar_produto_recorrente(rid) is False   # já removido


def test_obter_stats_contrato():
    s = db.obter_stats()
    for chave in ("total_ofertas", "pendentes", "postadas", "postadas_hoje",
                  "desconto_medio", "buscas_hoje"):
        assert chave in s
        assert isinstance(s[chave], (int, float))


def test_coletar_e_salvar_pipeline():
    brutas = [
        {"titulo": "Whey Protein 1kg", "preco": 120.0,
         "link_original": "https://x/MLB-8800001-whey", "loja": "Mercado Livre"},
        {"titulo": "Whey Protein 1kg", "preco": 120.0,   # duplicata (mesmo MLB 8800001)
         "link_original": "https://x/MLB-8800001-bis", "loja": "Mercado Livre"},
    ]
    novas = db.coletar_e_salvar(brutas, fonte="teste")
    try:
        assert len(novas) == 1                              # dedup pegou a 2a
        o = db.obter_oferta(novas[0]["id"])
        assert o["fonte"] == "teste"
        assert o["departamento_nome"] == "Fitness & Academia"   # whey -> Fitness
        assert db.obter_menor_preco("https://x/MLB-8800001-whey") == 120.0  # histórico gravado
    finally:
        db.deletar_oferta(novas[0]["id"])
