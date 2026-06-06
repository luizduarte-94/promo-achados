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

        if not config.WHATSAPP_TO:
            return {
                "sucesso": False,
                "resposta": (
                    "Defina WHATSAPP_TO (número destinatário E.164, ex: 5511999998888) "
                    "no .env. PHONE_NUMBER_ID é o remetente, não o destino."
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
            "to": config.WHATSAPP_TO,  # Destinatário E.164 (PHONE_NUMBER_ID é o remetente)
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

    def preview(self, oferta: dict) -> str:
        """Retorna a mensagem formatada SEM enviar (para copiar/colar manual)."""
        return self._montar_mensagem(oferta)

    def _montar_mensagem(self, oferta: dict) -> str:
        """Monta a mensagem no formato dos grupos de promoção do WhatsApp.

        Usa o markdown do WhatsApp: *negrito*, _itálico_ e ~tachado~. Sem HTML.
        """
        linhas = []

        desconto = oferta.get("desconto_pct", 0)
        if desconto >= 40:
            linhas.append("🔥 *OFERTA IMPERDÍVEL* 🔥")
        elif desconto >= 25:
            linhas.append("‼️ *PREÇO BAIXOU* ‼️")
        else:
            linhas.append("‼️ *ESGOTA RÁPIDO* ‼️")
        linhas.append("")

        linhas.append(f"*{oferta['titulo']}*")
        linhas.append("")

        # Frase persuasiva gerada por IA (opcional, mantém o formato do grupo)
        if config.USAR_IA_COPYWRITER and config.GEMINI_API_KEY:
            from backend.copywriter import gerar_frase_persuasiva
            frase = gerar_frase_persuasiva(oferta)
            if frase:
                linhas.append(f"_{frase}_")
                linhas.append("")

        preco_fmt = self.formatar_preco(oferta["preco"])
        if oferta.get("preco_original") and oferta["preco_original"] > oferta["preco"]:
            preco_orig_fmt = self.formatar_preco(oferta["preco_original"])
            linhas.append(f"De: ~{preco_orig_fmt}~")
            linhas.append(f"*Por: {preco_fmt} à vista*")
            linhas.append(f"📉 *{desconto:.0f}% OFF*")
        else:
            linhas.append(f"*Por: {preco_fmt} à vista*")
        linhas.append("")

        cupom = (oferta.get("dados_extra") or {}).get("cupom", "")
        if cupom:
            linhas.append(f"*Utilize o cupom: {cupom}*")
            linhas.append("_(o desconto entra na tela de pagamento)_")
            linhas.append("")

        if oferta.get("frete_gratis"):
            linhas.append("_Frete grátis para várias regiões, consulte seu CEP_")
            linhas.append("")

        link = oferta.get("link_afiliado") or oferta.get("link_original", "")
        linhas.append(f"*{oferta.get('loja', 'Loja')}:*")
        if link:
            linhas.append(f"Compre em: {link}")
        linhas.append("")

        linhas.append("Promoção por tempo limitado")
        linhas.append("")
        linhas.append("⚠️ O link ou foto não apareceu?")
        linhas.append("Adicione esse contato na sua agenda.")

        if config.LINKTREE_URL:
            linhas.append("")
            linhas.append("Economize também em outras categorias:")
            linhas.append(config.LINKTREE_URL)

        return "\n".join(linhas)
