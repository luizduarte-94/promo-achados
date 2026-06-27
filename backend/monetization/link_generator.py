# -*- coding: utf-8 -*-
"""
Motor de Afiliados e Tracking (TASK-10).

Recebe uma URL crua + canal de destino + produto_id e devolve a URL final de
afiliado, com:
  * UTMs (`utm_source=<canal>`, `utm_medium`, `utm_campaign`) — atribuição padrão;
  * `sub_id` — tracking nativo da Shopee (identifica canal + produto no relatório);
  * shortlink da Shopee (quando há credencial) — encurta links longos sem perder
    o sub_id.

Regras (docs/PROJECT.md):
  - Nenhum clique sem rastreio: todo link ingerido passa por aqui antes de salvar.
  - Canal identifica a origem do clique: telegram, whatsapp, instagram, site.

Sem dependência do scheduler nem dos canais — é serviço puro (urllib + config).
A chamada de rede (shortlink Shopee) é isolada e degrada para o link longo
rastreado quando não há credencial ou a API falha.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import requests

from backend.config import config


CANAIS_VALIDOS = ("telegram", "whatsapp", "instagram", "site")


def montar_sub_id(canal: str | None, produto_id: str | int | None) -> str:
    """Compõe o sub_id (tracking nativo Shopee): '<canal>_<produto_id>'.

    Mantém só [a-z0-9_], minúsculo, limitado a 50 chars (limite de sub_id).
    """
    partes = [str(p) for p in (canal, produto_id) if p not in (None, "")]
    bruto = "_".join(partes).lower()
    limpo = re.sub(r"[^a-z0-9_]+", "", bruto)
    return limpo[:50]


def aplicar_utms(url: str, **params: str) -> str:
    """Adiciona/atualiza parâmetros de query na URL (sobrescreve chaves existentes).

    Idempotente: chamar de novo com o mesmo `utm_source` não duplica o parâmetro.
    Ignora params com valor vazio/None.
    """
    if not url:
        return url
    partes = urlparse(url)
    query = dict(parse_qsl(partes.query, keep_blank_values=False))
    for chave, valor in params.items():
        if valor in (None, ""):
            continue
        query[chave] = str(valor)
    nova_query = urlencode(query)
    return urlunparse(partes._replace(query=nova_query))


def _eh_shopee(url: str) -> bool:
    return "shopee." in (urlparse(url).netloc or url).lower()


def eh_link_afiliado_ml(url: str | None) -> bool:
    """True somente para o shortlink comissionado gerado pelo Mercado Livre."""
    if not url:
        return False
    partes = urlparse(str(url).strip())
    return (
        partes.scheme == "https"
        and (partes.hostname or "").lower() == "meli.la"
        and bool(partes.path.strip("/"))
    )


def oferta_tem_link_afiliado_valido(oferta: dict) -> bool:
    """Valida monetização; Mercado Livre exige meli.la, outras lojas exigem URL."""
    link = (oferta.get("link_afiliado") or "").strip()
    if not link:
        return False
    if (oferta.get("loja") or "").strip().lower() == "mercado livre":
        return eh_link_afiliado_ml(link)
    partes = urlparse(link)
    return partes.scheme in ("http", "https") and bool(partes.hostname)


class LinkGenerator:
    """Converte URLs cruas em links de afiliado rastreáveis (ponto único)."""

    def gerar(
        self,
        url: str,
        canal: str | None = None,
        produto_id: str | int | None = None,
        encurtar: bool = True,
    ) -> str:
        """Retorna a URL final de afiliado, rastreada e (quando dá) encurtada.

        - `canal`: telegram/whatsapp/instagram/site. Vira `utm_source` e entra no
          `sub_id`. Se None, usa AFILIADO_CANAL_PADRAO (o que o site consome).
        - `produto_id`: ID canônico (MLB.../shopee...) p/ compor o sub_id.
        - `encurtar`: tenta shortlink Shopee (se credencial e habilitado).
        """
        if not url:
            return url

        canal = (canal or config.AFILIADO_CANAL_PADRAO).lower()
        sub_id = montar_sub_id(canal, produto_id)

        rastreada = aplicar_utms(
            url,
            utm_source=canal,
            utm_medium=config.UTM_MEDIUM,
            utm_campaign=config.UTM_CAMPAIGN,
            sub_id=sub_id,
        )

        if encurtar and _eh_shopee(url) and config.AFILIADO_ENCURTAR_SHOPEE:
            curto = self._encurtar_shopee(rastreada, sub_id)
            if curto:
                return curto

        return rastreada

    # --- Shortlink Shopee (Affiliate Open API) -------------------------------

    def _encurtar_shopee(self, url: str, sub_id: str) -> str | None:
        """Gera shortlink Shopee carregando o sub_id. None se sem credencial/erro."""
        if not config.shopee_ok():
            return None

        query = """
        mutation generateShortLink($input: ShortLinkInput!) {
            generateShortLink(input: $input) {
                shortLink
            }
        }
        """
        variables = {"input": {"originUrl": url, "subIds": [sub_id] if sub_id else []}}
        payload = json.dumps({"query": query, "variables": variables})

        try:
            resp = requests.post(
                config.SHOPEE_API_BASE,
                data=payload,
                headers=self._headers_shopee(payload),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return (data.get("generateShortLink") or {}).get("shortLink")
        except requests.RequestException as e:
            print(f"[MONETIZACAO] Falha ao encurtar Shopee (mantendo link longo): {e}")
            return None

    @staticmethod
    def _headers_shopee(payload: str) -> dict:
        """Assinatura HMAC-SHA256 da Affiliate Open API da Shopee."""
        timestamp = int(time.time())
        factor = f"{config.SHOPEE_APP_ID}{timestamp}{payload}{config.SHOPEE_APP_SECRET}"
        assinatura = hmac.new(
            config.SHOPEE_APP_SECRET.encode("utf-8"),
            factor.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "Content-Type": "application/json",
            "Authorization": (
                f"SHA256 Credential={config.SHOPEE_APP_ID},"
                f"Timestamp={timestamp},Signature={assinatura}"
            ),
        }


# Instância/funç. de conveniência (uso direto pelos canais na TASK-12).
_gerador = LinkGenerator()


def gerar_link_afiliado(
    url: str,
    canal: str | None = None,
    produto_id: str | int | None = None,
    encurtar: bool = True,
) -> str:
    """Atalho para LinkGenerator().gerar(...)."""
    return _gerador.gerar(url, canal=canal, produto_id=produto_id, encurtar=encurtar)
