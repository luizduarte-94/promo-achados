# -*- coding: utf-8 -*-
"""
PROMO ACHADOS BRASIL - BOT v2 (LISTA DE OFERTAS)
================================================
Mesma ideia do anterior, mas agora voce NAO precisa mexer no codigo a cada
oferta. Voce so adiciona suas ofertas na LISTA 'OFERTAS' la embaixo, e o bot
posta TODAS, uma de cada vez, no seu canal do Telegram.

Ideal pro fluxo MANUAL do Mercado Livre (e serve pra Shopee tambem):
  1) No painel do ML, gere o link de afiliado do produto (encurtador meli.la).
  2) Copie titulo, preco, imagem e o link.
  3) Cole tudo como mais um item na lista OFERTAS abaixo.
  4) Rode o arquivo: python promo_bot.py

COMO USAR (1a vez):
  - Cole o TOKEN do BotFather na linha indicada (o mesmo de antes).
  - No terminal:  pip install requests
  - Rode:  python promo_bot.py

REGRAS DE OURO DO MERCADO LIVRE (pra nao perder comissao):
  - Use SEMPRE o link meli.la oficial. NUNCA encurte com bit.ly e afins.
  - So poste produto de vendedor com REPUTACAO VERDE.
  - Mantenha o aviso de "link de afiliado" (ja vem no rodape).
"""

import time
import requests


# ======================================================================
# CONFIGURACAO
# ======================================================================
TOKEN = "8806303452:AAEPUUNuJUu5ex7HyNRERP9WeEMC3LY42Lc"     # o mesmo token de antes
CHAT_ID = "@promoachadosbrasiloficial"       # seu canal (ja preenchido)

PAUSA_ENTRE_POSTS = 3   # segundos de pausa entre uma oferta e outra
# ======================================================================


def montar_post(oferta):
    """Monta o TEXTO do post. Obrigatorios: titulo, preco, loja, link."""
    linhas = []

    if oferta.get("urgencia"):
        linhas.append(f"\u203c\ufe0f {oferta['urgencia']} \u203c\ufe0f")
        linhas.append("")

    linhas.append(oferta["titulo"])
    linhas.append("")

    preco = f"*Por: R$ {oferta['preco']}*"
    if oferta.get("preco_obs"):
        preco += f" {oferta['preco_obs']}"
    linhas.append(preco)
    if oferta.get("preco_unidade"):
        linhas.append(f"({oferta['preco_unidade']})")
    linhas.append("")

    if oferta.get("cupom"):
        if oferta.get("cupom_condicao"):
            linhas.append(oferta["cupom_condicao"])
        linhas.append(f"Utilize o cupom: *{oferta['cupom']}*")
        linhas.append("")

    if oferta.get("obs_vendedor"):
        linhas.append(f"\u2022 {oferta['obs_vendedor']}")
        linhas.append("")

    if oferta.get("frete"):
        linhas.append(oferta["frete"])
        linhas.append("")

    linhas.append(f"*{oferta['loja']}:*")
    linhas.append(f"Compre em: {oferta['link']}")
    linhas.append("")

    linhas.append("Promocao por tempo limitado")

    if oferta.get("link_grupos"):
        linhas.append("")
        linhas.append(oferta.get("texto_grupos", "Participe dos nossos outros grupos:"))
        linhas.append(oferta["link_grupos"])

    linhas.append("")
    linhas.append("\U0001f517 Contem links de afiliado")

    return "\n".join(linhas)


def postar_oferta(oferta):
    """Monta o texto e envia pro canal. Com 'imagem' manda foto+legenda."""

    if "COLE" in TOKEN:
        print("[AVISO] Voce ainda nao colou o TOKEN do BotFather.")
        return None

    texto = montar_post(oferta)

    if oferta.get("imagem"):
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        imagem_url = oferta["imagem"]
        
        # Tenta baixar a imagem para enviar por upload (mais garantido que o Telegram processar a URL diretamente)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res_img = requests.get(imagem_url, headers=headers, timeout=15)
            if res_img.ok:
                ext = "jpg"
                if ".png" in imagem_url.lower():
                    ext = "png"
                elif ".webp" in imagem_url.lower():
                    ext = "webp"
                
                arquivos = {"photo": (f"imagem.{ext}", res_img.content)}
                dados = {
                    "chat_id": CHAT_ID,
                    "caption": texto,
                    "parse_mode": "Markdown",
                }
                resposta = requests.post(url, data=dados, files=arquivos)
            else:
                raise Exception(f"Status HTTP {res_img.status_code}")
        except Exception as e:
            print(f"[AVISO] Nao foi possivel enviar a imagem por upload ({e}). Tentando enviar por link direto...")
            dados = {
                "chat_id": CHAT_ID,
                "photo": imagem_url,
                "caption": texto,
                "parse_mode": "Markdown",
            }
            resposta = requests.post(url, data=dados)
    else:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        dados = {
            "chat_id": CHAT_ID,
            "text": texto,
            "parse_mode": "Markdown",
        }
        resposta = requests.post(url, data=dados)

    if resposta.ok and resposta.json().get("ok"):
        print(f"[SUCESSO] Postado: {oferta['titulo'][:40]}...")
    else:
        print(f"[AVISO] Erro ao postar '{oferta['titulo'][:40]}...':")
        print("   ", resposta.text)

    return resposta


# ======================================================================
# SUAS OFERTAS - adicione/edite os itens desta lista.
# Cada oferta e um bloco { ... }. Copie um bloco pra criar outra oferta.
# Para o 1o teste, deixe a "imagem" comentada; depois ative com a URL real.
# ======================================================================
OFERTAS = [

    # ---- Oferta 1 (exemplo Mercado Livre) ----
    {
        "urgencia": "Esgota Rapido",
        "titulo": "Creatina Monohidratada Growth 250g",   # troque pelo nome real
        "preco": "59,90",
        "loja": "Mercado Livre",
        "link": "https://meli.la/1cnFt3E",   # seu link de afiliado meli.la
        # "imagem": "https://COLE_A_URL_DA_IMAGEM_DO_PRODUTO.jpg",
        "link_grupos": "https://t.me/promoachadosbrasiloficial",
        "texto_grupos": "Entre no canal:",
    },

    # ---- Oferta 2 (copie o bloco acima e edite) ----
    # {
    #     "titulo": "Outro produto",
    #     "preco": "00,00",
    #     "loja": "Mercado Livre",
    #     "link": "https://meli.la/SEULINK",
    #     "imagem": "https://...jpg",
    # },

]


if __name__ == "__main__":
    if not OFERTAS:
        print("Sua lista OFERTAS esta vazia. Adicione pelo menos uma oferta.")
    for i, oferta in enumerate(OFERTAS, 1):
        print(f"\n[{i}/{len(OFERTAS)}] enviando...")
        postar_oferta(oferta)
        if i < len(OFERTAS):
            time.sleep(PAUSA_ENTRE_POSTS)
    print("\nConcluido.")
