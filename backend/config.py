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
    USE_SQLITE   = os.getenv("USE_SQLITE", "False").lower() == "true"
    SQLITE_PATH  = os.getenv("SQLITE_PATH", "promo_achados.db")
    DB_PATH = Path(os.getenv("SQLITE_PATH", str(_BASE_DIR / "promo_achados.db")))
    FRONTEND_DIR = _BASE_DIR / "frontend"

    # --- PostgreSQL (banco principal; ver docker-compose.yml) ---
    # Default casa com o docker-compose local. A aplicação só passa a USAR o
    # Postgres na TASK-04; por ora a camada ORM (backend/models.py) o consome.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://promo:promo@localhost:5432/promo_achados"
    )

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
    # Comissão (0–1) a partir da qual a oferta é marcada high_commission (fila VIP).
    # Ex.: 0.10 = 10%. Selo "Comissão Extra" da Shopee também ativa a flag.
    SHOPEE_HIGH_COMMISSION_PCT: float = float(
        os.getenv("SHOPEE_HIGH_COMMISSION_PCT", "0.10")
    )

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

    # --- Analytics / Redirect interno (TASK-14/15) ---
    # Base pública do redirecionador /r/{id}. Os canais usam esse domínio no link
    # curto (ex.: https://api.promoachados.com/r/123?c=telegram). Em dev, localhost.
    REDIRECT_BASE_URL: str = os.getenv("REDIRECT_BASE_URL", "http://localhost:8000").rstrip("/")
    # Salt p/ hash de IP no log de cliques (LGPD: não guardamos IP em claro).
    CLICK_IP_SALT: str = os.getenv("CLICK_IP_SALT", "promo-achados")

    # --- Monetização / Tracking (TASK-10) ---
    # Parâmetros injetados em TODO link de afiliado para atribuir clique por canal.
    UTM_CAMPAIGN: str = os.getenv("UTM_CAMPAIGN", "promoachados")
    UTM_MEDIUM: str = os.getenv("UTM_MEDIUM", "afiliados")
    # Canal padrão atribuído ao link gravado na ingestão (o site consome esse link).
    AFILIADO_CANAL_PADRAO: str = os.getenv("AFILIADO_CANAL_PADRAO", "site")
    # Encurtar links da Shopee via Affiliate API (requer credenciais). Default ON.
    AFILIADO_ENCURTAR_SHOPEE: bool = (
        os.getenv("AFILIADO_ENCURTAR_SHOPEE", "True").lower() == "true"
    )

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

    # --- Revalidação de preço (re-checa o preço atual antes de postar/copiar) ---
    # Evita divulgar preço velho. Bloqueia o post se o preço subiu além do limite.
    REVALIDAR_PRECO_ENABLED: bool = (
        os.getenv("REVALIDAR_PRECO_ENABLED", "True").lower() == "true"
    )
    REVALIDAR_BLOQUEIO_ALTA_PCT: float = float(
        os.getenv("REVALIDAR_BLOQUEIO_ALTA_PCT", "5")
    )

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
    MONITOR_RECORRENTES_ENABLED: bool = (
        os.getenv("MONITOR_RECORRENTES_ENABLED", "False").lower() == "true"
    )
    MONITOR_RECORRENTES_INTERVALO_MINUTOS: int = int(
        os.getenv("MONITOR_RECORRENTES_INTERVALO_MINUTOS", "360")
    )

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
