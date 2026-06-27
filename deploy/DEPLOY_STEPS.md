# Deploy — promo-achados (VPS Ubuntu)

Guia operacional para subir o sistema numa VPS Ubuntu (24.04, Python 3.12).
A API e o **worker** rodam em **processos separados** (systemd). Banco: PostgreSQL.

Templates neste diretório:
- `promo-api.service` — unit da API
- `promo-worker.service` — unit do agendador
- `nginx-promo.conf` — reverse proxy + base p/ HTTPS

Premissas: deploy em `/opt/promo-achados`, usuário de serviço `promo`, domínio
com DNS `A` → IP da VPS. Substitua `SEU_DOMINIO` e `<SENHA_FORTE>` (sem secrets reais aqui).

---

## 1. VPS base e firewall

```bash
sudo adduser --system --group --home /opt/promo-achados promo
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw enable
```

> ⚠️ O Docker publica portas via iptables e **ignora o ufw**. Não confie no ufw
> para fechar o Postgres — a trava é o bind em `127.0.0.1` (passo 4).

## 2. Pacotes

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv git nginx postgresql-client \
                    docker.io docker-compose-v2
```

## 3. Código + venv

```bash
sudo -u promo git clone <repo-ou-rsync> /opt/promo-achados
cd /opt/promo-achados
sudo -u promo python3.12 -m venv .venv
sudo -u promo .venv/bin/pip install -r requirements.txt
```

## 4. Criar/preencher `.env` de produção

> ⛔ **Faça isto ANTES de subir o Postgres.** O `docker compose up -d` (passo 5)
> lê `POSTGRES_PASSWORD` e `POSTGRES_PORT=127.0.0.1:5432` do `.env`. Sem o `.env`
> pronto, o banco sobe com a senha default e/ou exposto na porta pública.
> **NÃO rode `docker compose up -d` antes de concluir este passo.**

```bash
cd /opt/promo-achados
cp .env.example .env
sudo chown promo:promo .env && sudo chmod 600 .env   # restringe o acesso ao arquivo
openssl rand -hex 24        # gere a senha → POSTGRES_PASSWORD e DATABASE_URL
openssl rand -hex 32        # gere o CLICK_IP_SALT
```

`.env` é gitignored — nunca versione. Chaves **críticas** (placeholders — sem secrets reais):

| Chave | Valor de produção |
|---|---|
| `POSTGRES_PORT` | `127.0.0.1:5432` (bind só no loopback — não expõe o banco) |
| `POSTGRES_PASSWORD` | `<SENHA_FORTE>` (a mesma usada na DATABASE_URL) |
| `DATABASE_URL` | `postgresql://promo:<SENHA_FORTE>@localhost:5432/promo_achados` |
| `USE_SQLITE` | `false` |
| `HOST` | `127.0.0.1` (fica atrás do Nginx) |
| `REDIRECT_BASE_URL` | `https://SEU_DOMINIO` (sem `/` final; nunca localhost) |
| `CLICK_IP_SALT` | aleatório longo → `openssl rand -hex 32` (LGPD; não deixar o default) |
| `PANEL_USER` / `PANEL_PASSWORD` | `admin` / `<SENHA_FORTE>` (vazio = painel aberto) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | bot oficial + canal |
| `GEMINI_API_KEY` | chave Gemini (copy IA) |
| Shopee / Instagram / WhatsApp | opcionais — vazio = canal dormente |

## 5. Subir o Postgres (Docker)

Só agora, com o `.env` preenchido — o compose lê `POSTGRES_PASSWORD` e
`POSTGRES_PORT=127.0.0.1:5432` dele:

```bash
cd /opt/promo-achados
sudo docker compose up -d
sudo docker compose ps      # postgres deve ficar "healthy"
```

Confirme que o banco NÃO está exposto (deve aparecer só loopback):

```bash
sudo ss -tlnp | grep 5432   # esperado: 127.0.0.1:5432  — NUNCA 0.0.0.0:5432
```

## 6. Migrações

Ordem obrigatória: **(a)** schema base via `db.init_db()` → **(b)** click-events →
**(c)** high-commission. O `.env` é carregado automaticamente (config resolve
`_BASE_DIR/.env`).

