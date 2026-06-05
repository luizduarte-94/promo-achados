# -*- coding: utf-8 -*-
"""
Canal Instagram — via Meta Graph API (container-based publishing).

NOTA: Requer conta Instagram Business/Creator + Facebook Page +
Meta App com permissão instagram_business_content_publish aprovada.
"""

import time
import requests
from backend.channels.base import BaseChannel
from backend.config import config


class InstagramChannel(BaseChannel):
    """Publica ofertas no Instagram via Graph API."""

    nome = "instagram"

    def __init__(self):
        self.api_base = "https://graph.facebook.com/v22.0"

    def esta_configurado(self) -> bool:
        return config.instagram_ok()

    def enviar(self, oferta: dict) -> dict:
        """Publica oferta no Instagram (fluxo container → publish)."""
        if not self.esta_configurado():
            return {
                "sucesso": False,
                "resposta": (
                    "Instagram não configurado. Configure INSTAGRAM_ACCESS_TOKEN "
                    "e INSTAGRAM_USER_ID no arquivo .env"
                ),
            }

        imagem_url = oferta.get("imagem_url")
        if not imagem_url:
            return {"sucesso": False, "resposta": "Instagram requer imagem. Esta oferta não tem imagem."}

        caption = self._montar_caption(oferta)

        try:
            # Passo 1: Criar container
            container_url = f"{self.api_base}/{config.INSTAGRAM_USER_ID}/media"
            container_resp = requests.post(container_url, data={
                "image_url": imagem_url,
                "caption": caption,
                "access_token": config.INSTAGRAM_ACCESS_TOKEN,
            }, timeout=30)

            if not container_resp.ok:
                return {"sucesso": False, "resposta": f"Erro ao criar container IG: {container_resp.text[:200]}"}

            creation_id = container_resp.json().get("id")
            if not creation_id:
                return {"sucesso": False, "resposta": "Container criado mas sem ID."}

            # Aguarda processamento
            time.sleep(5)

            # Passo 2: Publicar
            publish_url = f"{self.api_base}/{config.INSTAGRAM_USER_ID}/media_publish"
            pub_resp = requests.post(publish_url, data={
                "creation_id": creation_id,
                "access_token": config.INSTAGRAM_ACCESS_TOKEN,
            }, timeout=30)

            if pub_resp.ok:
                return {"sucesso": True, "resposta": "Publicado no Instagram!"}
            else:
                return {"sucesso": False, "resposta": f"Erro ao publicar IG: {pub_resp.text[:200]}"}

        except Exception as e:
            return {"sucesso": False, "resposta": f"Erro Instagram: {e}"}

    def _montar_caption(self, oferta: dict) -> str:
        """Monta caption para Instagram (sem links clicáveis em captions)."""
        linhas = []

        desconto = oferta.get("desconto_pct", 0)
        if desconto >= 40:
            linhas.append("🔥 OFERTA IMPERDÍVEL 🔥")
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
            linhas.append(f"📉 {desconto:.0f}% OFF!")
        else:
            linhas.append(f"Por: {preco_fmt}")
        linhas.append("")

        if oferta.get("frete_gratis"):
            linhas.append("🚚 Frete Grátis!")
            linhas.append("")

        linhas.append(f"🏪 {oferta.get('loja', 'Loja')}")
        linhas.append("🔗 Link na bio!")
        linhas.append("")
        linhas.append("⏰ Promoção por tempo limitado!")
        linhas.append("")

        # Hashtags para alcance
        linhas.append(
            "#promoção #oferta #desconto #achados #promoachados "
            "#ofertas #promocao #mercadolivre #shopee #barato "
            "#desconto #compraonline"
        )

        return "\n".join(linhas)
