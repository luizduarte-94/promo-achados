# -*- coding: utf-8 -*-
"""
Worker do agendador — processo SEPARADO da API (TASK-06).

A API FastAPI (main.py) só responde HTTP. Os jobs contínuos (busca automática,
auto-post, monitor de recorrentes, espelho) rodam aqui, num processo próprio,
reusando a mesma camada de dados (backend/database.py -> Postgres).

Uso:
    python -m backend.scheduler_worker

Encerra com Ctrl+C (SIGINT) ou SIGTERM — desliga o agendador com segurança.
"""

from __future__ import annotations

import signal
import threading
import time

from backend import database as db
from backend.config import config
from backend.scheduler import iniciar_agendador, parar_agendador

_parar = threading.Event()


def _on_signal(signum, _frame):
    print(f"\n[WORKER] Sinal {signum} recebido — encerrando...")
    _parar.set()


def main() -> None:
    print("=" * 55)
    print("  PROMO ACHADOS BRASIL - Worker (agendador)")
    print("=" * 55)

    db.init_db()
    print(f"  [OK] Banco: {db.get_engine().url.render_as_string(hide_password=True)}")

    signal.signal(signal.SIGINT, _on_signal)
    try:
        signal.signal(signal.SIGTERM, _on_signal)
    except (ValueError, AttributeError):
        pass  # SIGTERM pode não existir em alguns ambientes (ex.: Windows)

    iniciar_agendador()
    print(f"  [OK] Agendador ativo (busca a cada {config.BUSCA_INTERVALO_MINUTOS} min).")
    print("  Ctrl+C para encerrar.\n")

    try:
        while not _parar.is_set():
            time.sleep(1)
    finally:
        parar_agendador()
        print("  Worker finalizado.\n")


if __name__ == "__main__":
    main()
