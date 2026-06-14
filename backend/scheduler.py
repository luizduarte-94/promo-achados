# -*- coding: utf-8 -*-
"""
Agendador de tarefas — busca automática de ofertas em intervalos configuráveis.
"""

import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from backend.scrapers.mercadolivre import MercadoLivreScraper
from backend.scrapers.shopee import ShopeeScraper
from backend.channels.telegram import TelegramChannel
from backend.scoring import score_oferta
from backend.espelho import termos_do_espelho
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

    # Espelho: grupos WhatsApp como sinal de tendência (no-op se ESPELHO_ENABLED=false)
    try:
        total_novas += buscar_do_espelho()
    except Exception as e:
        print(f"[ESPELHO] Erro: {e}")

    print(f"[AGENDADOR] Busca concluída. {total_novas} novas ofertas adicionadas.")

    # Auto-post (no-op se AUTO_POST_ENABLED=false)
    try:
        auto_postar()
    except Exception as e:
        print(f"[AUTO-POST] Erro: {e}")

    print("=" * 50 + "\n")


def _casar_recorrente(rec: dict, resultados: list[dict]) -> dict | None:
    """Escolhe, entre os resultados da busca, qual corresponde ao recorrente.

    Prioriza o resultado com mesmo ID de produto (MLB/Shopee) quando o
    recorrente tem link; caso contrário, pega o de menor preço.
    """
    if not resultados:
        return None

    pid = db.extrair_produto_id(rec.get("link_original"))
    if pid:
        for r in resultados:
            if db.extrair_produto_id(r.get("link_original")) == pid:
                return r

    return min(resultados, key=lambda r: r.get("preco", float("inf")))


def monitorar_recorrentes():
    """Rebusca os produtos recorrentes e alerta no Telegram quando o preço cai.

    No-op se MONITOR_RECORRENTES_ENABLED=false. Alerta quando o preço atual
    cruza o preço alvo OU bate um novo menor preço histórico.
    """
    if not config.MONITOR_RECORRENTES_ENABLED:
        return
    if not telegram.esta_configurado():
        print("[MONITOR] Telegram não configurado. Pulando.")
        return

    recorrentes = db.listar_produtos_recorrentes(apenas_ativos=True)
    if not recorrentes:
        print("[MONITOR] Nenhum recorrente ativo.")
        return

    print(f"[MONITOR] Checando {len(recorrentes)} produto(s) recorrente(s)...")
    for rec in recorrentes:
        try:
            resultados = ml_scraper.buscar(rec["titulo"], filtrar_qualidade=False)
            match = _casar_recorrente(rec, resultados)
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not match:
                db.atualizar_produto_recorrente(rec["id"], {"ultimo_check": agora})
                print(f"[MONITOR] #{rec['id']} sem match para '{rec['titulo']}'")
                continue

            preco_novo = match["preco"]
            alvo = rec.get("preco_alvo")
            min_ant = rec.get("preco_minimo")
            atual_ant = rec.get("preco_atual")

            # Histórico (alimenta o gráfico da UI)
            db.registrar_preco(
                titulo=rec["titulo"],
                preco=preco_novo,
                link_original=match.get("link_original") or rec.get("link_original"),
                loja=match.get("loja", rec.get("loja")),
                preco_original=match.get("preco_original"),
                departamento_id=rec.get("departamento_id"),
            )

            # Decisão de alerta (anti-spam: alvo só ao cruzar; mínimo só se estritamente menor)
            bateu_alvo = bool(alvo) and preco_novo <= alvo and (atual_ant is None or atual_ant > alvo)
            novo_min = min_ant is not None and preco_novo < min_ant
            deve_alertar = bateu_alvo or novo_min

            # Update do recorrente
            novo_minimo = preco_novo if min_ant is None else min(min_ant, preco_novo)
            db.atualizar_produto_recorrente(rec["id"], {
                "preco_atual": preco_novo,
                "preco_minimo": novo_minimo,
                "ultimo_check": agora,
            })

            if deve_alertar:
                oferta = {
                    "titulo": rec["titulo"],
                    "preco": preco_novo,
                    "preco_original": min_ant or alvo,
                    "desconto_pct": match.get("desconto_pct", 0),
                    "loja": match.get("loja", rec.get("loja", "Mercado Livre")),
                    "link_original": match.get("link_original") or rec.get("link_original"),
                    "link_afiliado": None,
                    "imagem_url": match.get("imagem_url"),
                    "frete_gratis": match.get("frete_gratis", False),
                    "dados_extra": match.get("dados_extra", {}),
                }
                resultado = telegram.enviar(oferta)
                motivo = "alvo" if bateu_alvo else "novo minimo"
                print(f"[MONITOR] #{rec['id']} BAIXOU ({motivo}) -> R${preco_novo} | telegram={resultado['sucesso']}")
                time.sleep(config.PAUSA_ENTRE_POSTS)
            else:
                print(f"[MONITOR] #{rec['id']} sem queda relevante (R${preco_novo})")
        except Exception as e:
            print(f"[MONITOR] Erro no recorrente #{rec.get('id')}: {e}")


