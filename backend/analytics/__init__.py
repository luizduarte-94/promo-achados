# -*- coding: utf-8 -*-
"""Analytics interno: rastreamento de cliques (/r/) e relatórios de conversão."""

from backend.analytics.tracking import (
    montar_link_redirect,
    resolver_destino,
    registrar_clique,
    hash_ip,
)

__all__ = [
    "montar_link_redirect",
    "resolver_destino",
    "registrar_clique",
    "hash_ip",
]
