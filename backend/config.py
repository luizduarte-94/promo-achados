# -*- coding: utf-8 -*-
"""
Configuração centralizada — carrega variáveis do .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega o .env da raiz do projeto
_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


class Config:
    """Configurações globais do sistema."""

    # --- Paths ---
    BASE_DIR = _BASE_DIR
    DB_PATH = _BASE_DIR / "promo_achados.db"
    FRONTEND_DIR = _BASE_DIR / "frontend"

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "@promoachadosbrasiloficial")

    # --- Mercado Livre ---
    ML_CLIENT_ID: str = os.getenv("ML_CLIENT_ID", "")
    ML_CLIENT_SECRET: str = os.getenv("ML_CLIENT_SECRET", "")
    ML_API_BASE: str = "https://api.mercadolibre.com"

    # --- Shopee Affiliate ---
    SHOPEE_APP_ID: str = os.getenv("SHOPEE_APP_ID", "")
    SHOPEE_APP_SECRET: str = os.getenv("SHOPEE_APP_SECRET", "")
    SHOPEE_API_BASE: str = "https://open-api.affiliate.shopee.com.br/graphql"

    # --- WhatsApp Business ---
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    # Número destinatário (E.164, ex: 5511999998888). PHONE_NUMBER_ID é o remetente.
    WHATSAPP_TO: str = os.getenv("WHATSAPP_TO", "")

    # --- Instagram ---
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_USER_ID: str = os.getenv("INSTAGRAM_USER_ID", "")

    # --- Divulgação ---
    # Linktree/landing com todos os teus links (aparece no rodapé das mensagens).
    LINKTREE_URL: str = os.getenv("LINKTREE_URL", "")

    # --- Inteligência Artificial ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    USAR_IA_COPYWRITER: bool = os.getenv("USAR_IA_COPYWRITER", "True").lower() == "true"

    # --- Configurações do Bot ---
    BUSCA_INTERVALO_MINUTOS: int = int(os.getenv("BUSCA_INTERVALO_MINUTOS", "60"))
    BUSCA_PALAVRAS_CHAVE: list[str] = [
        kw.strip()
        for kw in os.getenv("BUSCA_PALAVRAS_CHAVE", "").split(",")
        if kw.strip()
    ]
    BUSCA_DESCONTO_MINIMO: int = int(os.getenv("BUSCA_DESCONTO_MINIMO", "15"))
    BUSCA_PRECO_MAXIMO: float = float(os.getenv("BUSCA_PRECO_MAXIMO", "500"))
    PAUSA_ENTRE_POSTS: int = int(os.getenv("PAUSA_ENTRE_POSTS", "3"))

    # --- Painel (autenticação básica) ---
    # PANEL_PASSWORD vazio = auth DESLIGADA (dev local). Defina p/ proteger o painel.
    PANEL_USER: str = os.getenv("PANEL_USER", "admin")
    PANEL_PASSWORD: str = os.getenv("PANEL_PASSWORD", "")

    # --- Auto-Post (postagem automatica pelo agendador) ---
    # Desligado por padrao: so posta sozinho quando explicitamente ativado.
    AUTO_POST_ENABLED: bool = os.getenv("AUTO_POST_ENABLED", "False").lower() == "true"
    AUTO_POST_SCORE_MINIMO: int = int(os.getenv("AUTO_POST_SCORE_MINIMO", "60"))
    AUTO_POST_MAX_POR_CICLO: int = int(os.getenv("AUTO_POST_MAX_POR_CICLO", "3"))

    # --- Monitoramento de Recorrentes (alerta de queda de preco) ---
    # Desligado por padrao. Quando ligado, rebusca os recorrentes e alerta no Telegram.
    MONITOR_RECORRENTES_ENABLED: bool = os.getenv("MONITOR_RECORRENTES_ENABLED", "False").lower() == "true"
    MONITOR_RECORRENTES_INTERVALO_MINUTOS: int = int(os.getenv("MONITOR_RECORRENTES_INTERVALO_MINUTOS", "360"))

    # --- Espelho (grupos WhatsApp como sinal de tendência) ---
    # O bot-espelho (Node) grava as mensagens dos grupos em data/espelho_inbox.jsonl.
    # O agendador lê os termos novos e busca esses produtos nas fontes (ML/Shopee).
    ESPELHO_ENABLED: bool = os.getenv("ESPELHO_ENABLED", "True").lower() == "true"
    # Quantos termos (produtos) buscar por ciclo — ML tem rate limit agressivo.
    ESPELHO_MAX_TERMOS: int = int(os.getenv("ESPELHO_MAX_TERMOS", "5"))
    ESPELHO_INBOX = _BASE_DIR / "data" / "espelho_inbox.jsonl"
    ESPELHO_OFFSET = _BASE_DIR / "data" / "espelho_inbox.offset"

    @classmethod
    def telegram_ok(cls) -> bool:
        return bool(cls.TELEGRAM_BOT_TOKEN and "COLE" not in cls.TELEGRAM_BOT_TOKEN)

    @classmethod
    def shopee_ok(cls) -> bool:
        return bool(cls.SHOPEE_APP_ID and cls.SHOPEE_APP_SECRET)

    @classmethod
    def whatsapp_ok(cls) -> bool:
        return bool(cls.WHATSAPP_ACCESS_TOKEN and cls.WHATSAPP_PHONE_NUMBER_ID)

    @classmethod
    def instagram_ok(cls) -> bool:
        return bool(cls.INSTAGRAM_ACCESS_TOKEN and cls.INSTAGRAM_USER_ID)


config = Config()
