# -*- coding: utf-8 -*-
"""
Agendador de tarefas — busca automática de ofertas em intervalos configuráveis.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from backend.scrapers.mercadolivre import MercadoLivreScraper
from backend.scrapers.shopee import ShopeeScraper
from backend import database as db
from backend.config import config


scheduler = BackgroundScheduler()
ml_scraper = MercadoLivreScraper()
shopee_scraper = ShopeeScraper()


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
