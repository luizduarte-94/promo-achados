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
import re
import secrets
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from backend import database as db
from backend.analytics.tracking import registrar_clique, resolver_destino
from backend.analytics.reports import gerar_resumo
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
    print("\n  Dashboard: http://localhost:8000")
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


# Superfície PÚBLICA (somente leitura) — liberada mesmo com PANEL_PASSWORD ativo.
# Tudo o que NÃO está aqui (admin + criação/edição/exclusão/busca/postagem) exige auth.
_PUBLIC_PREFIXOS = ("/r/", "/css/", "/js/")
_PUBLIC_GET_EXATO = {
    "/",
    "/api/ofertas",
    "/api/ml/callback",
}   # index (SPA), lista da vitrine e retorno OAuth


def _rota_publica(request: Request) -> bool:
    """True p/ rotas públicas de leitura (vitrine/redirect/estáticos/OAuth callback)."""
    if request.method == "OPTIONS":          # preflight CORS
        return True
    path = request.url.path
    if path.startswith(_PUBLIC_PREFIXOS):
        return True
    if request.method in ("GET", "HEAD") and path in _PUBLIC_GET_EXATO:
        return True
    return False


@app.middleware("http")
async def seguranca_e_cache(request: Request, call_next):
    """Basic Auth no painel/mutações + cabeçalhos de cache previsíveis.

    Auth ativa só quando PANEL_PASSWORD está definido. A VITRINE e os endpoints
    públicos de LEITURA (ver _rota_publica) ficam liberados; criação, edição,
    exclusão, busca, postagem e telas/admin exigem credencial. Comparação em
    tempo constante (secrets.compare_digest). AVISO: Basic Auth só é seguro sob HTTPS.
    """
    if config.PANEL_PASSWORD and not _rota_publica(request):
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

    resp = await call_next(request)

    # Cache previsível: só URLs efetivamente versionadas podem ser imutáveis.
    # Assets sem ?v= e o HTML revalidam sempre.
    path = request.url.path
    if path.startswith(("/css/", "/js/")):
        if request.query_params.get("v"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            resp.headers["Cache-Control"] = "no-cache"
    return resp

# API Routes
app.include_router(api_router)

# Serve frontend
app.mount("/css", StaticFiles(directory=str(config.FRONTEND_DIR / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(config.FRONTEND_DIR / "js")), name="js")


@app.get("/r/{oferta_id}")
def redirect_oferta(oferta_id: int, request: Request, background: BackgroundTasks, c: str = "site"):
    """Redirecionador interno de cliques (TASK-14).

    Registra o clique em background (não bloqueia) e responde 302 para a URL de
    afiliado resolvida nos bastidores. Rota pública (isenta de Basic Auth).
    """
    oferta = db.obter_oferta(oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")

    destino = resolver_destino(oferta, c)
    if not destino:
        raise HTTPException(status_code=404, detail="Oferta sem link para redirecionar")

    ip = request.client.host if request.client else None
    background.add_task(registrar_clique, oferta_id, c, ip)
    return RedirectResponse(url=destino, status_code=302)


@app.get("/analytics/summary")
def analytics_summary(limite: int = 10, dias: int | None = None):
    """Resumo analítico: cliques x ofertas (TASK-16).

    Cruza click_events com ofertas e devolve cliques por canal, top ofertas,
    faturamento estimado e EPC por canal. CTR vem como indisponível (sem
    impressões instrumentadas). Protegido pelo Basic Auth do painel (admin).
    """
    return gerar_resumo(limite=limite, dias=dias)


def _asset_version() -> str:
    """Versão dos assets = maior mtime de style.css/app.js (cache-busting automático)."""
    mt = 0
    for rel in ("css/style.css", "js/app.js"):
        try:
            mt = max(mt, int((config.FRONTEND_DIR / rel).stat().st_mtime))
        except OSError:
            pass
    return str(mt)


@app.get("/")
async def serve_index():
    """Serve o SPA. Injeta ?v=<mtime> nos assets (cache longo) e revalida o HTML."""
    html = (config.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    ver = _asset_version()
    # Reescreve /css/style.css e /js/app.js (com ou sem ?v=) p/ a versão atual.
    html = re.sub(r'(/css/style\.css|/js/app\.js)(\?v=[^"\']*)?', rf'\1?v={ver}', html)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import uvicorn
    # Por padrao escuta SO em 127.0.0.1 (apenas o seu PC) — mais seguro.
    # Para rodar num servidor exposto, defina HOST=0.0.0.0 no .env,
    # mas SO depois de colocar autenticacao (senha) no painel.
    host = os.getenv("HOST", "127.0.0.1")
    # reload=False evita o agendador iniciar duas vezes.
    uvicorn.run("main:app", host=host, port=8000, reload=False)
