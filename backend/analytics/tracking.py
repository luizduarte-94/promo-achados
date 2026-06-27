# -*- coding: utf-8 -*-
"""
Serviço de rastreamento de cliques e redirecionamento (TASK-14).

Fluxo do redirect interno (`GET /r/{oferta_id}?c=<canal>`):
  1. resolve a URL final de afiliado da oferta (camada de monetização, TASK-10),
     já com UTMs/sub_id do canal — o usuário nunca vê o link "sujo";
  2. registra o clique em `click_events` (em background, fora do caminho do 302);
  3. a rota responde 302 para a URL resolvida.

`montar_link_redirect` é o lado "emissor": os canais (TASK-15) usam o link curto
do nosso domínio em vez do link de afiliado direto.

Persistência: usa SEMPRE o engine atual de backend.database (que os testes
reaponta via reconfigurar()), então grava no banco certo em produção e em teste.
"""

from __future__ import annotations

import hashlib

from backend import database as db
from backend.config import config
from backend.models import ClickEvent, criar_session_factory
from backend.monetization import gerar_link_afiliado, eh_link_afiliado_ml


def montar_link_redirect(oferta_id: int, canal: str) -> str:
    """Link curto do redirecionador próprio (o que vai nas mensagens).

    Ex.: https://api.promoachados.com/r/123?c=telegram
    """
    base = config.REDIRECT_BASE_URL.rstrip("/")
    return f"{base}/r/{oferta_id}?c={canal}"


def resolver_destino(oferta: dict, canal: str) -> str:
    """URL final de afiliado p/ onde o 302 aponta (resolvida nos bastidores).

    Reusa o motor de monetização (TASK-10) com o canal do clique, para que o
    relatório de afiliado da Shopee também receba o sub_id/UTMs corretos.
    """
    base = oferta.get("link_afiliado") or ""
    if not base and (oferta.get("loja") or "").strip().lower() != "mercado livre":
        base = oferta.get("link_original") or ""
    if not base:
        return ""
    # O redirect interno já registra o canal; não altere o shortlink meli.la.
    if eh_link_afiliado_ml(base):
        return base
    return gerar_link_afiliado(base, canal=canal, produto_id=oferta.get("produto_id"))


def hash_ip(ip: str | None) -> str | None:
    """Hash estável do IP (SHA-256 + salt) p/ dedup sem guardar IP em claro."""
    if not ip:
        return None
    return hashlib.sha256(f"{config.CLICK_IP_SALT}:{ip}".encode("utf-8")).hexdigest()


def registrar_clique(oferta_id: int, canal: str, ip: str | None = None) -> None:
    """Grava um ClickEvent. Chamada em background pela rota /r/ (não bloqueia 302).

    Defensiva: falha de log NUNCA deve afetar o redirecionamento do usuário.
    """
    try:
        Session = criar_session_factory(db.get_engine())
        with Session() as s:
            s.add(ClickEvent(oferta_id=oferta_id, canal=canal, ip_hash=hash_ip(ip)))
            s.commit()
    except Exception as e:  # log de analytics não pode derrubar o fluxo
        print(f"[ANALYTICS] Falha ao registrar clique (oferta={oferta_id}): {e}")
