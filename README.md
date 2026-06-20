# 🔥 Promo Achados Brasil

Sistema de automação de ofertas para **afiliados**: encontra promoções no Mercado Livre,
classifica, valida o preço e distribui no Telegram e WhatsApp com copy gerada por IA.

---

## 🧩 Stack / Linguagens

| Camada | Linguagem | Tecnologias |
|---|---|---|
| **Backend** (principal) | Python | FastAPI, Uvicorn, SQLite, APScheduler, BeautifulSoup4, requests, google-genai (Gemini) |
| **Painel admin** | JS/HTML/CSS puro | sem framework |
| **Site público** | React + TypeScript | Vite |
| **Bot espelho** | Node.js | whatsapp-web.js |
| **Testes** | Python | pytest (45 testes) |

Banco: **SQLite** (`promo_achados.db`). Versionamento: git.

---

## 🗂️ Estrutura

```
backend/
  api/routes.py     → endpoints REST (consumidos pelo painel)
  database.py       → SQLite, coletar_e_salvar, classificação por departamento
  precos.py         → revalidação de preço (fonte única: painel + auto-post)
  scrapers/
    mercadolivre.py → scraper HTML com anti-bloqueio (rate-limit + cooldown)
    shopee.py       → API de afiliado (dormente, sem credencial)
  channels/
    telegram.py     → posta no canal (copy IA + botão)
    whatsapp.py     → gera mensagem p/ copiar (formato grupo de promoção)
    instagram.py    → dormente
  copywriter.py     → copy persuasiva via Gemini
  scheduler.py      → busca automática + auto-post + monitor + espelho
  espelho.py        → lê sinais de tendência dos grupos WhatsApp
  config.py         → configurações via .env
frontend/           → painel admin (index.html / js / css)
bot-espelho/        → bot Node que observa grupos WhatsApp (whatsapp-web.js)
public-site/        → vitrine pública (React/TS, em evolução)
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

# 2. Credenciais: copie .env.example -> .env e preencha
#    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY (mínimo)

# 3. Subir o sistema
python main.py            # http://localhost:8000

# 4. Testes
python -m pytest

# 5. (opcional) Bot espelho — usar SEMPRE chip dedicado
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
  WhatsApp (manual), espelho, anti-bloqueio, auth opcional, 45 testes.
- Pendente (operacional): operar com link de afiliado, ligar o bot-espelho (chip dedicado).
- Dormente (sem credencial): Shopee, Instagram. Site público (React) em evolução.

Rotina diária de operação: ver [OPERACAO.md](OPERACAO.md).
