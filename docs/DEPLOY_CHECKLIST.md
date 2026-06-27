# 🚀 Checklist de Deploy: Do PC para o Mundo Real

Você construiu uma Ferrari, agora é hora de tirá-la da garagem e colocá-la na pista. Para o sistema gerar links que funcionam no celular das pessoas e no Telegram, ele precisa estar em um servidor público (Produção).

Siga este checklist quando for subir o sistema em uma VPS (como Hetzner, DigitalOcean) ou plataforma em nuvem (como Render/Railway).

## 1. Banco de Dados e Migrações

- [ ] Instancie o PostgreSQL no servidor de produção (via Docker Compose ou serviço gerenciado).
- [ ] Conecte a aplicação apontando a variável `DATABASE_URL` no seu `.env` de produção para o IP/domínio do banco.
- [ ] **MUITO IMPORTANTE:** Aplique TODAS as migrações na produção, na ordem:
  ```bash
  psql -U seu_usuario -d promo_achados -f db/migrations/2026-06-21-click-events.sql
  psql -U seu_usuario -d promo_achados -f db/migrations/2026-06-21-ofertas-high-commission.sql
  ```

## 2. Variáveis de Ambiente Críticas (.env)

No servidor, seu `.env` DEVE possuir estas variáveis preenchidas para que os redirects e a segurança funcionem:

- [ ] `REDIRECT_BASE_URL`: **(Obrigatório)** Deve ser o seu domínio público (ex: `https://promoachados.com.br`). Se ficar vazio, o bot mandará mensagens com `http://localhost:8000/r/...`, que obviamente darão erro no celular do cliente.
- [ ] `CLICK_IP_SALT`: Um texto aleatório e longo (ex: `bZ9xP2kQ1...`). Isso garante a criptografia do IP dos clientes pela LGPD.
- [ ] `PANEL_PASSWORD`: Uma senha forte. Sem isso, qualquer pessoa na internet que achar seu painel vai poder postar ofertas e deletar seus dados.
- [ ] `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`: As suas chaves do bot oficial.

## 3. Disparo Contínuo (Serviço de Background)

A aplicação tem duas "metades" que rodam em **processos separados**. O `main.py` sobe SÓ a API/painel/redirects — ele **não** inicia nenhum agendador. Os jobs automáticos (busca, auto-post, monitor de recorrentes, espelho) vivem no worker `backend.scheduler_worker`.

- [ ] Rode os **dois** processos sob um gerenciador (PM2 ou Systemd), cada um como serviço próprio:
  ```bash
  python main.py                      # API + painel + redirects (porta 8000)
  python -m backend.scheduler_worker  # agendador (busca/auto-post/monitor/espelho)
  ```
- [ ] **Atenção:** se você só subir o `main.py`, as automações NÃO rodam — nada será buscado nem postado sozinho. O worker precisa estar de pé e ser reiniciado junto com a API.

## 4. Reverse Proxy / SSL (HTTPS)

- [ ] É essencial usar o Nginx ou Caddy na frente do seu Uvicorn. O FastAPI rodará na porta 8000 local do servidor, e o Nginx vai interceptar a porta 443 (HTTPS) e jogar para o 8000.
- [ ] O HTTPS é obrigatório, pois navegadores bloqueiam cliques e redirects de links HTTP comuns. Use o **Certbot (Let's Encrypt)** para gerar um certificado gratuito em 1 minuto.
- [ ] **HTTPS também por segurança:** o painel usa Basic Auth (usuário/senha em base64, NÃO criptografado). Sob HTTP puro a senha trafega de forma recuperável. Só exponha o painel atrás de HTTPS.
- [ ] **Restrinja o CORS:** o `main.py` sobe com `allow_origins=["*"]` (liberado, conveniente em dev). Em produção, limite a origem ao seu domínio — no reverse proxy (Nginx) ou ajustando o middleware — para o painel não aceitar requisições de qualquer site.

## 5. O Grande Teste Final

- [ ] Acesse seu painel pela internet na raiz: `https://seu-dominio.com/` (o painel é servido em `/` — não existe rota `/painel`).
- [ ] Poste 1 oferta no seu Telegram (canal fechado de teste).
- [ ] Acesse o Telegram no seu celular com 4G (para ter um IP externo), clique na oferta.
- [ ] Verifique se o celular abriu a Shopee/Mercado Livre corretamente.
- [ ] Volte no painel de Analytics e confirme se apareceu `1 Clique` no seu painel!

Se sim: Parabéns, a máquina de vendas está online. 💸
