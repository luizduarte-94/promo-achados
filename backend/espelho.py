# -*- coding: utf-8 -*-
"""
Espelho de grupos WhatsApp -> termos de busca (sinal de tendência).

O bot-espelho (Node/whatsapp-web.js) grava cada mensagem dos grupos monitorados
em data/espelho_inbox.jsonl (uma linha JSON por mensagem). Este módulo lê as
LINHAS NOVAS desde o último ciclo (offset em data/espelho_inbox.offset), extrai
o NOME do produto de cada mensagem e devolve como termos de busca.

IMPORTANTE: nunca copiamos o texto dos outros grupos (plágio + risco). Só
usamos QUAL produto está bombando para buscar nas fontes e gerar oferta própria
(link e copy nossos).
"""

import json
import re

from backend.config import config

_LINK = re.compile(r"(https?://\S+)|(www\.\S+)", re.IGNORECASE)
_PRECO = re.compile(r"R\$\s?\d[\d.,]*", re.IGNORECASE)
# Emojis e símbolos diversos.
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿←-⇿⬀-⯿]")
# Palavras de promoção que não ajudam a identificar o produto.
_LIXO = re.compile(
    r"\b(cupom|frete\s*gr[áa]tis|oferta[s]?|promo[cç][aã]o|desconto|"
    r"por\s+apenas|por|apenas|use|ganhe|garanta|aproveite|corre|"
    r"s[óo]\s+hoje|link\s+na\s+bio|imperd[íi]vel|baixou|menor\s+pre[çc]o|"
    r"compre|clique|aqui)\b",
    re.IGNORECASE,
)


def _ler_offset() -> int:
    try:
        return int(config.ESPELHO_OFFSET.read_text())
    except (OSError, ValueError):
        return 0


def _salvar_offset(pos: int) -> None:
    config.ESPELHO_OFFSET.parent.mkdir(parents=True, exist_ok=True)
    config.ESPELHO_OFFSET.write_text(str(pos))


def extrair_produto(texto: str) -> str:
    """Tira link, preço, emoji e palavras de promoção -> sobra o nome do produto."""
    if not texto:
        return ""
    t = _LINK.sub(" ", texto)
    # O nome do produto vem ANTES do preço; corta o resto (preço, cupom, CTA).
    m = _PRECO.search(t)
    if m and m.start() > 0:
        t = t[: m.start()]
    t = _PRECO.sub(" ", t)
    t = _EMOJI.sub(" ", t)
    t = _LIXO.sub(" ", t)
    t = re.sub(r"[^\wÀ-ÿ ]", " ", t)  # remove pontuação/símbolos restantes
    t = re.sub(r"\s+", " ", t).strip()
    # primeiras ~6 palavras = termo de busca
    return " ".join(t.split()[:6])


def termos_do_espelho(max_termos: int | None = None) -> list[str]:
    """Lê as mensagens novas do inbox e devolve termos de busca deduplicados.

    Avança o offset sobre TODAS as linhas lidas (o sinal é transitório). O
    `max_termos` só limita quantos termos buscamos por ciclo (o ML tem rate
    limit agressivo).
    """
    inbox = config.ESPELHO_INBOX
    if not config.ESPELHO_ENABLED or not inbox.exists():
        return []

    pos = _ler_offset()
    termos: list[str] = []
    try:
        with inbox.open("r", encoding="utf-8") as f:
            f.seek(pos)
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    obj = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                termo = extrair_produto(obj.get("text", ""))
                if len(termo) >= 4:  # ignora ruído curtinho
                    termos.append(termo)
            _salvar_offset(f.tell())
    except OSError as e:
        print(f"[ESPELHO] Erro ao ler inbox: {e}")
        return []

    # dedup preservando ordem
    vistos: set[str] = set()
    saida: list[str] = []
    for t in termos:
        k = t.lower()
        if k not in vistos:
            vistos.add(k)
            saida.append(t)

    limite = max_termos if max_termos is not None else config.ESPELHO_MAX_TERMOS
    return saida[:limite]
