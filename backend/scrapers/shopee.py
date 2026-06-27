# -*- coding: utf-8 -*-
"""
Scraper da Shopee — via Affiliate Open API (GraphQL).

Ingestão agressiva de promoções (TASK-09):
  * Produtos (`productOfferV2`): marca `high_commission` quando a comissão passa
    do limiar (config.SHOPEE_HIGH_COMMISSION_PCT) → fila VIP de publicação.
  * Ofertas/Cupons relâmpago (`shopeeOfferV2`): captura validade (`expira_em`) e
    o cupom, priorizando o que está "expirando" e o de alta comissão.

NOTA: Requer credenciais (SHOPEE_APP_ID e SHOPEE_APP_SECRET) do painel de afiliado
da Shopee. Sem elas, todos os métodos de rede retornam lista vazia.
"""

import hashlib
import hmac
import time
import json
import datetime as dt
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

    def _post_graphql(self, query: str, variables: dict, contexto: str) -> dict | None:
        """Executa uma chamada GraphQL autenticada. Retorna o `data` ou None."""
        payload = json.dumps({"query": query, "variables": variables})
        try:
            resp = requests.post(
                config.SHOPEE_API_BASE,
                data=payload,
                headers=self._headers(payload),
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
        except requests.RequestException as e:
            print(f"[SHOPEE] Erro em {contexto}: {e}")
            return None

    # =============================================
    # PRODUTOS (productOfferV2)
    # =============================================

    def buscar(self, palavra_chave: str, limite: int = 20) -> list[dict]:
        """
        Busca produtos na Shopee Affiliate API.
        Retorna lista vazia se as credenciais não estiverem configuradas.
        """
        if not config.shopee_ok():
            print("[SHOPEE] Credenciais não configuradas. Vá ao painel de afiliado da Shopee para obter App ID e App Secret.")
            return []

        query = """
        query productOfferV2($keyword: String!, $limit: Int, $sortType: Int) {
            productOfferV2(keyword: $keyword, limit: $limit, sortType: $sortType) {
                nodes {
                    productName
                    priceMin
                    priceMax
                    priceOriginal
                    priceDiscountRate
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

        data = self._post_graphql(query, variables, f"busca por '{palavra_chave}'")
        if data is None:
            return []

        nodes = data.get("productOfferV2", {}).get("nodes", [])
        ofertas = [o for o in (self._parsear_item(n) for n in nodes) if o]
        # Alta comissão primeiro, depois maior desconto (fila de publicação VIP).
        ofertas.sort(key=lambda o: (o["high_commission"], o["desconto_pct"]), reverse=True)
        return ofertas

    # =============================================
    # OFERTAS / CUPONS RELÂMPAGO (shopeeOfferV2)
    # =============================================

    def buscar_ofertas_relampago(self, limite: int = 50) -> list[dict]:
        """Captura ofertas/cupons da Shopee com validade e selo de comissão.

        Usa `shopeeOfferV2` (ofertas de loja/cupom), que carrega janela de
        validade (periodStart/EndTime). Prioriza o que está EXPIRANDO e o de
        alta comissão — o combustível das publicações de urgência.

        NOTA (manutenção): atualmente SEM USO — nenhum job/scheduler chama este
        método (confirmado por varredura). Recomendação: ligar no scheduler de
        ingestão (junto de buscar/buscar_todas_palavras) para realmente capturar
        flash deals e cupons, OU remover se a estratégia mudar. Mantido por ser
        capacidade pronta e testada.
        """
        if not config.shopee_ok():
            print("[SHOPEE] Credenciais não configuradas — sem ofertas relâmpago.")
            return []

        query = """
        query shopeeOfferV2($limit: Int) {
            shopeeOfferV2(limit: $limit) {
                nodes {
                    commissionRate
                    imageUrl
                    offerName
                    originalLink
                    offerLink
                    periodStartTime
                    periodEndTime
                    categoryName
                }
            }
        }
        """
        data = self._post_graphql(query, {"limit": min(limite, 100)}, "ofertas relâmpago")
        if data is None:
            return []

        nodes = data.get("shopeeOfferV2", {}).get("nodes", [])
        ofertas = [o for o in (self._parsear_oferta_loja(n) for n in nodes) if o]
        # Expira mais cedo primeiro (urgência); alta comissão desempata.
        ofertas.sort(key=lambda o: (
            o["expira_em"] or dt.datetime.max,
            not o["high_commission"],
        ))
        return ofertas

    # =============================================
    # PARSERS
    # =============================================

    @staticmethod
    def _preco_float(valor) -> float:
        """Converte preço da API (string decimal em reais ou número) para float."""
        if valor in (None, ""):
            return 0.0
        try:
            return float(str(valor).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _comissao_float(valor) -> float:
        """Comissão como fração 0–1 (a API manda '0.1' = 10%)."""
        if valor in (None, ""):
            return 0.0
        try:
            return float(str(valor).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _epoch_para_dt(valor) -> dt.datetime | None:
        """Converte epoch (segundos) da janela de validade para datetime local."""
        if valor in (None, "", 0, "0"):
            return None
        try:
            return dt.datetime.fromtimestamp(int(valor))
        except (TypeError, ValueError, OSError):
            return None

    def _eh_alta_comissao(self, comissao: float) -> bool:
        """True quando a comissão cruza o limiar configurado (fila VIP)."""
        return comissao >= config.SHOPEE_HIGH_COMMISSION_PCT

    def _parsear_item(self, node: dict) -> dict | None:
        """Converte item de `productOfferV2` para o formato padronizado."""
        try:
            # productOfferV2 retorna preços como string decimal em BRL (ex "29.90").
            preco = self._preco_float(node.get("priceMin"))
            po = self._preco_float(node.get("priceOriginal"))
            preco_original = po if po > 0 else None

            desconto = self._calcular_desconto(preco, preco_original)
            # Fallback: a própria API pode mandar a taxa de desconto pronta (0–100).
            if not desconto and node.get("priceDiscountRate"):
                desconto = round(self._preco_float(node.get("priceDiscountRate")), 1)

            comissao = self._comissao_float(node.get("commissionRate"))

            return {
                "titulo": node.get("productName", "Sem título"),
                "preco": round(preco, 2),
                "preco_original": round(preco_original, 2) if preco_original else None,
                "desconto_pct": desconto,
                "loja": "Shopee",
                "link_original": node.get("productLink", ""),
                "link_afiliado": None,  # gerado pela camada de monetização (TASK-10)
                "imagem_url": node.get("imageUrl"),
                "categoria": node.get("categoryName"),
                "vendedor": node.get("shopName"),
                "reputacao": str(node.get("ratingStar", "")),
                "frete_gratis": False,
                "fonte": "shopee_api",
                "high_commission": self._eh_alta_comissao(comissao),
                "cupom": node.get("voucherCode") or node.get("couponCode"),
                "expira_em": self._epoch_para_dt(node.get("periodEndTime")),
                "dados_extra": {
                    "commission_rate": node.get("commissionRate"),
                    "sales": node.get("sales"),
                },
            }
        except Exception as e:
            print(f"[SHOPEE] Erro ao parsear item: {e}")
            return None

    def _parsear_oferta_loja(self, node: dict) -> dict | None:
        """Converte oferta/cupom de `shopeeOfferV2` (carrega validade)."""
        try:
            comissao = self._comissao_float(node.get("commissionRate"))
            expira = self._epoch_para_dt(node.get("periodEndTime"))
            return {
                "titulo": node.get("offerName", "Oferta Shopee"),
                "preco": 0.0,                 # oferta de loja/cupom: sem preço fixo
                "preco_original": None,
                "desconto_pct": 0.0,
                "loja": "Shopee",
                "link_original": node.get("originalLink") or node.get("offerLink", ""),
                "link_afiliado": node.get("offerLink"),
                "imagem_url": node.get("imageUrl"),
                "categoria": node.get("categoryName"),
                "vendedor": None,
                "reputacao": "",
                "frete_gratis": False,
                "fonte": "shopee_oferta",
                "high_commission": self._eh_alta_comissao(comissao),
                "cupom": node.get("voucherCode") or node.get("couponCode"),
                "expira_em": expira,
                "dados_extra": {
                    "commission_rate": node.get("commissionRate"),
                    "period_start": node.get("periodStartTime"),
                    "period_end": node.get("periodEndTime"),
                },
            }
        except Exception as e:
            print(f"[SHOPEE] Erro ao parsear oferta de loja: {e}")
            return None

    def gerar_link_afiliado(self, url_produto: str) -> str | None:
        """Gera link curto de afiliado para um produto.

        Mantido por compatibilidade. A geração canônica (com UTMs/sub_id) vive
        agora em backend/monetization/ (TASK-10).
        """
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
        data = self._post_graphql(query, variables, "geração de link de afiliado")
        if data is None:
            return None
        return data.get("generateShortLink", {}).get("shortLink")

    def buscar_todas_palavras(self) -> list[dict]:
        """Busca para todas as palavras-chave configuradas."""
        todas = []
        for kw in config.BUSCA_PALAVRAS_CHAVE:
            print(f"[SHOPEE] Buscando: {kw}...")
            resultados = self.buscar(kw)
            todas.extend(resultados)
            time.sleep(1)
        return todas
