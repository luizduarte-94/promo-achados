# -*- coding: utf-8 -*-
"""
Scraper da Shopee — via Affiliate Open API (GraphQL).

NOTA: Este módulo requer credenciais (SHOPEE_APP_ID e SHOPEE_APP_SECRET)
obtidas no painel de afiliado da Shopee. Sem elas, retorna lista vazia.
"""

import hashlib
import hmac
import time
import json
import requests
from backend.scrapers.base import BaseScraper
from backend.config import config


class ShopeeScraper(BaseScraper):
    """Busca ofertas na Shopee via Affiliate Open API."""

    nome = "Shopee"

    def _gerar_assinatura(self, payload: str, timestamp: int) -> str:
        """Gera assinatura HMAC-SHA256 para autenticação na API."""
        factor = f"{config.SHOPEE_APP_ID}{timestamp}{payload}{config.SHOPEE_APP_SECRET}"
        return hmac.new(
            config.SHOPEE_APP_SECRET.encode("utf-8"),
            factor.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self, payload: str) -> dict:
        """Monta os headers de autenticação."""
        timestamp = int(time.time())
        signature = self._gerar_assinatura(payload, timestamp)
        return {
            "Content-Type": "application/json",
            "Authorization": f"SHA256 Credential={config.SHOPEE_APP_ID},Timestamp={timestamp},Signature={signature}",
        }

    def buscar(self, palavra_chave: str, limite: int = 20) -> list[dict]:
        """
        Busca produtos na Shopee Affiliate API.
        Retorna lista vazia se as credenciais não estiverem configuradas.
        """
        if not config.shopee_ok():
            print("[SHOPEE] Credenciais não configuradas. Pule para o painel de afiliado da Shopee para obter App ID e App Secret.")
            return []

        query = """
        query productOfferV2($keyword: String!, $limit: Int, $sortType: Int) {
            productOfferV2(keyword: $keyword, limit: $limit, sortType: $sortType) {
                nodes {
                    productName
                    priceMin
                    priceMax
                    priceOriginal
                    commissionRate
                    sales
                    productLink
                    imageUrl
                    shopName
                    categoryName
                    ratingStar
                }
            }
        }
        """

        variables = {
            "keyword": palavra_chave,
            "limit": min(limite, 50),
            "sortType": 2,  # Sort by sales
        }

        payload = json.dumps({"query": query, "variables": variables})

        try:
            resp = requests.post(
                config.SHOPEE_API_BASE,
                data=payload,
                headers=self._headers(payload),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"[SHOPEE] Erro na busca por '{palavra_chave}': {e}")
            return []

        nodes = (
            data.get("data", {})
            .get("productOfferV2", {})
            .get("nodes", [])
        )

        ofertas = []
        for node in nodes:
            oferta = self._parsear_item(node)
            if oferta:
                ofertas.append(oferta)

        ofertas.sort(key=lambda o: o["desconto_pct"], reverse=True)
        return ofertas

    def _parsear_item(self, node: dict) -> dict | None:
        """Converte item da API Shopee para formato padronizado."""
        try:
            preco = float(node.get("priceMin", 0)) / 100000  # Shopee retorna em centavos * 1000
            preco_original = float(node.get("priceOriginal", 0)) / 100000 if node.get("priceOriginal") else None

            desconto = self._calcular_desconto(preco, preco_original)

            return {
                "titulo": node.get("productName", "Sem título"),
                "preco": round(preco, 2),
                "preco_original": round(preco_original, 2) if preco_original else None,
                "desconto_pct": desconto,
                "loja": "Shopee",
                "link_original": node.get("productLink", ""),
                "link_afiliado": None,  # Será gerado via generateShortLink
                "imagem_url": node.get("imageUrl"),
                "categoria": node.get("categoryName"),
                "vendedor": node.get("shopName"),
                "reputacao": str(node.get("ratingStar", "")),
                "frete_gratis": False,
                "fonte": "shopee_api",
                "dados_extra": {
                    "commission_rate": node.get("commissionRate"),
                    "sales": node.get("sales"),
                },
            }
        except Exception as e:
            print(f"[SHOPEE] Erro ao parsear item: {e}")
            return None

    def gerar_link_afiliado(self, url_produto: str) -> str | None:
        """Gera link curto de afiliado para um produto."""
        if not config.shopee_ok():
            return None

        query = """
        mutation generateShortLink($url: String!) {
            generateShortLink(input: { url: $url }) {
                shortLink
            }
        }
        """
        variables = {"url": url_produto}
        payload = json.dumps({"query": query, "variables": variables})

        try:
            resp = requests.post(
                config.SHOPEE_API_BASE,
                data=payload,
                headers=self._headers(payload),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("generateShortLink", {}).get("shortLink")
        except Exception as e:
            print(f"[SHOPEE] Erro ao gerar link de afiliado: {e}")
            return None

    def buscar_todas_palavras(self) -> list[dict]:
        """Busca para todas as palavras-chave configuradas."""
        todas = []
        for kw in config.BUSCA_PALAVRAS_CHAVE:
            print(f"[SHOPEE] Buscando: {kw}...")
            resultados = self.buscar(kw)
            todas.extend(resultados)
            time.sleep(1)
        return todas
