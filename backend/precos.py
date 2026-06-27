# -*- coding: utf-8 -*-
"""
Revalidação de preço — fonte única usada pelo painel (postar/copiar) e pelo
agendador (auto-post). Re-busca o preço atual no ML antes de divulgar, pra
nunca postar preço velho.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from backend import database as db
from backend.config import config
from backend.scrapers.mercadolivre import MercadoLivreScraper

ml_scraper = MercadoLivreScraper()
_PRECO_CONFIRMADO_TTL = timedelta(hours=6)


def _preco_confirmado_manual(oferta: dict) -> tuple[float | None, bool]:
    """Retorna (preço, expirou) para uma confirmação feita no painel."""
    dados_extra = oferta.get("dados_extra") or {}
    if not isinstance(dados_extra, dict) or "preco_confirmado_manual" not in dados_extra:
        return None, False
    try:
        preco = float(dados_extra["preco_confirmado_manual"])
        confirmado_em = datetime.fromisoformat(str(dados_extra["preco_confirmado_em"]))
        if confirmado_em.tzinfo is None:
            confirmado_em = confirmado_em.replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None, True
    expirou = datetime.now(timezone.utc) - confirmado_em > _PRECO_CONFIRMADO_TTL
    return (None, True) if expirou or preco <= 0 else (preco, False)


def extrair_anuncio_ml_id(link: str) -> str | None:
    """Extrai o ID do anúncio (wid), diferente do ID de catálogo /p/MLB..."""
    partes = urlsplit(link or "")
    for parametros in (parse_qs(partes.query), parse_qs(partes.fragment)):
        wid = (parametros.get("wid") or [""])[0].upper()
        if wid.startswith("MLB") and wid[3:].isdigit():
            return wid
    return None


def casar_por_produto_id(link_original: str, resultados: list[dict]) -> dict | None:
    """Acha, entre os resultados, o que tem o MESMO ID de produto (MLB/Shopee).

    Só casa por ID (exato) — não faz fallback. Quem quiser fallback decide fora.
    """
    anuncio_id = extrair_anuncio_ml_id(link_original)
    if anuncio_id:
        for resultado in resultados:
            if extrair_anuncio_ml_id(resultado.get("link_original")) == anuncio_id:
                return resultado
        return None

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
    preco_manual, confirmacao_expirada = _preco_confirmado_manual(oferta)
    if confirmacao_expirada:
        return {"status": "confirmacao_expirada"}

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
    novo = preco_manual if preco_manual is not None else float(match.get("preco") or 0)
    if novo <= 0:
        return {"status": "indisponivel"}

    if preco_manual is not None:
        original_salvo = oferta.get("preco_original")
        orig = original_salvo if original_salvo and original_salvo > novo else None
    else:
        orig = match.get("preco_original")
    desc = round((orig - novo) / orig * 100, 1) if orig and orig > novo else 0

    var = ((novo - antigo) / antigo * 100) if antigo else 0
    res = {"status": "ok", "preco_antigo": antigo, "preco_novo": novo, "variacao_pct": round(var, 1)}
    if preco_manual is None and var > config.REVALIDAR_BLOQUEIO_ALTA_PCT:
        res["status"] = "subiu"
    if preco_manual is not None:
        res["fonte_preco"] = "confirmado_manual"

    dados_extra = dict(oferta.get("dados_extra") or {})
    dados_match = match.get("dados_extra")
    if isinstance(dados_match, dict):
        dados_extra.update(dados_match)
        if not dados_match.get("forma_pagamento"):
            dados_extra.pop("forma_pagamento", None)

    dados_extra.pop("parcelamento_destaque", None)
    parcelamento_manual = (dados_extra.get("parcelamento_manual") or "").strip()
    if parcelamento_manual:
        dados_extra["parcelamento_destaque"] = parcelamento_manual
    elif res["status"] == "ok":
        try:
            parcelamento = ml_scraper.buscar_parcelamento(
                match.get("link_original") or oferta.get("link_original") or ""
            )
            if parcelamento:
                dados_extra["parcelamento_destaque"] = parcelamento
        except Exception as e:
            print(f"[REVALIDA] Não foi possível consultar parcelamento: {e}")

    atualizacao = {
        "preco": novo,
        "preco_original": orig,
        "desconto_pct": desc,
        "dados_extra": dados_extra,
    }
    db.atualizar_oferta(oferta["id"], atualizacao)
    oferta.update(atualizacao)
    return res
