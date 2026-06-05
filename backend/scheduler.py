# -*- coding: utf-8 -*-
"""
Agendador de tarefas — busca automática de ofertas em intervalos configuráveis.
"""

import time

from apscheduler.schedulers.background import BackgroundScheduler
from backend.scrapers.mercadolivre import MercadoLivreScraper
from backend.scrapers.shopee import ShopeeScraper
from backend.channels.telegram import TelegramChannel
from backend.scoring import score_oferta
from backend import database as db
from backend.config import config


scheduler = BackgroundScheduler()
ml_scraper = MercadoLivreScraper()
shopee_scraper = ShopeeScraper()
telegram = TelegramChannel()


def auto_postar():
    """Posta automaticamente as melhores ofertas pendentes no Telegram.

    Só roda se AUTO_POST_ENABLED=true. Posta apenas ofertas que:
      - estão pendentes,
      - já têm link de afiliado (nunca posta sem link que paga),
      - têm score >= AUTO_POST_SCORE_MINIMO.
    Limita a AUTO_POST_MAX_POR_CICLO por execução.
    """
    if not config.AUTO_POST_ENABLED:
        return
    if not telegram.esta_configurado():
        print("[AUTO-POST] Telegram não configurado. Pulando.")
        return

    pendentes = db.listar_ofertas(status="pendente", limite=200)
    candidatas = [
        o for o in pendentes
        if (o.get("link_afiliado") or "").strip()
        and score_oferta(o) >= config.AUTO_POST_SCORE_MINIMO
    ]
    candidatas.sort(key=score_oferta, reverse=True)
    candidatas = candidatas[: config.AUTO_POST_MAX_POR_CICLO]

    if not candidatas:
        print("[AUTO-POST] Nenhuma oferta elegível (sem link afiliado ou score baixo).")
        return

    print(f"[AUTO-POST] Postando {len(candidatas)} oferta(s) no Telegram...")
    for oferta in candidatas:
        resultado = telegram.enviar(oferta)
        db.registrar_postagem(oferta["id"], "telegram", resultado["sucesso"], resultado["resposta"])
        print(f"[AUTO-POST] #{oferta['id']} score={score_oferta(oferta)} -> {resultado['sucesso']}")
        time.sleep(config.PAUSA_ENTRE_POSTS)


def tarefa_busca_automatica():
    """Executa busca automática em todas as fontes configuradas."""
    print("\n" + "=" * 50)
    print("[AGENDADOR] Iniciando busca automática...")
    print("=" * 50)

    total_novas = 0

    # Mercado Livre
    try:
        resultados_ml = ml_scraper.buscar_todas_palavras()
        novas_ml = 0
        for oferta in resultados_ml:
            if not db.oferta_existe(oferta["link_original"]):
                # Classificação automática de departamento
                dep_id = db.classificar_departamento(oferta["titulo"])
                if dep_id:
                    oferta["departamento_id"] = dep_id
                db.criar_oferta(oferta)
                novas_ml += 1
                # Registrar preço no histórico
                db.registrar_preco(
                    titulo=oferta["titulo"],
                    preco=oferta["preco"],
                    link_original=oferta["link_original"],
                    loja=oferta.get("loja", "Mercado Livre"),
                    preco_original=oferta.get("preco_original"),
                    departamento_id=dep_id,
                )
        db.registrar_busca("mercadolivre", "auto", len(resultados_ml))
        print(f"[ML] {len(resultados_ml)} encontradas, {novas_ml} novas")
        total_novas += novas_ml
    except Exception as e:
        print(f"[ML] Erro na busca automática: {e}")

    # Shopee
    if config.shopee_ok():
        try:
            resultados_sp = shopee_scraper.buscar_todas_palavras()
            novas_sp = 0
            for oferta in resultados_sp:
                if not db.oferta_existe(oferta["link_original"]):
                    db.criar_oferta(oferta)
                    novas_sp += 1
            db.registrar_busca("shopee", "auto", len(resultados_sp))
            print(f"[SHOPEE] {len(resultados_sp)} encontradas, {novas_sp} novas")
            total_novas += novas_sp
        except Exception as e:
            print(f"[SHOPEE] Erro na busca automática: {e}")

    print(f"[AGENDADOR] Busca concluída. {total_novas} novas ofertas adicionadas.")

    # Auto-post (no-op se AUTO_POST_ENABLED=false)
    try:
        auto_postar()
    except Exception as e:
        print(f"[AUTO-POST] Erro: {e}")

    print("=" * 50 + "\n")


def iniciar_agendador():
    """Inicia o agendador de buscas automáticas."""
    intervalo = config.BUSCA_INTERVALO_MINUTOS

    scheduler.add_job(
        tarefa_busca_automatica,
        "interval",
        minutes=intervalo,
        id="busca_automatica",
        replace_existing=True,
    )

    scheduler.start()
    print(f"[AGENDADOR] Busca automática agendada a cada {intervalo} minutos")


def parar_agendador():
    """Para o agendador."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[AGENDADOR] Parado.")
