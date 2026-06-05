# -*- coding: utf-8 -*-
"""
PROMO ACHADOS BRASIL — Entry Point
===================================
Inicia o servidor FastAPI com dashboard + API REST + agendador.

Uso:
    python main.py

O dashboard abre em: http://localhost:8000
"""

import contextlib
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend import database as db
from backend.api.routes import router as api_router
from backend.scheduler import iniciar_agendador, parar_agendador
from backend.config import config


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia startup e shutdown da aplicação."""
    # Startup
    print("\n" + "=" * 55)
    print("  PROMO ACHADOS BRASIL - Iniciando...")
    print("=" * 55)

    db.init_db()
    print("  [OK] Banco de dados inicializado")

    # Status dos canais
    print(f"  [{'OK' if config.telegram_ok() else 'X'}] Telegram")
    print(f"  [{'OK' if config.shopee_ok() else '..'}] Shopee Affiliate API")
    print(f"  [{'OK' if config.whatsapp_ok() else '..'}] WhatsApp Business")
    print(f"  [{'OK' if config.instagram_ok() else '..'}] Instagram")

    iniciar_agendador()
    print(f"\n  Dashboard: http://localhost:8000")
    print("=" * 55 + "\n")

    yield

    # Shutdown
    parar_agendador()
    print("\n  Promo Achados Brasil finalizado.\n")


app = FastAPI(
    title="Promo Achados Brasil",
    description="Sistema de automação de ofertas para afiliados",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS para desenvolvimento
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router)

# Serve frontend
app.mount("/css", StaticFiles(directory=str(config.FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(config.FRONTEND_DIR / "js")), name="js")


@app.get("/")
async def serve_index():
    """Serve o dashboard."""
    return FileResponse(str(config.FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    # Por padrao escuta SO em 127.0.0.1 (apenas o seu PC) — mais seguro.
    # Para rodar num servidor exposto, defina HOST=0.0.0.0 no .env,
    # mas SO depois de colocar autenticacao (senha) no painel.
    host = os.getenv("HOST", "127.0.0.1")
    # reload=False evita o agendador iniciar duas vezes.
    uvicorn.run("main:app", host=host, port=8000, reload=False)
