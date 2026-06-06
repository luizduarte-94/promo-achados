# -*- coding: utf-8 -*-
"""
Scraper do Mercado Livre — via BeautifulSoup (Plano B).

Implementa o "Plano B" de scraping: usar scraping de HTML via BeautifulSoup
simulando o Googlebot para ignorar a restrição de token (Erro 403) da API oficial.
"""

import time
import requests
import bs4
from backend.scrapers.base import BaseScraper
from backend.config import config
from backend import database as db

class MercadoLivreScraper(BaseScraper):
    """Busca ofertas no Mercado Livre via Scraping HTML (Plano B)."""

    nome = "Mercado Livre"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self):
        pass

    def buscar(self, palavra_chave: str, limite: int = 20, filtrar_qualidade: bool = True) -> list[dict]:
        """
        Busca produtos no ML via HTML scraping.

        Por padrao filtra por desconto minimo e preco maximo. Passe
        filtrar_qualidade=False para obter o preco bruto de todos os itens
        (usado pelo monitoramento de recorrentes, que precisa do preco
        independente de desconto).
        """
        url = f"https://lista.mercadolivre.com.br/{palavra_chave.replace(' ', '-')}"

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[ML Plano B] Erro na requisição HTML por '{palavra_chave}': {e}")
            return []

        soup = bs4.BeautifulSoup(resp.text, 'html.parser')
        resultados_brutos = soup.select('li.ui-search-layout__item')
        ofertas = []

        for item in resultados_brutos[:50]:  # Máximo de 50 resultados analisados
            oferta = self._parsear_item(item)
            if oferta and (not filtrar_qualidade or self._filtro_qualidade(oferta)):
                ofertas.append(oferta)

            if len(ofertas) >= limite:
                break

        # Ordena por maior desconto
        ofertas.sort(key=lambda o: o["desconto_pct"], reverse=True)

        return ofertas

    @staticmethod
    def _extrair_money(el) -> float | None:
        """Extrai o valor de um bloco .andes-money-amount (fraction + cents).

        Combina parte inteira e centavos e remove o separador de milhar
        (ex.: '1.299' + '90' -> 1299.90). Retorna None se não houver preço.
        """
        if not el:
            return None
        frac = el.select_one('.andes-money-amount__fraction')
        if not frac:
            return None
        inteiro = frac.text.strip().replace('.', '')  # remove separador de milhar
        cents_el = el.select_one('.andes-money-amount__cents')
        cents = cents_el.text.strip() if cents_el else '00'
        try:
            return float(f"{inteiro}.{cents or '00'}")
        except ValueError:
            return None

    def _parsear_item(self, item: bs4.element.Tag) -> dict | None:
        """Extrai as informações de um elemento HTML do produto."""
        try:
            # 1. Título e Link
            a_tag = item.select_one('a.poly-component__title') or item.select_one('.ui-search-item__title').parent
            if not a_tag:
                return None
                
            titulo = a_tag.text.strip()
            link = a_tag.get('href', '')

            # 2. Imagem
            img = item.select_one('img.poly-component__picture') or item.select_one('img.ui-search-result-image__element')
            imagem = img.get('src') or img.get('data-src') if img else ''
            
            # Tenta pegar uma imagem de maior qualidade
            if imagem and "D_Q_NP_" in imagem:
                imagem = imagem.replace("D_Q_NP_", "D_NQ_NP_").replace("-V.webp", "-O.webp").replace("-E.webp", "-O.webp")

            # 3. Preço atual e original (fraction + cents, escopado ao bloco certo)
            cur_el = (item.select_one('.poly-price__current .andes-money-amount')
                      or item.select_one('.ui-search-price--size-medium .andes-money-amount'))
            preco = self._extrair_money(cur_el) or 0.0

            prev_el = item.select_one('s.andes-money-amount--previous')
            preco_original = self._extrair_money(prev_el)

            if preco <= 0:
                return None

            # 4. Frete Grátis
            frete_gratis_el = item.select_one('.poly-component__shipping')
            frete_gratis = False
            if frete_gratis_el and "grátis" in frete_gratis_el.text.lower():
                frete_gratis = True

            # 5. Vendedor (Loja Oficial ou nome)
            vendedor_el = item.select_one('.poly-component__seller')
            vendedor = vendedor_el.text.strip().replace("por ", "") if vendedor_el else ""

            # 6. Cupom de Desconto
            cupom_el = item.select_one('.poly-coupons__pill')
            cupom = cupom_el.text.strip() if cupom_el else ""

            # 7. Parcelamento e PIX
            pagamento_info = []
            current_el_full = item.select_one('.poly-price__current')
            if current_el_full and "pix" in current_el_full.text.lower():
                pagamento_info.append("no PIX")
                
            installments_el = item.select_one('.poly-price__installments')
            if installments_el:
                pagamento_info.append(installments_el.text.strip())
                
            forma_pagamento = " | ".join(pagamento_info)

            desconto = self._calcular_desconto(preco, preco_original)

            return {
                "titulo": titulo,
                "preco": preco,
                "preco_original": preco_original,
                "desconto_pct": desconto,
                "loja": "Mercado Livre",
                "link_original": link,
                "link_afiliado": None,
                "imagem_url": imagem,
                "categoria": "",
                "vendedor": vendedor,
                "reputacao": "",
                "frete_gratis": frete_gratis,
                "fonte": "mercadolivre_scraping",
                "dados_extra": {
                    "cupom": cupom,
                    "forma_pagamento": forma_pagamento
                },
            }
        except Exception as e:
            # Ignora o item com erro, mas registra para diagnóstico (sem derrubar a busca).
            print(f"[ML Plano B] Falha ao parsear item: {type(e).__name__}: {e}")
            return None

    def _filtro_qualidade(self, oferta: dict) -> bool:
        """Filtra ofertas por desconto minimo e preco maximo."""
        if oferta["desconto_pct"] < config.BUSCA_DESCONTO_MINIMO:
            return False
        if config.BUSCA_PRECO_MAXIMO > 0 and oferta["preco"] > config.BUSCA_PRECO_MAXIMO:
            return False
        return True

    def buscar_todas_palavras(self) -> list[dict]:
        """Busca para todas as palavras-chave configuradas."""
        todas = []
        for kw in config.BUSCA_PALAVRAS_CHAVE:
            print(f"[ML Plano B] Buscando: {kw}...")
            resultados = self.buscar(kw)
            todas.extend(resultados)
            
            # Rate limiting humanizado: Pausa aleatória entre 3 e 7 segundos
            import random
            espera = random.uniform(3.0, 7.0)
            time.sleep(espera)
        return todas
