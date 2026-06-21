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
from backend.monetization import gerar_link_afiliado


class TelegramChannel(BaseChannel):
    """Envia ofertas para canal/grupo do Telegram."""

    nome = "telegram"

    def __init__(self):
        self.api_base = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
        self.chat_id = config.TELEGRAM_CHAT_ID

    def esta_configurado(self) -> bool:
        return config.telegram_ok()

    def enviar(self, oferta: dict) -> dict:
        """Envia oferta formatada para o canal do Telegram."""
        if not self.esta_configurado():
            return {"sucesso": False, "resposta": "Token do Telegram nao configurado."}

        texto = self._montar_post(oferta)
        imagem_url = oferta.get("imagem_url")
        link = self._link_rastreado(oferta)

        try:
            if imagem_url:
                return self._enviar_com_imagem(texto, imagem_url, link)
            else:
                return self._enviar_texto(texto, link)
        except Exception as e:
            return {"sucesso": False, "resposta": f"Erro inesperado: {e}"}

    @staticmethod
    def _esc(texto) -> str:
        """Escapa caracteres especiais de HTML (<, >, &) para o Telegram."""
        return html.escape(str(texto), quote=False)

    def _link_rastreado(self, oferta: dict) -> str:
        """Link de afiliado rastreado p/ o canal Telegram (TASK-12).

        Usa o motor de monetização (TASK-10) com canal="telegram" + produto_id,
        em vez do link cru — cada clique passa a ser atribuído ao canal.
        """
        base = oferta.get("link_afiliado") or oferta.get("link_original") or ""
        if not base:
            return ""
        return gerar_link_afiliado(base, canal="telegram", produto_id=oferta.get("produto_id"))

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
        import json
        return json.dumps({
            "inline_keyboard": [[
                {"text": "🛒 COMPRAR COM DESCONTO", "url": link}
            ]]
        })

    def _enviar_com_imagem(self, texto: str, imagem_url: str, link: str) -> dict:
        """Envia post com foto — tenta upload, fallback para URL."""
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
                    "chat_id": self.chat_id,
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
                "chat_id": self.chat_id,
                "photo": imagem_url,
                "caption": texto,
                "parse_mode": "HTML",
            }
            if reply_markup:
                dados["reply_markup"] = reply_markup
            resp = requests.post(url, data=dados, timeout=30)

        return self._processar_resposta(resp)

    def _enviar_texto(self, texto: str, link: str) -> dict:
        """Envia post apenas texto."""
        url = f"{self.api_base}/sendMessage"
        reply_markup = self._get_reply_markup(link)
        dados = {
            "chat_id": self.chat_id,
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
