# -*- coding: utf-8 -*-
"""Motor de monetização: converte links crus em links de afiliado rastreáveis.

Ponto único de geração de link comissionado (UTMs, sub_id, shortlink). Os canais
(Telegram/WhatsApp/Instagram/Site) DEVEM consumir daqui — nunca montar tracking
por conta própria (ver docs/AGENTS.md).
"""

from backend.monetization.link_generator import (
    LinkGenerator,
    gerar_link_afiliado,
    aplicar_utms,
    montar_sub_id,
)

__all__ = [
    "LinkGenerator",
    "gerar_link_afiliado",
    "aplicar_utms",
    "montar_sub_id",
]
