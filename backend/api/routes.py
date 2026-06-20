# -*- coding: utf-8 -*-
"""
Rotas REST da API — consumidas pelo dashboard frontend.
"""

import time
from urllib.parse import quote
import requests
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import RedirectResponse
from backend import database as db
from backend.precos import revalidar_preco
from backend.scrapers.mercadolivre import MercadoLivreScraper
from backend.scrapers.shopee import ShopeeScraper
from backend.channels.telegram import TelegramChannel
from backend.channels.whatsapp import WhatsAppChannel
from backend.channels.instagram import InstagramChannel
from backend.config import config

router = APIRouter(prefix="/api")

# Instâncias dos scrapers e canais
ml_scraper = MercadoLivreScraper()
shopee_scraper = ShopeeScraper()

canais = {
    "telegram": TelegramChannel(),
    "whatsapp": WhatsAppChannel(),
    "instagram": InstagramChannel(),
}


# =============================================
# OFERTAS
# =============================================

@router.get("/ofertas")
def listar_ofertas(status: str = None, loja: str = None, limite: int = 100):
    """Lista ofertas com filtros opcionais."""
    return db.listar_ofertas(status=status, loja=loja, limite=limite)


@router.post("/ofertas")
def criar_oferta(dados: dict = Body(...)):
    """Cria uma oferta manualmente."""
    oferta_id = db.criar_oferta(dados)
    return {"id": oferta_id, "mensagem": "Oferta criada com sucesso!"}


