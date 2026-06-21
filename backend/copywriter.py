# -*- coding: utf-8 -*-
"""
Módulo de IA (Copywriting) para geração de textos persuasivos.
"""

import re
from google import genai
from backend.config import config

# Cache em memória: evita re-chamar o Gemini para a mesma oferta (mesmo título,
# preço e cupom). Reduz custo e latência em postagens repetidas / em lote.
_COPY_CACHE: dict[tuple, str] = {}
_COPY_CACHE_MAX = 500

# Cache das frases persuasivas curtas (WhatsApp), por título.
_FRASE_CACHE: dict[str, str] = {}


def gerar_frase_persuasiva(oferta: dict) -> str:
    """Gera UMA frase de venda curta (<= 15 palavras) para inserir na mensagem.

    Texto puro: sem HTML, sem markdown, sem links, sem preço, sem emoji.
    Retorna "" se a IA estiver desligada ou falhar (o chamador segue sem a frase).
    """
    titulo = (oferta.get("titulo") or "").strip()
    if not titulo:
        return ""

    if titulo in _FRASE_CACHE:
        return _FRASE_CACHE[titulo]

    client = obter_client_ia()
    if not client:
        return ""

    prompt = (
        "Gere UMA frase de venda curta e persuasiva (máximo 15 palavras) para o "
        f"produto abaixo, em português do Brasil.\n\nProduto: {titulo}\n\n"
        "Regras: apenas a frase, sem aspas, sem links, sem preço, sem hashtag, "
        "sem emoji e sem quebra de linha."
    )
    try:
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        frase = (resp.text or "").strip().strip('"').replace("\n", " ")
        if frase:
            if len(_FRASE_CACHE) >= _COPY_CACHE_MAX:
                _FRASE_CACHE.clear()
            _FRASE_CACHE[titulo] = frase
        return frase
    except Exception as e:
        print(f"[IA Copywriter] Erro ao gerar frase: {e}")
        return ""


def obter_client_ia():
    if config.GEMINI_API_KEY:
        # Tenta criar o client com a chave
        try:
            return genai.Client(api_key=config.GEMINI_API_KEY)
        except Exception as e:
            print(f"[IA Copywriter] Erro ao configurar Client: {e}")
            return None
    return None

def gerar_copy_oferta(oferta: dict) -> str:
    """
    Usa o Gemini para gerar um texto de vendas curto e persuasivo para o Telegram.
    Retorna o texto em formato HTML compatível com a API do Telegram.
    """
    client = obter_client_ia()
    if not client:
        return ""

    titulo = oferta.get("titulo", "")
    preco = oferta.get("preco", 0)
    preco_orig = oferta.get("preco_original", "")
    desconto = oferta.get("desconto_pct", 0)
    loja = oferta.get("loja", "Loja")

    # Extrai o cupom e forma de pagamento se existir.
    # Cupom relâmpago pode vir top-level (TASK-09) ou em dados_extra (legado).
    dados_extra = oferta.get("dados_extra", {})
    cupom = oferta.get("cupom") or dados_extra.get("cupom", "")
    pagamento = dados_extra.get("forma_pagamento", "")

    # Cache: mesma oferta não re-chama o Gemini
    cache_key = (titulo, preco, cupom)
    if cache_key in _COPY_CACHE:
        return _COPY_CACHE[cache_key]
    
    prompt = f"""
Você é um copywriter profissional especialista em ofertas no Telegram.
Sua missão é criar uma mensagem PERSUASIVA para o seguinte produto:

Produto: {titulo}
Preço Original: R$ {preco_orig}
Preço Atual: R$ {preco}
Desconto: {desconto:.0f}%
Loja: {loja}
Forma de Pagamento: {pagamento}
"""

    if cupom:
        prompt += f"\nATENÇÃO: Este produto tem um CUPOM de desconto: '{cupom}'!\n"
        preco_final_cupom = None
        try:
            match_rs = re.search(r'R\$\s*([\d\.,]+)', cupom, re.IGNORECASE)
            match_pct = re.search(r'(\d+(?:\.\d+)?)%', cupom)
            if match_rs:
                val_str = match_rs.group(1).replace('.', '').replace(',', '.')
                if val_str.count('.') > 1:
                    val_str = val_str.replace('.', '', val_str.count('.') - 1)
                preco_final_cupom = float(preco) - float(val_str)
            elif match_pct:
                preco_final_cupom = float(preco) * (1 - (float(match_pct.group(1)) / 100))
        except Exception:
            pass

        if preco_final_cupom and preco_final_cupom < float(preco):
            prompt += f"-> O Preço Final aplicando o cupom cai para R$ {preco_final_cupom:.2f}!\n"
            prompt += f"VOCÊ DEVE DAR DESTAQUE ABSOLUTO PARA O PREÇO FINAL COM CUPOM (R$ {preco_final_cupom:.2f}) NO TEXTO!\n"
            prompt += "Exemplo: 'Por apenas R$ 800 usando o cupom!'\n"
        else:
            prompt += "Você DEVE destacar esse cupom no texto e avisar o usuário para usá-lo na hora da compra.\n"

    prompt += """
Regras de Estrutura Visual e Copywriting:
O cliente quer uma copy PROFISSIONAL e de ALTA CONVERSÃO. O grande segredo é o respiro (linhas em branco) para facilitar a leitura.

Siga EXATAMENTE este layout estrutural (Não mude a ordem, nem junte as linhas):

‼️ [Escreva 2 palavras de urgência, ex: Esgota Rápido, Estoque Baixo, etc] ‼️
[Título do Produto Limpo e Resumido]

[Uma única frase de copy muito persuasiva vendendo o produto, máximo 15 palavras]

De: <s>R$ [Preço Original]</s>
Por: <b>R$ [Preço Final]</b>

💳 [Forma de Pagamento, ex: no PIX ou em 10x sem juros]
🎟️ [Se houver cupom, escreva: Utilize o cupom: XYZ]
(O desconto do cupom entra na tela de pagamento)

👇 Toque no botão abaixo para garantir antes que acabe:

Regras adicionais:
- Respeite rigorosamente as linhas em branco do layout acima. Não crie blocos de texto grudados.
- PROIBIDO escrever mais de 1 frase na parte da "copy".
- NÃO escreva as palavras "Compre em" ou coloque links. O link já vai no botão.
- A formatação deve usar HTML suportado pelo Telegram (<b>, <i>, <s>). NÃO USE MARKDOWN (* ou **).

Gere APENAS o texto da mensagem final.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        texto = response.text.strip()
        if texto:
            if len(_COPY_CACHE) >= _COPY_CACHE_MAX:
                _COPY_CACHE.clear()
            _COPY_CACHE[cache_key] = texto
        return texto
    except Exception as e:
        print(f"[IA Copywriter] Erro ao gerar texto: {e}")
        return ""


