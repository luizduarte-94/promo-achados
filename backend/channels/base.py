# -*- coding: utf-8 -*-
"""
Classe base para canais de distribuição.
"""

from abc import ABC, abstractmethod


class BaseChannel(ABC):
    """Interface comum para todos os canais de envio."""

    nome: str = "base"

    @abstractmethod
    def enviar(self, oferta: dict) -> dict:
        """
        Envia uma oferta para o canal.

        Args:
            oferta: dict com dados da oferta (formato padrão do DB).

        Returns:
            dict com:
                "sucesso": bool,
                "resposta": str (mensagem de status ou erro),
        """
        ...

    @abstractmethod
    def esta_configurado(self) -> bool:
        """Retorna True se as credenciais estão configuradas."""
        ...

    def preview(self, oferta: dict) -> str:
        """Texto da mensagem SEM enviar (copiar/colar manual).

        Default vazio; canais que suportam copy manual sobrescrevem.
        """
        return ""

    def formatar_preco(self, preco: float) -> str:
        """Formata preço em Real brasileiro."""
        return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
