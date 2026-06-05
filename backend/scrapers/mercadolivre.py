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

            # 3. Preço e Preço Original
            # Original
            original_el = item.select_one('s.andes-money-amount--previous .andes-money-amount__fraction')
            preco_original = None
            if original_el:
                po_str = original_el.text.replace('.', '').replace(',', '.')
                preco_original = float(po_str) if po_str else None

            # Atual
            current_el = item.select_one('.poly-price__current .andes-money-amount__fraction') or item.select_one('.ui-search-price--size-medium .andes-money-amount__fraction')
            preco = 0.0
            if current_el:
                p_str = current_el.text.replace('.', '').replace(',', '.')
                preco = float(p_str) if p_str else 0.0
                
            # Fallback se não encontrou o elemento de preço atual específico
            if preco == 0.0:
                todas_fractions = item.select('.andes-money-amount__fraction')
                if todas_fractions:
                    # Se houver mais de um, geralmente o segundo é o atual quando tem desconto
                    idx = 1 if preco_original and len(todas_fractions) > 1 else 0
                    p_str = todas_fractions[idx].text.replace('.', '').replace(',', '.')
                    preco = float(p_str) if p_str else 0.0

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
            # Silencia erros individuais para não poluir log, apenas ignora o item
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
