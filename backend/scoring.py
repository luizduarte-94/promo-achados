# -*- coding: utf-8 -*-
"""
Pontuação de ofertas — decide quais têm maior potencial de venda.

Função pura (sem I/O): recebe um dict de oferta e devolve um score 0..100.
Usada pelo agendador para priorizar/filtrar o que vale auto-postar.
"""


def score_oferta(oferta: dict) -> int:
    """Calcula um score de 0 a 100 para uma oferta.

    Componentes (somados e limitados a 100):
      - Desconto:        até 50 pts (40% OFF ou mais = teto)
      - Cupom presente:  +15 pts
      - Frete grátis:    +10 pts
      - Loja/vendedor:   +10 pts (tem vendedor identificado)
      - Faixa de preço:  +15 pts (preço "comprável", penaliza caro)
    """
    score = 0.0

    desconto = float(oferta.get("desconto_pct") or 0)
    # 40% OFF satura os 50 pts; linear até lá.
    score += min(desconto, 40) / 40 * 50

    dados_extra = oferta.get("dados_extra") or {}
    if isinstance(dados_extra, dict) and (dados_extra.get("cupom") or "").strip():
        score += 15

    if oferta.get("frete_gratis"):
        score += 10

    if (oferta.get("vendedor") or "").strip():
        score += 10

    preco = float(oferta.get("preco") or 0)
    if 0 < preco <= 150:
        score += 15
    elif preco <= 300:
        score += 10
    elif preco <= 500:
        score += 5

    return int(round(min(score, 100)))
