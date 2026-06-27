# -*- coding: utf-8 -*-
"""
Agendador de tarefas — busca automática de ofertas em intervalos configuráveis.
"""

import json
import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from backend.scrapers.mercadolivre import MercadoLivreScraper
from backend.scrapers.shopee import ShopeeScraper
from backend.channels.telegram import TelegramChannel
from backend.scoring import score_oferta
from backend.espelho import termos_do_espelho
from backend import database as db
from backend import precos
from backend.config import config
from backend.monetization import oferta_tem_link_afiliado_valido


# --- Observabilidade: logs estruturados (JSON) dos jobs (TASK-08) ---
logger = logging.getLogger("promo.jobs")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))  # a mensagem já é JSON
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _log(**campos):
    """Emite uma linha de log estruturada (JSON) com timestamp."""
    campos.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
    logger.info(json.dumps(campos, ensure_ascii=False, default=str))


def _dur_ms(inicio: float) -> float:
    return round((time.perf_counter() - inicio) * 1000, 1)


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
        if oferta_tem_link_afiliado_valido(o)
        and score_oferta(o) >= config.AUTO_POST_SCORE_MINIMO
    ]
    candidatas.sort(key=score_oferta, reverse=True)
    candidatas = candidatas[: config.AUTO_POST_MAX_POR_CICLO]

    if not candidatas:
        print("[AUTO-POST] Nenhuma oferta elegível (sem link afiliado ou score baixo).")
        return

    inicio = time.perf_counter()
    publicadas = puladas = erros = 0
    print(f"[AUTO-POST] Postando {len(candidatas)} oferta(s) no Telegram...")
    for oferta in candidatas:
        # Revalida o preço antes de postar — nunca divulga preço velho (igual ao manual).
        rev = precos.revalidar_preco(oferta)
        if rev["status"] in ("subiu", "sumiu"):
            puladas += 1
            _log(job_name="auto_post", evento="publicacao", canal="telegram",
                 offer_id=oferta["id"], status="pulada", motivo=rev["status"])
            print(f"[AUTO-POST] #{oferta['id']} pulada (preço {rev['status']}).")
            continue
        resultado = telegram.enviar(oferta)
        db.registrar_postagem(oferta["id"], "telegram", resultado["sucesso"], resultado["resposta"])
        if resultado["sucesso"]:
            publicadas += 1
        else:
            erros += 1
        _log(job_name="auto_post", evento="publicacao", canal="telegram",
             offer_id=oferta["id"], status="ok" if resultado["sucesso"] else "erro")
        print(f"[AUTO-POST] #{oferta['id']} score={score_oferta(oferta)} -> {resultado['sucesso']}")
        time.sleep(config.PAUSA_ENTRE_POSTS)

    _log(job_name="auto_post", status="erro" if erros else "ok", duration_ms=_dur_ms(inicio),
         publicadas=publicadas, puladas=puladas, erros=erros)