@router.get("/ofertas/{oferta_id}")
def obter_oferta(oferta_id: int):
    """Retorna uma oferta pelo ID."""
    oferta = db.obter_oferta(oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")
    return oferta


@router.get("/ofertas/{oferta_id}/mensagem")
def mensagem_oferta(oferta_id: int, canal: str = "whatsapp"):
    """Gera a mensagem pronta da oferta para copiar/colar (sem enviar).

    Retorna o texto formatado e um wa_url (link wa.me com o texto preenchido).
    """
    oferta = db.obter_oferta(oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")

    canal_obj = canais.get(canal)
    if not canal_obj:
        raise HTTPException(status_code=400, detail=f"Canal desconhecido: {canal}")

    # Revalida o preço atual para a mensagem refletir o valor real (não bloqueia o copiar).
    rev = revalidar_preco(oferta)

    texto = canal_obj.preview(oferta)
    if not texto:
        raise HTTPException(status_code=400, detail=f"Canal '{canal}' não suporta mensagem manual")

    return {
        "canal": canal,
        "texto": texto,
        "revalidacao": rev,
        "wa_url": "https://wa.me/?text=" + quote(texto),
    }


@router.put("/ofertas/{oferta_id}")
def atualizar_oferta(oferta_id: int, dados: dict = Body(...)):
    """Atualiza uma oferta (ex: colar link de afiliado)."""
    ok = db.atualizar_oferta(oferta_id, dados)
    if not ok:
        raise HTTPException(status_code=404, detail="Oferta não encontrada ou sem alterações")
    return {"mensagem": "Oferta atualizada!"}


@router.delete("/ofertas/{oferta_id}")
def deletar_oferta(oferta_id: int):
    """Remove uma oferta."""
    ok = db.deletar_oferta(oferta_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")
    return {"mensagem": "Oferta removida!"}


# =============================================
# POSTAGEM
# =============================================

@router.post("/ofertas/{oferta_id}/postar")
def postar_oferta(oferta_id: int, dados: dict = Body(...)):
    """
    Posta uma oferta nos canais selecionados.
    Body: { "canais": ["telegram", "whatsapp", "instagram"] }
    """
    oferta = db.obter_oferta(oferta_id)
    if not oferta:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")

    # Protege contra postar sem link de afiliado (evita divulgar link que nao paga).
    if not (oferta.get("link_afiliado") or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Adicione o link de afiliado antes de postar (esta oferta não tem link_afiliado)."
        )

    # Revalida o preço atual antes de postar (evita divulgar preço velho/errado).
    rev = revalidar_preco(oferta)
    if rev["status"] == "subiu":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Preço SUBIU {rev['variacao_pct']}% (de R${rev['preco_antigo']:.2f} "
                f"para R${rev['preco_novo']:.2f}). Não postei pra não divulgar errado — "
                "o card já foi atualizado, revise antes de postar."
            ),
        )
    if rev["status"] == "sumiu":
        raise HTTPException(
            status_code=409,
            detail="Produto não encontrado no ML agora (pode ter saído do ar). Não postei.",
        )

    canais_selecionados = dados.get("canais", ["telegram"])
    resultados = []

    for nome_canal in canais_selecionados:
        canal = canais.get(nome_canal)
        if not canal:
            resultados.append({"canal": nome_canal, "sucesso": False, "resposta": "Canal desconhecido"})
            continue

        if not canal.esta_configurado():
            resultados.append({
                "canal": nome_canal,
                "sucesso": False,
                "resposta": f"{nome_canal.title()} não está configurado. Verifique o .env"
            })
            continue

        resultado = canal.enviar(oferta)
        db.registrar_postagem(oferta_id, nome_canal, resultado["sucesso"], resultado["resposta"])
        resultados.append({"canal": nome_canal, **resultado})

        time.sleep(config.PAUSA_ENTRE_POSTS)

    return {"resultados": resultados}


@router.post("/ofertas/postar-lote")
def postar_lote(dados: dict = Body(...)):
    """
    Posta múltiplas ofertas.
    Body: { "ids": [1, 2, 3], "canais": ["telegram"] }
    """
    ids = dados.get("ids", [])
    canais_selecionados = dados.get("canais", ["telegram"])
    resultados = []

    for oferta_id in ids:
        oferta = db.obter_oferta(oferta_id)
        if not oferta:
            resultados.append({"oferta_id": oferta_id, "erro": "Não encontrada"})
            continue

        if not (oferta.get("link_afiliado") or "").strip():
            resultados.append({"oferta_id": oferta_id, "erro": "Sem link de afiliado — adicione antes de postar"})
            continue

        for nome_canal in canais_selecionados:
            canal = canais.get(nome_canal)
            if canal and canal.esta_configurado():
                resultado = canal.enviar(oferta)
                db.registrar_postagem(oferta_id, nome_canal, resultado["sucesso"], resultado["resposta"])
                resultados.append({"oferta_id": oferta_id, "canal": nome_canal, **resultado})
                time.sleep(config.PAUSA_ENTRE_POSTS)

    return {"resultados": resultados}


# =============================================
# BUSCA
# =============================================

@router.post("/buscar")
def buscar_ofertas(dados: dict = Body(default={})):
    """
    Dispara busca nos scrapers.
    Body opcional: { "palavra_chave": "creatina", "fontes": ["mercadolivre", "shopee"] }
    """
    palavra = dados.get("palavra_chave", "")
    fontes = dados.get("fontes", ["mercadolivre", "shopee"])
    todas_ofertas = []

    if "mercadolivre" in fontes:
        resultados = ml_scraper.buscar(palavra) if palavra else ml_scraper.buscar_todas_palavras()
        todas_ofertas.extend(db.coletar_e_salvar(resultados))
        db.registrar_busca("mercadolivre", palavra or "todas", len(resultados))

    if "shopee" in fontes:
        resultados = shopee_scraper.buscar(palavra) if palavra else shopee_scraper.buscar_todas_palavras()
        todas_ofertas.extend(db.coletar_e_salvar(resultados))
        db.registrar_busca("shopee", palavra or "todas", len(resultados))

    return {
        "encontradas": len(todas_ofertas),
        "ofertas": todas_ofertas[:20],
        "mensagem": f"Busca concluída! {len(todas_ofertas)} novas ofertas encontradas."
    }


# =============================================
# DASHBOARD / STATS
# =============================================

@router.get("/dashboard/stats")
def dashboard_stats():
    """Estatísticas para o dashboard."""
    stats = db.obter_stats()
    stats["canais"] = {
        "telegram": canais["telegram"].esta_configurado(),
        "whatsapp": canais["whatsapp"].esta_configurado(),
        "instagram": canais["instagram"].esta_configurado(),
    }
    # Verifica se existe token do ML salvo
    ml_token = db.obter_configuracao("ml_access_token")
    stats["ml_connected"] = bool(ml_token)
    return stats


@router.get("/historico")
def historico_postagens(limite: int = 50):
    """Histórico de postagens recentes."""
    return db.listar_postagens(limite=limite)


# =============================================
# CONFIGURAÇÕES
# =============================================

@router.get("/configuracoes")
def obter_configuracoes():
    """Retorna configurações atuais."""
    return {
        "palavras_chave": config.BUSCA_PALAVRAS_CHAVE,
        "intervalo_minutos": config.BUSCA_INTERVALO_MINUTOS,
        "desconto_minimo": config.BUSCA_DESCONTO_MINIMO,
        "preco_maximo": config.BUSCA_PRECO_MAXIMO,
        "pausa_entre_posts": config.PAUSA_ENTRE_POSTS,
        "telegram_chat_id": config.TELEGRAM_CHAT_ID,
    }


# =============================================
# MERCADO LIVRE OAUTH2
# =============================================

@router.get("/ml/auth_url")
def ml_auth_url():
    """Retorna a URL de redirecionamento do Mercado Livre OAuth2."""
    if not (config.ML_CLIENT_ID and config.ML_CLIENT_SECRET):
        raise HTTPException(status_code=400, detail="Mercado Livre Client ID/Secret não configurados no .env")
    
    redirect_uri = "http://localhost:8000/api/ml/callback"
    url = (
        f"https://auth.mercadolivre.com.br/authorization"
        f"?response_type=code"
        f"&client_id={config.ML_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
    )
    return {"url": url}


@router.get("/ml/callback")
def ml_callback(code: str = None, error: str = None):
    """Recebe o code temporário do Mercado Livre e troca por tokens permanentes."""
    if error or not code:
        return RedirectResponse(url="/?ml_connected=false&error=" + (error or "missing_code"))

    redirect_uri = "http://localhost:8000/api/ml/callback"
    url = f"{config.ML_API_BASE}/oauth/token"
    
    try:
        resp = requests.post(
            url,
            data={
                "grant_type": "authorization_code",
                "client_id": config.ML_CLIENT_ID,
                "client_secret": config.ML_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = int(data.get("expires_in", 21600))
        expires_at = time.time() + expires_in
        
        db.definir_configuracao("ml_access_token", access_token)
        db.definir_configuracao("ml_refresh_token", refresh_token)
        db.definir_configuracao("ml_token_expires_at", str(expires_at))
        
        return RedirectResponse(url="/?ml_connected=true")
    except Exception as e:
        print(f"[ML AUTH] Erro no callback de autorização: {e}")
        return RedirectResponse(url=f"/?ml_connected=false&error=token_exchange_failed")


# =============================================
# DEPARTAMENTOS
# =============================================

@router.get("/departamentos")
def listar_deps():
    """Lista todos os departamentos ativos."""
    return db.listar_departamentos()


@router.post("/departamentos")
def criar_dep(dados: dict = Body(...)):
    """Cria um novo departamento."""
    dep_id = db.criar_departamento(
        nome=dados.get("nome", "Novo Departamento"),
        emoji=dados.get("emoji", "📦"),
        palavras_chave=dados.get("palavras_chave", ""),
    )
    return {"id": dep_id, "mensagem": "Departamento criado!"}


@router.put("/departamentos/{dep_id}")
def atualizar_dep(dep_id: int, dados: dict = Body(...)):
    """Atualiza um departamento."""
    ok = db.atualizar_departamento(dep_id, dados)
    if not ok:
        raise HTTPException(status_code=404, detail="Departamento não encontrado")
    return {"mensagem": "Departamento atualizado!"}


# =============================================
# HISTÓRICO DE PREÇOS
# =============================================

@router.get("/historico-precos")
def historico_precos(link: str = None, titulo: str = None, limite: int = 180):
    """Retorna histórico de preços de um produto."""
    return db.obter_historico_precos(link_original=link, titulo=titulo, limite=limite)


@router.get("/historico-precos/menor")
def menor_preco(link: str):
    """Retorna o menor preço histórico de um produto."""
    menor = db.obter_menor_preco(link)
    return {"menor_preco": menor}


# =============================================
# PRODUTOS RECORRENTES
# =============================================

@router.get("/produtos-recorrentes")
def listar_recorrentes():
    """Lista produtos recorrentes monitorados."""
    return db.listar_produtos_recorrentes()


@router.post("/produtos-recorrentes")
def criar_recorrente(dados: dict = Body(...)):
    """Cadastra um produto recorrente."""
    prod_id = db.criar_produto_recorrente(dados)
    return {"id": prod_id, "mensagem": "Produto recorrente cadastrado!"}


@router.put("/produtos-recorrentes/{prod_id}")
def atualizar_recorrente(prod_id: int, dados: dict = Body(...)):
    """Atualiza um produto recorrente."""
    ok = db.atualizar_produto_recorrente(prod_id, dados)
    if not ok:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return {"mensagem": "Produto atualizado!"}


@router.delete("/produtos-recorrentes/{prod_id}")
def deletar_recorrente(prod_id: int):
    """Remove um produto recorrente."""
    ok = db.deletar_produto_recorrente(prod_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return {"mensagem": "Produto removido!"}
