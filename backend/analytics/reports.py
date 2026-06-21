# -*- coding: utf-8 -*-
"""
Motor de Relatórios — consolidação de cliques x ofertas (TASK-16).

Cruza `click_events` (TASK-13/14) com `ofertas` para produzir um resumo estável,
fácil de consumir por um dashboard:

  * total de cliques e cliques por canal;
  * top ofertas por volume de cliques;
  * faturamento estimado por canal (comissão potencial dos cliques);
  * EPC por canal = faturamento_estimado / total_de_cliques;
  * CTR: NÃO é calculado — não há fonte confiável de impressões instrumentada.
    Em vez de inventar, o JSON declara isso explicitamente (`disponivel=False`).

Honestidade dos números (regra do projeto): nada é fabricado. A comissão vem de
`oferta.dados_extra.commission_rate` (fração 0–1, vinda da ingestão Shopee). Onde
não há esse dado (ex.: Mercado Livre), o clique não entra na soma de faturamento e
isso é reportado como cobertura, para o consumidor saber a confiabilidade.

Persistência: usa SEMPRE o engine atual de backend.database (reaponta nos testes).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from backend import database as db
from backend.models import ClickEvent, Oferta, Postagem, criar_session_factory


# Premissa do faturamento estimado deixada explícita no payload (sem rastreio de
# conversão real, assumimos no máximo 1 venda por clique p/ a comissão potencial).
_METODOLOGIA = {
    "faturamento_estimado": (
        "Soma, por clique, da comissão potencial da oferta clicada "
        "(preco * commission_rate de dados_extra). NÃO há rastreio de conversão "
        "real: assume-se no máximo 1 venda por clique. Cliques de ofertas sem "
        "commission_rate não entram na soma (ver cobertura_comissao_pct)."
    ),
    "epc": "faturamento_estimado / total_de_cliques do canal.",
    "ctr": (
        "Requer impressões/disparos confiáveis por canal, ainda não "
        "instrumentados. Por isso não é calculado (disponivel=False)."
    ),
}


def _commission_rate(oferta_row) -> float | None:
    """Extrai a taxa de comissão (fração 0–1) de dados_extra. None se ausente."""
    dados_extra = oferta_row.dados_extra if isinstance(oferta_row.dados_extra, dict) else {}
    raw = dados_extra.get("commission_rate")
    if raw in (None, ""):
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


def gerar_resumo(limite: int = 10, dias: int | None = None) -> dict:
    """Gera o resumo analítico cruzando click_events x ofertas.

    Args:
        limite: nº de ofertas no ranking "top_ofertas".
        dias: se informado, considera só cliques dos últimos N dias.
    """
    Session = criar_session_factory(db.get_engine())
    with Session() as s:
        filtro_data = []
        if dias is not None:
            corte = datetime.now() - timedelta(days=dias)
            filtro_data.append(ClickEvent.created_at >= corte)

        # 1) Cliques por canal.
        stmt_canal = select(ClickEvent.canal, func.count()).group_by(ClickEvent.canal)
        for f in filtro_data:
            stmt_canal = stmt_canal.where(f)
        cliques_por_canal = {canal: n for canal, n in s.execute(stmt_canal).all()}
        total_cliques = sum(cliques_por_canal.values())

        # 2) Cliques por (canal, oferta) — base p/ top ofertas e faturamento.
        stmt_co = (
            select(ClickEvent.canal, ClickEvent.oferta_id, func.count())
            .group_by(ClickEvent.canal, ClickEvent.oferta_id)
        )
        for f in filtro_data:
            stmt_co = stmt_co.where(f)
        linhas_co = s.execute(stmt_co).all()

        # Ofertas referenciadas (sem FK: a oferta pode ter sido removida).
        ids = {oid for _, oid, _ in linhas_co}
        ofertas = {}
        if ids:
            for o in s.scalars(select(Oferta).where(Oferta.id.in_(ids))).all():
                ofertas[o.id] = o

        # 3) Top ofertas por volume de cliques (soma entre canais).
        cliques_por_oferta: dict[int, int] = {}
        for _canal, oid, n in linhas_co:
            cliques_por_oferta[oid] = cliques_por_oferta.get(oid, 0) + n

        top_ofertas = []
        for oid, n in sorted(cliques_por_oferta.items(), key=lambda kv: kv[1], reverse=True)[:limite]:
            o = ofertas.get(oid)
            top_ofertas.append({
                "oferta_id": oid,
                "titulo": o.titulo if o else None,
                "loja": o.loja if o else None,
                "removida": o is None,
                "cliques": n,
            })

        # 4) Faturamento estimado por canal + cobertura de comissão.
        fat: dict[str, float] = {c: 0.0 for c in cliques_por_canal}
        cliques_com_comissao: dict[str, int] = {c: 0 for c in cliques_por_canal}
        for canal, oid, n in linhas_co:
            o = ofertas.get(oid)
            if not o:
                continue
            rate = _commission_rate(o)
            if rate is None or o.preco is None:
                continue
            fat[canal] += n * (o.preco * rate)
            cliques_com_comissao[canal] += n

        faturamento_por_canal = {}
        epc_por_canal = {}
        for canal, cliques in cliques_por_canal.items():
            comissao = round(fat.get(canal, 0.0), 2)
            com_dado = cliques_com_comissao.get(canal, 0)
            faturamento_por_canal[canal] = {
                "comissao_estimada": comissao,
                "cliques": cliques,
                "cliques_com_comissao": com_dado,
                "cobertura_comissao_pct": round(100 * com_dado / cliques, 1) if cliques else 0.0,
            }
            epc_por_canal[canal] = round(comissao / cliques, 4) if cliques else None

        # 5) Disparos por canal (tabela postagens) — contexto p/ futuro CTR.
        #    NÃO são impressões; servem só de referência. CTR segue indisponível.
        disparos_por_canal = {
            canal: n
            for canal, n in s.execute(
                select(Postagem.canal, func.count())
                .where(Postagem.sucesso.is_(True))
                .group_by(Postagem.canal)
            ).all()
        }

    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "filtro_dias": dias,
        "totais": {
            "cliques": total_cliques,
            "ofertas_com_clique": len(cliques_por_oferta),
            "canais": len(cliques_por_canal),
        },
        "cliques_por_canal": cliques_por_canal,
        "top_ofertas": top_ofertas,
        "ctr": {
            "disponivel": False,
            "valor": None,
            "motivo": (
                "Depende de impressões/disparos confiáveis por canal, ainda não "
                "instrumentados no projeto. Não calculado para não fabricar dado."
            ),
        },
        "faturamento_estimado_por_canal": faturamento_por_canal,
        "epc_por_canal": epc_por_canal,
        "disparos_por_canal": disparos_por_canal,
        "metodologia": _METODOLOGIA,
    }