def tarefa_busca_automatica():
    """Executa busca automática em todas as fontes configuradas."""
    print("\n" + "=" * 50)
    print("[AGENDADOR] Iniciando busca automática...")
    print("=" * 50)

    inicio = time.perf_counter()
    total_novas = 0
    erros = 0

    # Mercado Livre
    try:
        resultados_ml = ml_scraper.buscar_todas_palavras()
        novas_ml = len(db.coletar_e_salvar(resultados_ml))
        db.registrar_busca("mercadolivre", "auto", len(resultados_ml))
        print(f"[ML] {len(resultados_ml)} encontradas, {novas_ml} novas")
        total_novas += novas_ml
        _log(job_name="busca_automatica", evento="scrape", fonte="mercadolivre",
             status="ok", encontradas=len(resultados_ml), capturadas=novas_ml)
    except Exception as e:
        erros += 1
        _log(job_name="busca_automatica", evento="scrape", fonte="mercadolivre",
             status="erro", error=f"{type(e).__name__}: {e}")
        print(f"[ML] Erro na busca automática: {e}")

    # Shopee
    if config.shopee_ok():
        try:
            resultados_sp = shopee_scraper.buscar_todas_palavras()
            novas_sp = len(db.coletar_e_salvar(resultados_sp))
            db.registrar_busca("shopee", "auto", len(resultados_sp))
            print(f"[SHOPEE] {len(resultados_sp)} encontradas, {novas_sp} novas")
            total_novas += novas_sp
            _log(job_name="busca_automatica", evento="scrape", fonte="shopee",
                 status="ok", encontradas=len(resultados_sp), capturadas=novas_sp)
        except Exception as e:
            erros += 1
            _log(job_name="busca_automatica", evento="scrape", fonte="shopee",
                 status="erro", error=f"{type(e).__name__}: {e}")
            print(f"[SHOPEE] Erro na busca automática: {e}")

    # Espelho: grupos WhatsApp como sinal de tendência (no-op se ESPELHO_ENABLED=false)
    try:
        total_novas += buscar_do_espelho()
    except Exception as e:
        erros += 1
        _log(job_name="busca_automatica", evento="espelho", status="erro",
             error=f"{type(e).__name__}: {e}")
        print(f"[ESPELHO] Erro: {e}")

    print(f"[AGENDADOR] Busca concluída. {total_novas} novas ofertas adicionadas.")
    _log(job_name="busca_automatica", status="erro" if erros else "ok",
         duration_ms=_dur_ms(inicio), capturadas=total_novas, erros=erros)

    # Auto-post (no-op se AUTO_POST_ENABLED=false)
    try:
        auto_postar()
    except Exception as e:
        _log(job_name="auto_post", status="erro", error=f"{type(e).__name__}: {e}")
        print(f"[AUTO-POST] Erro: {e}")

    print("=" * 50 + "\n")


def _casar_recorrente(rec: dict, resultados: list[dict]) -> dict | None:
    """Escolhe, entre os resultados da busca, qual corresponde ao recorrente.

    Prioriza o resultado com mesmo ID de produto (MLB/Shopee); caso não ache,
    cai para o de menor preço (monitoramento é best-effort).
    """
    if not resultados:
        return None
    match = precos.casar_por_produto_id(rec.get("link_original"), resultados)
    return match or min(resultados, key=lambda r: r.get("preco", float("inf")))


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
    inicio = time.perf_counter()
    checados = alertas = erros = 0
    for rec in recorrentes:
        checados += 1
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
                alertas += 1
                motivo = "alvo" if bateu_alvo else "novo minimo"
                _log(job_name="monitor_recorrentes", evento="alerta", canal="telegram",
                     offer_id=rec["id"], status="ok" if resultado["sucesso"] else "erro",
                     motivo=motivo, preco=preco_novo)
                print(f"[MONITOR] #{rec['id']} BAIXOU ({motivo}) -> R${preco_novo} | telegram={resultado['sucesso']}")
                time.sleep(config.PAUSA_ENTRE_POSTS)
            else:
                print(f"[MONITOR] #{rec['id']} sem queda relevante (R${preco_novo})")
        except Exception as e:
            erros += 1
            _log(job_name="monitor_recorrentes", evento="check", offer_id=rec.get("id"),
                 status="erro", error=f"{type(e).__name__}: {e}")
            print(f"[MONITOR] Erro no recorrente #{rec.get('id')}: {e}")

    _log(job_name="monitor_recorrentes", status="erro" if erros else "ok",
         duration_ms=_dur_ms(inicio), checados=checados, alertas=alertas, erros=erros)


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
    inicio = time.perf_counter()
    novas = 0
    erros = 0
    for termo in termos:
        # Mercado Livre (já filtra desconto/preço por padrão)
        try:
            novas += len(db.coletar_e_salvar(ml_scraper.buscar(termo), fonte="espelho"))
        except Exception as e:
            erros += 1
            print(f"[ESPELHO][ML] Erro em '{termo}': {e}")

        # Shopee (se houver credenciais)
        if config.shopee_ok():
            try:
                novas += len(db.coletar_e_salvar(shopee_scraper.buscar(termo), fonte="espelho"))
            except Exception as e:
                erros += 1
                print(f"[ESPELHO][SHOPEE] Erro em '{termo}': {e}")

    db.registrar_busca("espelho", ", ".join(termos)[:200], novas)
    print(f"[ESPELHO] {novas} nova(s) oferta(s) a partir dos grupos.")
    _log(job_name="espelho", fonte="espelho", status="erro" if erros else "ok",
         duration_ms=_dur_ms(inicio), termos=len(termos), capturadas=novas, erros=erros)
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