```bash
cd /opt/promo-achados

# (a) cria as tabelas base (SQLAlchemy create_all)
sudo -u promo .venv/bin/python -c "from backend import database as db; db.init_db()"

# (b) tabela de eventos de clique
sudo docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U promo -d promo_achados \
  < db/migrations/2026-06-21-click-events.sql

# (c) coluna high_commission nas ofertas
sudo docker compose exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U promo -d promo_achados \
  < db/migrations/2026-06-21-ofertas-high-commission.sql
```

> ⛔ **Se qualquer comando acima retornar erro, PARE.** Não rode o próximo nem
> suba os serviços. Investigue a causa (conexão/credencial errada, banco
> divergente, permissão, SQL recusado) e só prossiga depois de resolver.
> `ON_ERROR_STOP=1` faz o psql abortar no primeiro erro em vez de seguir adiante.

Verificar o resultado:

```bash
sudo docker compose exec -T postgres psql -U promo -d promo_achados -c "\dt click_events"
sudo docker compose exec -T postgres psql -U promo -d promo_achados -c "\d ofertas" | grep high_commission
```

## 7. systemd — API e worker (processos separados)

```bash
sudo cp deploy/promo-api.service    /etc/systemd/system/
sudo cp deploy/promo-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now promo-api promo-worker
sudo systemctl status promo-api promo-worker
journalctl -u promo-api -f      # confirme "Banco de dados inicializado" no boot
```

> A API não inicia o agendador. Sem `promo-worker` de pé, não há busca,
> auto-post nem monitor — nada roda sozinho.

## 8. Nginx + HTTPS

```bash
sudo cp deploy/nginx-promo.conf /etc/nginx/sites-available/promo
sudo ln -s /etc/nginx/sites-available/promo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d SEU_DOMINIO     # emite o cert e força HTTPS
```

## 9. Teste final

```bash
# 1. Painel/vitrine sobe
curl -I https://SEU_DOMINIO/                       # 200

# 2. Redirect de clique (use um <ID> de oferta com link de afiliado)
curl -I "https://SEU_DOMINIO/r/<ID>?c=telegram"    # espera 302 + header Location

# 3. Analytics contou o clique (rota protegida por Basic Auth)
curl -u "admin:<SENHA_FORTE>" "https://SEU_DOMINIO/analytics/summary"
#    confira no JSON: cliques do canal "telegram" >= 1
```

Fluxo real: poste 1 oferta no Telegram de teste → clique pelo celular (4G, IP
externo) → veja o clique aparecer no painel de Analytics.

## 10. bot-espelho (opcional)

```bash
cd /opt/promo-achados/bot-espelho
npm install
node index.js     # escaneia o QR — SEMPRE chip dedicado (cliente não-oficial pode banir o número)
```

Para manter de pé: `pm2 start index.js --name promo-espelho` ou um 3º systemd unit.

---

## Riscos a fechar antes de subir

- **Banco:** `DATABASE_URL` apontando pro Postgres real com `<SENHA_FORTE>` — o default `promo:promo` é só dev.
- **Exposição do Postgres:** `POSTGRES_PORT=127.0.0.1:5432` + checar com `ss` (Docker fura o ufw).
- **HTTPS:** obrigatório; sem cert o Basic Auth do painel vaza a senha.
- **LGPD:** trocar `CLICK_IP_SALT` do default público por aleatório.

## TODO (melhorias futuras — exigem mudar código, fora deste pacote)

- **CORS no FastAPI via env:** hoje `main.py` sobe com `allow_origins=["*"]` e o
  Nginx só reescreve o header (paliativo). Mover para `CORSMiddleware` lendo uma
  env (ex. `CORS_ALLOW_ORIGINS`) deixa a origem versionada/testável e dispensa o
  `proxy_hide_header`.
- **IP real atrás do proxy:** o log de cliques usa `request.client.host`. Atrás do
  Nginx isso pode registrar `127.0.0.1`; habilitar forwarded-headers no uvicorn
  (`--forwarded-allow-ips`) ou ler `X-Forwarded-For` faz o hash de IP refletir o cliente.
