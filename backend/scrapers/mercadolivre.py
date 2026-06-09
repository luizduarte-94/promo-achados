# -*- coding: utf-8 -*-
"""
Scraper do Mercado Livre — via BeautifulSoup (Plano B).

Implementa o "Plano B": scraping do HTML SSR do ML (entregue a crawlers tipo
Googlebot) com proteção anti-bloqueio — ritmo com jitter entre requisições e
cooldown automático ao detectar bloqueio (HTTP 403/429).
"""

import random
import threading
import time
import requests
import bs4
from backend.scrapers.base import BaseScraper
from backend.config import config

# --- Rate limiting global (compartilhado entre agendador e API) ---
_REQUEST_LOCK = threading.Lock()
_ultimo_request = 0.0       # timestamp da última requisição
_cooldown_ate = 0.0         # se > agora, está em cooldown anti-bloqueio
_INTERVALO_MIN = 4.0        # segundos mínimos entre requisições
_INTERVALO_MAX = 8.0        # teto do jitter
_COOLDOWN_BLOQUEIO = 900    # 15 min de pausa ao detectar bloqueio


class MercadoLivreScraper(BaseScraper):
    """Busca ofertas no Mercado Livre via Scraping HTML (Plano B)."""

    nome = "Mercado Livre"

    # IMPORTANTE: o ML só entrega o HTML renderizado (SSR, com os itens da busca)
    # para crawlers tipo Googlebot. Com User-Agent de navegador comum a página vem
    # sem os resultados (depende de JS) e o scraping retorna 0. Por isso o UA de
    # Googlebot é necessário para o "Plano B" funcionar — a proteção anti-bloqueio
    # vem do ritmo/cooldown em _fetch, não de esconder o UA.
    # Accept-Encoding sem 'br': o requests não decodifica brotli sem a lib extra.
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
    }

    def __init__(self):
        pass

    def _fetch(self, url: str):
        """Requisição protegida: ritmo com jitter + cooldown em bloqueio.

        Serializa as requisições (lock global) para nunca disparar em rajada,
        respeita um intervalo aleatório entre chamadas e, ao detectar bloqueio
        (HTTP 403/429), entra em cooldown e devolve None.
        """
        global _ultimo_request, _cooldown_ate
        with _REQUEST_LOCK:
            agora = time.time()
            if agora < _cooldown_ate:
                restante = int(_cooldown_ate - agora)
                print(f"[ML] Em cooldown anti-bloqueio ({restante}s restantes). Requisição pulada.")
                return None

            espera = (_ultimo_request + random.uniform(_INTERVALO_MIN, _INTERVALO_MAX)) - agora
            if espera > 0:
                time.sleep(espera)

            try:
                resp = requests.get(url, headers=self.HEADERS, timeout=15)
            except requests.RequestException as e:
                _ultimo_request = time.time()
                print(f"[ML] Erro de rede: {e}")
                return None

            _ultimo_request = time.time()

            if resp.status_code in (403, 429):
                _cooldown_ate = time.time() + _COOLDOWN_BLOQUEIO
                print(
                    f"[ML] Possível bloqueio (HTTP {resp.status_code}). "
                    f"Pausando scraping por {_COOLDOWN_BLOQUEIO // 60} min."
                )
                return None
            if resp.status_code != 200:
                print(f"[ML] Resposta inesperada (HTTP {resp.status_code}).")
                return None
            return resp

    def buscar(self, palavra_chave: str, limite: int = 20, filtrar_qualidade: bool = True) -> list[dict]:
        """
        Busca produtos no ML via HTML scraping.

        Por padrao filtra por desconto minimo e preco maximo. Passe
        filtrar_qualidade=False para obter o preco bruto de todos os itens
        (usado pelo monitoramento de recorrentes, que precisa do preco
        independente de desconto).
        """
        url = f"https://lista.mercadolivre.com.br/{palavra_chave.replace(' ', '-')}"

        resp = self._fetch(url)
        if resp is None:
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
            a_tag = item.select_one('a.poly-component__title')
            if not a_tag:
                titulo_el = item.select_one('.ui-search-item__title')
                a_tag = titulo_el.parent if titulo_el else None
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
        """Busca para todas as palavras-chave configuradas.

        O ritmo entre requisições é controlado por _fetch (jitter global),
        então não há sleep extra aqui.
        """
        todas = []
        for kw in config.BUSCA_PALAVRAS_CHAVE:
            print(f"[ML Plano B] Buscando: {kw}...")
            todas.extend(self.buscar(kw))
        return todas
