# -*- coding: utf-8 -*-
"""
Classe base para scrapers de ofertas.
"""

from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """Interface comum para todos os scrapers."""

    nome: str = "base"

    @abstractmethod
    def buscar(self, palavra_chave: str, limite: int = 20) -> list[dict]:
        """
        Busca produtos por palavra-chave.

        Retorna lista de dicts com formato padronizado:
        {
            "titulo": str,
            "preco": float,
            "preco_original": float | None,
            "desconto_pct": float,
            "loja": str,
            "link_original": str,
            "link_afiliado": str | None,
            "imagem_url": str | None,
            "categoria": str | None,
            "vendedor": str | None,
            "reputacao": str | None,
            "frete_gratis": bool,
            "fonte": str,
            "dados_extra": dict | None,
        }
        """
        ...

    def _calcular_desconto(self, preco: float, preco_original: float | None) -> float:
        """Calcula percentual de desconto."""
        if not preco_original or preco_original <= 0 or preco_original <= preco:
            return 0.0
        return round(((preco_original - preco) / preco_original) * 100, 1)
