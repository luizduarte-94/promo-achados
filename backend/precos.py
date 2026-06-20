# -*- coding: utf-8 -*-
"""
Revalidação de preço — fonte única usada pelo painel (postar/copiar) e pelo
agendador (auto-post). Re-busca o preço atual no ML antes de divulgar, pra
nunca postar preço velho.
"""

from backend import database as db
from backend.config import config
from backend.scrapers.mercadolivre import MercadoLivreScraper

ml_scraper = MercadoLivreScraper()


def casar_por_produto_id(link_original: str, resultados: list[dict]) -> dict | None:
    """Acha, entre os resultados, o que tem o MESMO ID de produto (MLB/Shopee).

    Só casa por ID (exato) — não faz fallback. Quem quiser fallback decide fora.
    """
    pid = db.extrair_produto_id(link_original)
    if not pid:
        return None
    for r in resultados:
        if db.extrair_produto_id(r.get("link_original")) == pid:
            return r
    return None


def revalidar_preco(oferta: dict) -> dict:
    """Re-busca o preço atual da oferta no ML e atualiza o banco se mudou.

    Muta `oferta` (preco/preco_original/desconto_pct) com o valor atual e
    persiste. Retorna status:
      - "ok"          : preço igual ou caiu (segue normal)
      - "subiu"       : subiu além do limite -> chamador deve BLOQUEAR
      - "sumiu"       : produto não encontrado agora -> chamador deve BLOQUEAR
      - "indisponivel": não deu pra revalidar (flag off / sem título / rede) -> segue com aviso
    """
    if not config.REVALIDAR_PRECO_ENABLED:
        return {"status": "indisponivel"}

    titulo = (oferta.get("titulo") or "").strip()
    if not titulo:
        return {"status": "indisponivel"}

    try:
        resultados = ml_scraper.buscar(titulo, filtrar_qualidade=False)
    except Exception as e:
        print(f"[REVALIDA] Erro ao revalidar '{titulo}': {e}")
        return {"status": "indisponivel"}

    match = casar_por_produto_id(oferta.get("link_original"), resultados)
    if not match:
        return {"status": "sumiu"}

    antigo = float(oferta.get("preco") or 0)
    novo = float(match.get("preco") or 0)
    if novo <= 0:
        return {"status": "indisponivel"}

    orig = match.get("preco_original")
    desc = round((orig - novo) / orig * 100, 1) if orig and orig > novo else 0
    db.atualizar_oferta(oferta["id"], {"preco": novo, "preco_original": orig, "desconto_pct": desc})
    oferta["preco"], oferta["preco_original"], oferta["desconto_pct"] = novo, orig, desc

    var = ((novo - antigo) / antigo * 100) if antigo else 0
    res = {"status": "ok", "preco_antigo": antigo, "preco_novo": novo, "variacao_pct": round(var, 1)}
    if var > config.REVALIDAR_BLOQUEIO_ALTA_PCT:
        res["status"] = "subiu"
    return res