def buscar_do_espelho() -> int:
    """Busca produtos sinalizados pelos grupos-espelho do WhatsApp.

    Lê os termos novos de data/espelho_inbox.jsonl (gravado pelo bot-espelho),
    busca cada um no ML (e Shopee, se configurada) e salva as ofertas novas com
    fonte 'espelho'. NÃO copia o texto dos grupos — só usa o produto como sinal.
    Retorna a quantidade de ofertas novas adicionadas.
    """
    if not config.ESPELHO_ENABLED:
        return 0

    termos = termos_do_espelho()
    if not termos:
        return 0

    print(f"[ESPELHO] {len(termos)} termo(s) dos grupos: {termos}")
    novas = 0
    for termo in termos:
        # Mercado Livre (já filtra desconto/preço por padrão)
        try:
            for oferta in ml_scraper.buscar(termo):
                if db.oferta_existe(oferta["link_original"]):
                    continue
                oferta["fonte"] = "espelho"
                dep_id = db.classificar_departamento(oferta["titulo"])
                if dep_id:
                    oferta["departamento_id"] = dep_id
                db.criar_oferta(oferta)
                db.registrar_preco(
                    titulo=oferta["titulo"],
                    preco=oferta["preco"],
                    link_original=oferta["link_original"],
                    loja=oferta.get("loja", "Mercado Livre"),
                    preco_original=oferta.get("preco_original"),
                    departamento_id=dep_id,
                )
                novas += 1
        except Exception as e:
            print(f"[ESPELHO][ML] Erro em '{termo}': {e}")

        # Shopee (se houver credenciais)
        if config.shopee_ok():
            try:
                for oferta in shopee_scraper.buscar(termo):
                    if db.oferta_existe(oferta["link_original"]):
                        continue
                    oferta["fonte"] = "espelho"
                    db.criar_oferta(oferta)
                    novas += 1
            except Exception as e:
                print(f"[ESPELHO][SHOPEE] Erro em '{termo}': {e}")

    db.registrar_busca("espelho", ", ".join(termos)[:200], novas)
    print(f"[ESPELHO] {novas} nova(s) oferta(s) a partir dos grupos.")
    return novas


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

    if config.MONITOR_RECORRENTES_ENABLED:
        intervalo_mon = config.MONITOR_RECORRENTES_INTERVALO_MINUTOS
        scheduler.add_job(
            monitorar_recorrentes,
            "interval",
            minutes=intervalo_mon,
            id="monitor_recorrentes",
            replace_existing=True,
        )
        print(f"[AGENDADOR] Monitoramento de recorrentes agendado a cada {intervalo_mon} minutos")

    scheduler.start()
    print(f"[AGENDADOR] Busca automática agendada a cada {intervalo} minutos")


def parar_agendador():
    """Para o agendador."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[AGENDADOR] Parado.")
