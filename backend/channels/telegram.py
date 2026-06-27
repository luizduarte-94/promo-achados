# -*- coding: utf-8 -*-
"""
Canal Telegram — envio de ofertas via Bot API.

CORRIGIDO: agora usa parse_mode HTML com escape dos campos dinamicos.
Isso evita o erro "can't parse entities" quando o titulo do produto tem
caracteres especiais como _ * [ ] etc.
"""

import html
import requests
from backend.channels.base import BaseChannel
from backend.config import config
from backend.analytics import montar_link_redirect


class TelegramChannel(BaseChannel):
    """Envia ofertas para canal/grupo do Telegram."""

    nome = "telegram"

    def __init__(self):
        self.api_base = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
        self.chat_id = config.TELEGRAM_CHAT_ID

    def esta_configurado(self) -> bool:
        return config.telegram_ok()

    def enviar(self, oferta: dict) -> dict:
        """Envia oferta formatada para o canal OFICIAL do Telegram."""
        if not self.esta_configurado():
            return {"sucesso": False, "resposta": "Token do Telegram nao configurado."}
        return self._postar(oferta, self.chat_id)

    def enviar_teste(self, oferta: dict) -> dict:
        """Posta a oferta no canal de TESTE (TELEGRAM_TEST_CHAT_ID).

        Segurança: NUNCA usa o TELEGRAM_CHAT_ID oficial. Se o canal de teste não
        estiver configurado, retorna instrução clara SEM tentar enviar nada.
        """
        if not self.esta_configurado():
            return {"sucesso": False, "resposta": "Token do Telegram nao configurado."}
        if not config.TELEGRAM_TEST_CHAT_ID:
            return {
                "sucesso": False,
                "resposta": (
                    "Canal de teste não configurado. Defina TELEGRAM_TEST_CHAT_ID "
                    "(ex.: id de um grupo/privado só seu) no ambiente. O envio de "
                    "teste nunca usa o canal oficial."
                ),
            }
        return self._postar(oferta, config.TELEGRAM_TEST_CHAT_ID)

    def _postar(self, oferta: dict, chat_id: str) -> dict:
        """Monta e envia o post para um chat_id específico (oficial ou de teste)."""
        texto = self._montar_post(oferta)
        imagem_url = oferta.get("imagem_url")
        link = self._link_rastreado(oferta)
        try:
            if imagem_url:
                return self._enviar_com_imagem(texto, imagem_url, link, chat_id=chat_id)
            return self._enviar_texto(texto, link, chat_id=chat_id)
        except Exception as e:
            return {"sucesso": False, "resposta": f"Erro inesperado: {e}"}

    @staticmethod
    def _esc(texto) -> str:
        """Escapa caracteres especiais de HTML (<, >, &) para o Telegram."""
        return html.escape(str(texto), quote=False)

    def _link_rastreado(self, oferta: dict) -> str:
        """Link curto do redirecionador próprio /r/{id}?c=telegram (TASK-15).

        Em vez do link de afiliado direto, manda o usuário ao nosso /r/, que
        registra o clique e faz o 302 para a URL real (resolvida nos bastidores).
        Sem id (oferta ad-hoc), cai no link de afiliado/original já existente.
        """
        oid = oferta.get("id")
        if oid:
            return montar_link_redirect(oid, self.nome)
        return oferta.get("link_afiliado") or oferta.get("link_original") or ""

    def _montar_post(self, oferta: dict) -> str:
        """Monta o texto do post em HTML (robusto a caracteres especiais)."""
        
        if config.USAR_IA_COPYWRITER and config.GEMINI_API_KEY:
            from backend.copywriter import gerar_copy_oferta
            texto_ia = gerar_copy_oferta(oferta)
            if texto_ia:
                return texto_ia

        linhas = []

        # Urgencia
        desconto = oferta.get("desconto_pct", 0)
        if desconto >= 40:
            linhas.append("🔥🔥🔥 <b>OFERTA IMPERDÍVEL</b> 🔥🔥🔥")
        elif desconto >= 25:
            linhas.append("‼️ <b>PREÇO BAIXOU</b> ‼️")
        else:
            linhas.append("💰 <b>ACHADO DO DIA</b> 💰")
        linhas.append("")

        # Titulo (escapado)
        linhas.append(f"📦 {self._esc(oferta['titulo'])}")
        linhas.append("")

        # Preco
        preco_fmt = self._esc(self.formatar_preco(oferta["preco"]))
        if oferta.get("preco_original") and oferta["preco_original"] > oferta["preco"]:
            preco_orig_fmt = self._esc(self.formatar_preco(oferta["preco_original"]))
            linhas.append(f"<s>De: {preco_orig_fmt}</s>")
            linhas.append(f"<b>Por: {preco_fmt}</b> 🏷️")
            linhas.append(f"📉 <b>{desconto:.0f}% OFF</b>")
        else:
            linhas.append(f"<b>Por: {preco_fmt}</b>")
        linhas.append("")

        parcelamento = self.obter_parcelamento(oferta)
        if parcelamento:
            linhas.append(f"💳 <b>{self._esc(parcelamento)}</b>")
            linhas.append("")

        # Frete
        if oferta.get("frete_gratis"):
            linhas.append("🚚 <b>Frete Grátis!</b>")
            linhas.append("")

        # Cupom relâmpago (TASK-09/12): cupom top-level ou em dados_extra.
        cupom = oferta.get("cupom") or (oferta.get("dados_extra") or {}).get("cupom", "")
        if cupom:
            linhas.append("⚡ <b>CUPOM RELÂMPAGO</b>")
            linhas.append(f"🎟️ <b>{self._esc(cupom)}</b>")
            if oferta.get("expira_em"):
                linhas.append(f"⏳ Expira em: {self._esc(oferta['expira_em'])}")
            linhas.append("")

        # Loja e link (link escapado)
        loja = self._esc(oferta.get("loja", "Loja"))
        linhas.append(f"🏪 <b>{loja}</b>")
        linhas.append("")

        # Rodape
        linhas.append("⏰ Promoção por tempo limitado!")
        linhas.append("")
        linhas.append("📢 Entre no canal: https://t.me/promoachadosbrasiloficial")

        return "\n".join(linhas)

    def _get_reply_markup(self, link: str):
        if not link:
            return None
            
        # Proteção: A API do Telegram proíbe links locais em botões.
        # Removemos o botão em ambiente de dev para que o post não falhe.
        if "localhost" in link or "127.0.0.1" in link:
            return None
            
        import json
        return json.dumps({
            "inline_keyboard": [[
                {"text": "🛒 COMPRAR COM DESCONTO", "url": link}
            ]]
        })

    def _enviar_com_imagem(self, texto: str, imagem_url: str, link: str, chat_id: str = None) -> dict:
        """Envia post com foto — tenta upload, fallback para URL."""
        chat_id = chat_id or self.chat_id
        url = f"{self.api_base}/sendPhoto"
        reply_markup = self._get_reply_markup(link)

        # Tenta baixar a imagem e enviar por upload
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            img_resp = requests.get(imagem_url, headers=headers, timeout=15)

            if img_resp.ok:
                ext = "jpg"
                if ".png" in imagem_url.lower():
                    ext = "png"
                elif ".webp" in imagem_url.lower():
                    ext = "webp"

                arquivos = {"photo": (f"produto.{ext}", img_resp.content)}
                dados = {
                    "chat_id": chat_id,
                    "caption": texto,
                    "parse_mode": "HTML",
                }
                if reply_markup:
                    dados["reply_markup"] = reply_markup

                resp = requests.post(url, data=dados, files=arquivos, timeout=30)
            else:
                raise Exception(f"HTTP {img_resp.status_code}")

        except Exception:
            # Fallback: envia URL direta
            dados = {
                "chat_id": chat_id,
                "photo": imagem_url,
                "caption": texto,
                "parse_mode": "HTML",
            }
            if reply_markup:
                dados["reply_markup"] = reply_markup
            resp = requests.post(url, data=dados, timeout=30)

        return self._processar_resposta(resp)

    def _enviar_texto(self, texto: str, link: str, chat_id: str = None) -> dict:
        """Envia post apenas texto."""
        chat_id = chat_id or self.chat_id
        url = f"{self.api_base}/sendMessage"
        reply_markup = self._get_reply_markup(link)
        dados = {
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML",
        }
        if reply_markup:
            dados["reply_markup"] = reply_markup
        resp = requests.post(url, data=dados, timeout=30)
        return self._processar_resposta(resp)

    def _processar_resposta(self, resp: requests.Response) -> dict:
        """Processa resposta da API do Telegram."""
        try:
            data = resp.json()
            if resp.ok and data.get("ok"):
                return {"sucesso": True, "resposta": "Postado com sucesso no Telegram!"}
            else:
                desc = data.get("description", resp.text[:200])
                return {"sucesso": False, "resposta": f"Erro Telegram: {desc}"}
        except Exception as e:
            return {"sucesso": False, "resposta": f"Erro ao processar resposta: {e}"}
