# -*- coding: utf-8 -*-
"""
Legendas (captions) do Instagram — conteúdo puro, sem chamadas de API.

Separa a montagem do texto da orquestração da Graph API (backend/channels/
instagram.py). Funções puras = fáceis de testar e reusar (Feed e Carrossel).
Stories não levam caption (o CTA é o link sticker), por isso não há função aqui.
"""

from __future__ import annotations

HASHTAGS = (
    "#promoção #oferta #desconto #achados #promoachados "
    "#ofertas #promocao #mercadolivre #shopee #barato #compraonline"
)


def formatar_preco(preco: float) -> str:
    """Formata preço em Real brasileiro (R$ 1.234,56)."""
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _chamada_urgencia(desconto: float) -> str:
    if desconto >= 40:
        return "🔥 OFERTA IMPERDÍVEL 🔥"
    if desconto >= 25:
        return "‼️ PREÇO BAIXOU ‼️"
    return "💰 ACHADO DO DIA 💰"


def caption_feed(oferta: dict) -> str:
    """Caption de post único (Feed). CTA: comentar palavra-chave / link na bio."""
    desconto = oferta.get("desconto_pct", 0)
    linhas = [_chamada_urgencia(desconto), ""]

    linhas.append(f"📦 {oferta['titulo']}")
    linhas.append("")

    preco_fmt = formatar_preco(oferta["preco"])
    if oferta.get("preco_original") and oferta["preco_original"] > oferta["preco"]:
        linhas.append(f"De: {formatar_preco(oferta['preco_original'])}")
        linhas.append(f"Por: {preco_fmt} 🏷️")
        linhas.append(f"📉 {desconto:.0f}% OFF!")
    else:
        linhas.append(f"Por: {preco_fmt}")
    linhas.append("")

    cupom = (oferta.get("dados_extra") or {}).get("cupom") or oferta.get("cupom")
    if cupom:
        linhas.append(f"🎟️ Cupom: {cupom}")
        linhas.append("")

    if oferta.get("frete_gratis"):
        linhas.append("🚚 Frete Grátis!")
        linhas.append("")

    linhas.append(f"🏪 {oferta.get('loja', 'Loja')}")
    linhas.append("💬 Comente *EU QUERO* que mando o link na sua DM!")
    linhas.append("🔗 Ou pega o link na bio.")
    linhas.append("")
    linhas.append("⏰ Promoção por tempo limitado!")
    linhas.append("")
    linhas.append(HASHTAGS)
    return "\n".join(linhas)


def caption_carrossel(ofertas: list[dict], titulo: str = "🛒 TOP OFERTAS DO DIA") -> str:
    """Caption do Carrossel: lista enxuta das ofertas (ML + Shopee misturados)."""
    linhas = [titulo, ""]
    for i, o in enumerate(ofertas, start=1):
        preco_fmt = formatar_preco(o["preco"])
        desconto = o.get("desconto_pct", 0)
        sufixo = f" ({desconto:.0f}% OFF)" if desconto >= 10 else ""
        linhas.append(f"{i}. {o['titulo']} — {preco_fmt}{sufixo}")
    linhas.append("")
    linhas.append("💬 Comente o número do que te interessou!")
    linhas.append("🔗 Links na bio.")
    linhas.append("")
    linhas.append(HASHTAGS)
    return "\n".join(linhas)
