# -*- coding: utf-8 -*-
"""
PROMO ACHADOS BRASIL — Entry Point (API)
========================================
Inicia SÓ o servidor FastAPI (dashboard + API REST). O agendador (jobs de
busca/postagem) roda num processo SEPARADO — ver backend/scheduler_worker.py.

Uso:
    python main.py                      # API
    python -m backend.scheduler_worker  # agendador (outro terminal)

O dashboard abre em: http://localhost:8000
"""

import base64
import contextlib
import os
import secrets
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from backend import database as db
from backend.api.routes import router as api_router
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

    if config.PANEL_PASSWORD:
        print(f"  [OK] Painel protegido por senha (usuario: {config.PANEL_USER})")
    else:
        print("  [!!] Painel SEM senha (PANEL_PASSWORD vazio). Defina no .env p/ proteger.")

    print("  [i] Agendador roda à parte: python -m backend.scheduler_worker")
    print(f"\n  Dashboard: http://localhost:8000")
    print("=" * 55 + "\n")

    yield

    # Shutdown
    print("\n  Promo Achados Brasil (API) finalizado.\n")


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


@app.middleware("http")
async def autenticacao_basica(request: Request, call_next):
    """HTTP Basic Auth no painel inteiro.

    Ativa só quando PANEL_PASSWORD está definido no .env. Compara em tempo
    constante (secrets.compare_digest) para evitar timing attack.
    AVISO: Basic Auth só é seguro sobre HTTPS — em produção, ponha atrás de TLS.
    """
    if config.PANEL_PASSWORD and request.method != "OPTIONS":
        auth = request.headers.get("Authorization", "")
        autorizado = False
        if auth.startswith("Basic "):
            try:
                usuario, _, senha = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
                autorizado = (
                    secrets.compare_digest(usuario, config.PANEL_USER)
                    and secrets.compare_digest(senha, config.PANEL_PASSWORD)
                )
            except Exception:
                autorizado = False
        if not autorizado:
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Promo Achados"'},
            )
    return await call_next(request)

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
