# 🚀 Checklist de Deploy: Do PC para o Mundo Real

Você construiu uma Ferrari, agora é hora de tirá-la da garagem e colocá-la na pista. Para o sistema gerar links que funcionam no celular das pessoas e no Telegram, ele precisa estar em um servidor público (Produção).

Siga este checklist quando for subir o sistema em uma VPS (como Hetzner, DigitalOcean) ou plataforma em nuvem (como Render/Railway).

## 1. Banco de Dados e Migrações

- [ ] Instancie o PostgreSQL no servidor de produção (via Docker Compose ou serviço gerenciado).
- [ ] Conecte a aplicação apontando a variável `DATABASE_URL` no seu `.env` de produção para o IP/domínio do banco.
- [ ] **MUITO IMPORTANTE:** Aplique as migrações na produção rodando o script SQL:
  ```bash
  psql -U seu_usuario -d promo_achados -f db/migrations/2026-06-21-click-events.sql
  ```

## 2. Variáveis de Ambiente Críticas (.env)

No servidor, seu `.env` DEVE possuir estas variáveis preenchidas para que os redirects e a segurança funcionem:

- [ ] `REDIRECT_BASE_URL`: **(Obrigatório)** Deve ser o seu domínio público (ex: `https://promoachados.com.br`). Se ficar vazio, o bot mandará mensagens com `http://localhost:8000/r/...`, que obviamente darão erro no celular do cliente.
- [ ] `CLICK_IP_SALT`: Um texto aleatório e longo (ex: `bZ9xP2kQ1...`). Isso garante a criptografia do IP dos clientes pela LGPD.
- [ ] `PANEL_PASSWORD`: Uma senha forte. Sem isso, qualquer pessoa na internet que achar seu painel vai poder postar ofertas e deletar seus dados.
- [ ] `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`: As suas chaves do bot oficial.

## 3. Disparo Contínuo (Serviço de Background)

A nossa aplicação tem duas "metades". O FastAPI (que serve o painel e os redirects) e o Worker (que busca ofertas sozinho a cada X minutos).

- [ ] Garanta que o comando principal está rodando sob um gerenciador de processos (como PM2 ou Systemd):
  ```bash
  python main.py
  ```
- [ ] *Nota:* O `main.py` atual já possui a lógica de ligar os schedulers nativamente dentro do startup do FastAPI, então apenas garantir que o `main.py` não morra já é suficiente para 90% das automações básicas rodarem.

## 4. Reverse Proxy / SSL (HTTPS)

- [ ] É essencial usar o Nginx ou Caddy na frente do seu Uvicorn. O FastAPI rodará na porta 8000 local do servidor, e o Nginx vai interceptar a porta 443 (HTTPS) e jogar para o 8000.
- [ ] O HTTPS é obrigatório, pois navegadores bloqueiam cliques e redirects de links HTTP comuns. Use o **Certbot (Let's Encrypt)** para gerar um certificado gratuito em 1 minuto.

## 5. O Grande Teste Final

- [ ] Acesse seu painel pela internet: `https://seu-dominio.com/painel`.
- [ ] Poste 1 oferta no seu Telegram (canal fechado de teste).
- [ ] Acesse o Telegram no seu celular com 4G (para ter um IP externo), clique na oferta.
- [ ] Verifique se o celular abriu a Shopee/Mercado Livre corretamente.
- [ ] Volte no painel de Analytics e confirme se apareceu `1 Clique` no seu painel!

Se sim: Parabéns, a máquina de vendas está online. 💸
