# -*- coding: utf-8 -*-
"""
Canal Instagram — Meta Graph API (publicação por container) (TASK-11).

Três formatos (docs/PROJECT.md §2):
  * Feed    : post de imagem única (produto campeão / alta margem).
  * Stories : urgência; anexa o LINK STICKER apontando p/ o link de afiliado
              rastreado (canal="instagram", gerado pela camada de monetização).
  * Carrossel: "Top N Ofertas do Dia" (mescla Mercado Livre + Shopee).

Credenciais só via .env (NUNCA hardcode): INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_USER_ID.

Limites (docs/AGENTS.md): o canal IMPORTA o link de afiliado pronto da camada de
monetização (TASK-10) — não monta tracking por conta própria.
"""

import time
import requests
from backend.channels.base import BaseChannel
from backend.config import config
from backend.analytics import montar_link_redirect
from backend.templates.instagram_captions import caption_feed, caption_carrossel


class InstagramChannel(BaseChannel):
    """Publica ofertas no Instagram via Graph API (Feed, Stories, Carrossel)."""

    nome = "instagram"

    # Graph API aceita até 10 itens; usamos 5 (Top 5 do dia).
    MAX_CARROSSEL = 5
    # Tempo de espera p/ a Meta processar o container antes de publicar.
    PROCESSAMENTO_SEG = 5

    def __init__(self):
        self.api_base = "https://graph.facebook.com/v22.0"

    def esta_configurado(self) -> bool:
        return config.instagram_ok()

    # =============================================
    # CONTRATO (compat): enviar == publicar no Feed
    # =============================================

    def enviar(self, oferta: dict) -> dict:
        """Mantém o contrato dos canais (routes/scheduler chamam .enviar)."""
        return self.publicar_feed(oferta)

    # =============================================
    # FEED (imagem única)
    # =============================================

    def publicar_feed(self, oferta: dict) -> dict:
        """Publica um post de imagem única no Feed."""
        erro = self._checar_pronto(oferta.get("imagem_url"))
        if erro:
            return erro

        creation_id, falha = self._criar_container({
            "image_url": oferta["imagem_url"],
            "caption": caption_feed(oferta),
        })
        if falha:
            return falha
        return self._publicar(creation_id, "Feed publicado no Instagram!")

    # =============================================
    # STORIES (com link sticker do afiliado)
    # =============================================

    def publicar_story(self, oferta: dict) -> dict:
        """Publica um Story anexando o link de afiliado rastreado (sticker).

        O link sticker leva direto ao link de afiliado encurtado/rastreado
        (canal="instagram"). A geração do link vem da camada de monetização.
        """
        erro = self._checar_pronto(oferta.get("imagem_url"))
        if erro:
            return erro

        link = self._link_afiliado(oferta)

        params = {
            "image_url": oferta["imagem_url"],
            "media_type": "STORIES",
        }
        # Link sticker: a Graph API expõe o sticker de link p/ contas elegíveis.
        # Enviamos a URL rastreada; se a conta/versão não suportar, o Story sai
        # mesmo assim e o link fica disponível p/ o operador no retorno.
        if link:
            params["link"] = link

        creation_id, falha = self._criar_container(params)
        if falha:
            return falha
        res = self._publicar(creation_id, "Story publicado no Instagram!")
        res["link_afiliado"] = link
        return res

    # =============================================
    # CARROSSEL (Top N do dia)
    # =============================================

    def publicar_carrossel(self, ofertas: list[dict], titulo: str | None = None) -> dict:
        """Publica um carrossel com até MAX_CARROSSEL ofertas (com imagem)."""
        if not self.esta_configurado():
            return self._erro_config()

        com_imagem = [o for o in ofertas if o.get("imagem_url")][: self.MAX_CARROSSEL]
        if len(com_imagem) < 2:
            return {"sucesso": False, "resposta": "Carrossel exige ao menos 2 ofertas com imagem."}

        # 1) Containers-filho (um por imagem).
        filhos = []
        for o in com_imagem:
            cid, falha = self._criar_container({
                "image_url": o["imagem_url"],
                "is_carousel_item": "true",
            })
            if falha:
                return {"sucesso": False, "resposta": f"Falha em item do carrossel: {falha['resposta']}"}
            filhos.append(cid)

        # 2) Container-pai (CAROUSEL) com a legenda agregada.
        caption = caption_carrossel(com_imagem, titulo) if titulo else caption_carrossel(com_imagem)
        parent_id, falha = self._criar_container({
            "media_type": "CAROUSEL",
            "children": ",".join(filhos),
            "caption": caption,
        })
        if falha:
            return falha

        # 3) Publica o pai.
        res = self._publicar(parent_id, f"Carrossel publicado ({len(filhos)} itens)!")
        res["itens"] = len(filhos)
        return res

    # =============================================
    # HELPERS Graph API (baixo nível)
    # =============================================

    def _link_afiliado(self, oferta: dict) -> str:
        """Link curto do redirecionador próprio /r/{id}?c=instagram (TASK-15).

        O link sticker do Story passa pelo nosso /r/ (registra o clique + 302
        para a URL real). Sem id, cai no link de afiliado/original existente.
        """
        oid = oferta.get("id")
        if oid:
            return montar_link_redirect(oid, self.nome)
        return oferta.get("link_afiliado") or oferta.get("link_original") or ""

    def _checar_pronto(self, imagem_url) -> dict | None:
        """Pré-condições comuns: configurado + tem imagem. None se OK."""
        if not self.esta_configurado():
            return self._erro_config()
        if not imagem_url:
            return {"sucesso": False, "resposta": "Instagram requer imagem. Esta oferta não tem imagem."}
        return None

    def _erro_config(self) -> dict:
        return {
            "sucesso": False,
            "resposta": (
                "Instagram não configurado. Configure INSTAGRAM_ACCESS_TOKEN "
                "e INSTAGRAM_USER_ID no arquivo .env"
            ),
        }

    def _criar_container(self, params: dict) -> tuple[str | None, dict | None]:
        """POST /{user}/media. Retorna (creation_id, None) ou (None, erro_dict)."""
        url = f"{self.api_base}/{config.INSTAGRAM_USER_ID}/media"
        dados = {**params, "access_token": config.INSTAGRAM_ACCESS_TOKEN}
        try:
            resp = requests.post(url, data=dados, timeout=30)
        except requests.RequestException as e:
            return None, {"sucesso": False, "resposta": f"Erro de rede no container IG: {e}"}

        if not resp.ok:
            return None, {"sucesso": False, "resposta": f"Erro ao criar container IG: {resp.text[:200]}"}
        creation_id = resp.json().get("id")
        if not creation_id:
            return None, {"sucesso": False, "resposta": "Container criado mas sem ID."}
        return creation_id, None

    def _publicar(self, creation_id: str, msg_ok: str) -> dict:
        """POST /{user}/media_publish após aguardar o processamento do container."""
        time.sleep(self.PROCESSAMENTO_SEG)
        url = f"{self.api_base}/{config.INSTAGRAM_USER_ID}/media_publish"
        dados = {"creation_id": creation_id, "access_token": config.INSTAGRAM_ACCESS_TOKEN}
        try:
            resp = requests.post(url, data=dados, timeout=30)
        except requests.RequestException as e:
            return {"sucesso": False, "resposta": f"Erro de rede ao publicar IG: {e}"}

        if resp.ok:
            return {"sucesso": True, "resposta": msg_ok}
        return {"sucesso": False, "resposta": f"Erro ao publicar IG: {resp.text[:200]}"}

    # Compat: mantém o nome antigo usado por testes anteriores.
    def _montar_caption(self, oferta: dict) -> str:
        return caption_feed(oferta)
