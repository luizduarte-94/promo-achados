# -*- coding: utf-8 -*-
"""
Canal WhatsApp — via Meta Cloud API.

NOTA: Requer conta Meta Business verificada + WhatsApp Business API configurada.
Este módulo está preparado para funcionar quando as credenciais forem fornecidas.
"""

import requests
from backend.channels.base import BaseChannel
from backend.config import config


class WhatsAppChannel(BaseChannel):
    """Envia ofertas via WhatsApp Business Cloud API."""

    nome = "whatsapp"

    def __init__(self):
        self.api_base = "https://graph.facebook.com/v22.0"

    def esta_configurado(self) -> bool:
        return config.whatsapp_ok()

    def enviar(self, oferta: dict) -> dict:
        """Envia oferta via WhatsApp Cloud API."""
        if not self.esta_configurado():
            return {
                "sucesso": False,
                "resposta": (
                    "WhatsApp não configurado. Configure WHATSAPP_ACCESS_TOKEN "
                    "e WHATSAPP_PHONE_NUMBER_ID no arquivo .env"
                ),
            }

        texto = self._montar_mensagem(oferta)
        url = f"{self.api_base}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"

        headers = {
            "Authorization": f"Bearer {config.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

        # Envia como mensagem de texto formatada
        payload = {
            "messaging_product": "whatsapp",
            "to": config.WHATSAPP_PHONE_NUMBER_ID,  # Número do destinatário (será configurável)
            "type": "text",
            "text": {"body": texto},
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            if resp.ok:
                return {"sucesso": True, "resposta": "Enviado via WhatsApp!"}
            else:
                return {"sucesso": False, "resposta": f"Erro WhatsApp: {resp.text[:200]}"}
        except Exception as e:
            return {"sucesso": False, "resposta": f"Erro ao enviar WhatsApp: {e}"}

    def _montar_mensagem(self, oferta: dict) -> str:
        """Monta mensagem para WhatsApp (texto puro, sem Markdown)."""
        linhas = []

        desconto = oferta.get("desconto_pct", 0)
        if desconto >= 40:
            linhas.append("🔥🔥🔥 OFERTA IMPERDÍVEL 🔥🔥🔥")
        elif desconto >= 25:
            linhas.append("‼️ PREÇO BAIXOU ‼️")
        else:
            linhas.append("💰 ACHADO DO DIA 💰")
        linhas.append("")

        linhas.append(f"📦 {oferta['titulo']}")
        linhas.append("")

        preco_fmt = self.formatar_preco(oferta["preco"])
        if oferta.get("preco_original") and oferta["preco_original"] > oferta["preco"]:
            preco_orig_fmt = self.formatar_preco(oferta["preco_original"])
            linhas.append(f"De: {preco_orig_fmt}")
            linhas.append(f"Por: {preco_fmt} 🏷️")
            linhas.append(f"📉 {desconto:.0f}% OFF")
        else:
            linhas.append(f"Por: {preco_fmt}")
        linhas.append("")

        if oferta.get("frete_gratis"):
            linhas.append("🚚 Frete Grátis!")
            linhas.append("")

        link = oferta.get("link_afiliado") or oferta.get("link_original", "")
        linhas.append(f"🏪 {oferta.get('loja', 'Loja')}:")
        if link:
            linhas.append(f"🔗 {link}")
        linhas.append("")
        linhas.append("⏰ Promoção por tempo limitado!")
        linhas.append("🔗 Contém links de afiliado")

        return "\n".join(linhas)
