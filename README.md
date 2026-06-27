# 🔥 Promo Achados Brasil

Sistema de automação de ofertas para **afiliados**: encontra promoções no Mercado Livre,
classifica, valida o preço e distribui no Telegram e WhatsApp com copy gerada por IA.

---

## 🧩 Stack / Linguagens

| Camada | Linguagem | Tecnologias |
|---|---|---|
| **Backend** (principal) | Python | FastAPI, Uvicorn, PostgreSQL (SQLAlchemy), APScheduler, BeautifulSoup4, requests, google-genai (Gemini) |
| **Painel admin + vitrine** | JS/HTML/CSS puro | sem framework (mesma base serve o painel e a vitrine pública de leitura) |
| **Bot espelho** | Node.js | whatsapp-web.js |
| **Testes** | Python | pytest (197 testes) |

Banco: **PostgreSQL** por padrão (via SQLAlchemy, `DATABASE_URL`; ver `docker-compose.yml`). SQLite é só fallback de testes/local (`USE_SQLITE=true`). Versionamento: git.

---

## 🗂️ Estrutura

```
backend/
  api/routes.py     → endpoints REST (consumidos pelo painel)
  database.py       → camada de dados (SQLAlchemy/Postgres), coletar_e_salvar, classificação
  precos.py         → revalidação de preço (fonte única: painel + auto-post)
  scrapers/
    mercadolivre.py → scraper HTML com anti-bloqueio (rate-limit + cooldown)
    shopee.py       → API de afiliado (dormente, sem credencial)
  channels/
    telegram.py     → posta no canal (copy IA + botão)
    whatsapp.py     → gera mensagem p/ copiar (formato grupo de promoção)
    instagram.py    → dormente
  copywriter.py     → copy persuasiva via Gemini
  scheduler.py      → jobs: busca automática + auto-post + monitor + espelho
  scheduler_worker.py → processo SEPARADO que roda os jobs (python -m backend.scheduler_worker)
  espelho.py        → lê sinais de tendência dos grupos WhatsApp
  config.py         → configurações via .env
main.py             → SÓ a API/painel/redirects (NÃO inicia os jobs)
frontend/           → painel admin + vitrine pública de leitura (index.html / js / css)
bot-espelho/        → bot Node que observa grupos WhatsApp (whatsapp-web.js)
tests/              → pytest
OPERACAO.md         → playbook de operação diária (afiliado)
```

---

## ⚙️ Como funciona (o ciclo)

1. **Coleta** — scraper do ML busca por palavra-chave (HTML, com pausa 4-8s + cooldown
   anti-bloqueio). O **espelho** observa grupos de WhatsApp e usa o *nome* dos produtos
   que bombam como sinal de tendência (nunca copia o texto dos outros).
2. **Processa** (`db.coletar_e_salvar`) — dedup por ID do produto, classifica o
   departamento, salva a oferta e grava o histórico de preço.
3. **Curadoria** — no painel você filtra por departamento e escolhe a melhor oferta.
4. **Monetiza** — cola o link de afiliado (meli.la) na oferta.
5. **Revalida o preço** — antes de postar/copiar, re-checa o preço atual no ML; bloqueia
   se subiu além do limite ou se o produto sumiu (nunca divulga preço velho).
6. **Distribui** — Telegram (copy IA + botão) ou WhatsApp (mensagem formatada p/ copiar).
7. **Automações opcionais** — busca automática (60 min), monitor de recorrentes
   (alerta de queda), auto-post (desligado por padrão).

---

## 🚀 Como rodar

```bash
# 1. Dependências Python
pip install -r requirements.txt

# 2. Banco: suba o Postgres (default) via Docker...
docker compose up -d      # Postgres em localhost:5432 (ver docker-compose.yml)
#    ...ou, p/ rodar local sem Postgres, defina USE_SQLITE=true no .env

# 3. Credenciais: copie .env.example -> .env e preencha
#    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY (mínimo)

# 4. Subir a API (painel + redirects)
python main.py            # http://localhost:8000

# 5. Subir o agendador — processo SEPARADO (sem ele, nada roda sozinho)
python -m backend.scheduler_worker

# 6. Testes
python -m pytest

# 7. (opcional) Bot espelho — usar SEMPRE chip dedicado
cd bot-espelho
npm install               # (1ª vez)
node index.js             # escaneia o QR
```

---

## 🔧 Configuração (.env)

Principais chaves (ver `.env.example` completo):

| Chave | Pra quê |
|---|---|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | postar no canal |
| `GEMINI_API_KEY` / `USAR_IA_COPYWRITER` | copy persuasiva por IA |
| `BUSCA_PALAVRAS_CHAVE` / `BUSCA_INTERVALO_MINUTOS` | busca automática |
| `REVALIDAR_PRECO_ENABLED` / `REVALIDAR_BLOQUEIO_ALTA_PCT` | revalidação de preço |
| `ESPELHO_ENABLED` / `ESPELHO_GRUPOS` | sinal de tendência do WhatsApp |
| `AUTO_POST_ENABLED` / `MONITOR_RECORRENTES_ENABLED` | automações (default off) |
| `PANEL_PASSWORD` | senha do painel (vazio = sem senha, só local) |

---

## ⚠️ Avisos importantes

- **Scraper ML:** uso anônimo de baixo volume; pior caso = bloqueio temporário de IP
  (auto-recupera com cooldown). Não é ban de conta.
- **Bot espelho (whatsapp-web.js):** cliente NÃO-OFICIAL, viola os termos do WhatsApp e
  pode **banir o número**. Use SEMPRE um **chip dedicado**, nunca o pessoal.
- **Conta de afiliado:** nunca compre/clique pelo próprio link (fraude = ban na hora).
- **Preço:** revalidado antes de postar, mas o ML mostra preço personalizado (Pix/login);
  pode haver pequena diferença pro comprador. Poste ofertas frescas.

---

## ✅ Estado

- Pronto: coleta, classificação, dedup, preço correto + revalidação, Telegram (IA),
  WhatsApp (manual), espelho, anti-bloqueio, auth opcional, 197 testes.
- Pendente (operacional): operar com link de afiliado, ligar o bot-espelho (chip dedicado).
- Dormente (sem credencial): Shopee, Instagram. Vitrine pública servida pelo `frontend/` (leitura).

Rotina diária de operação: ver [OPERACAO.md](OPERACAO.md).
