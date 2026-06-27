# Agentes do Claude Code

Define os limites e responsabilidades dos agentes autônomos nesta fase de **Monetização e Canais Avançados**.

## 1. `agent_monetization` (NOVO)
- **Foco Principal**: Motor de afiliação, UTMs, shortlinks e rastreamento de cliques.
- **Responsabilidades**:
  - Implementar a lógica de integração com as APIs de Afiliados (Shopee Affiliate API, Lomadee, etc) para gerar os links dinamicamente.
  - Assegurar que os links carreguem rastreios (`sub_id`, `utm_source`, `utm_campaign`).
  - Lidar com rate limits das APIs de encurtadores.
- **Limites**:
  - Restrito a pasta `backend/monetization/` e aos serviços compartilhados (`backend/config.py`).
  - **NÃO DEVE** alterar a rotina do Scheduler nem as chamadas diretas às APIs de envio do Telegram/WhatsApp.

## 2. `agent_channels`
- **Foco Principal**: Saída de dados (agora com grande foco no Instagram).
- **Responsabilidades**:
  - Construir a integração oficial e segura via Meta Graph API para o Instagram (Feed, Stories, Carrosséis).
  - Atualizar o Telegram e o WhatsApp para injetarem os links trackeados do `agent_monetization`.
- **Limites**:
  - Restrito ao diretório `backend/channels/` e lógicas de copy (`backend/copywriter.py`).
  - Deve importar os links gerados, mas **não deve** criar lógicas próprias de afiliação dentro de `telegram.py` ou `instagram.py`.

## 3. `agent_scrapers`
- **Foco Principal**: Captura agressiva de promoções relâmpago e cupons.
- **Responsabilidades**:
  - Aprofundar as técnicas de extração da Shopee.
  - Identificar tags HTML/JSON de "Flash Deal", "Cupons Ativos" ou selos de alta comissão.
  - Mapear esses novos atributos no banco de dados via ORM.
- **Limites**:
  - Focado em `backend/scrapers/*` e `backend/models.py`.
  - **NÃO DEVE** se preocupar em como os links vão virar links de afiliado (isso é responsabilidade do `agent_monetization`).

## 4. `agent_tests`
- **Foco Principal**: Garantir que as lógicas de afiliação e as chamadas ao Instagram não quebrem a aplicação.
- **Responsabilidades**:
  - Criar *mocks* bem estruturados da Graph API da Meta para testar o Instagram.
  - Garantir que a injeção de parâmetros UTMs está concatenando strings validamente.

## 5. `agent_analytics` (NOVO)
- **Foco Principal**: Inteligência de dados, rastreamento de eventos, banco de dados analítico e geração de relatórios de conversão (CTR/EPC).
- **Responsabilidades**:
  - Criar as tabelas de eventos de log (`click_events`).
  - Implementar as rotas de redirect (`/r/{oferta_id}`) que interceptam o clique.
  - Criar views ou rotas de agregação de métricas para os relatórios.
- **Limites**:
  - Trabalha no diretório `backend/analytics/`, `backend/models.py` e rotas da API em `main.py`.
  - **NÃO DEVE** alterar o comportamento de disparo dos canais nem o scraper de ingestão.
  
*(Ajuste de limite para os outros agentes)*: O `agent_channels` agora passa a depender das rotas criadas pelo `agent_analytics` para injetar os links de redirect nos disparos (em vez do link sujo). O `agent_monetization` continua isolado, sendo consumido nos bastidores para gerar o link final da Shopee antes do usuário ser redirecionado pelo Tracking.

## 6. `agent_frontend_ux`
- **Foco Principal**: Refinamento visual da Vitrine Pública (Storefront UI), garantindo layout limpo, escaneável e focado em conversão.
- **Responsabilidades**:
  - Manter a arquitetura visual clara da vitrine de ofertas: fundo claro (Light Theme), grids de produtos organizados e botões de conversão (CTAs) otimizados.
  - Agrupar e organizar os produtos em seções (ex: Mercado Livre, Shopee, Amazon) com banners laterais (âncoras institucionais).
  - Escopar todas as regras CSS da vitrine (`.storefront-container`, `#tabOfertas`) para não quebrarem o Dark Theme das abas administrativas.
  - Otimizar responsividade (Mobile/Tablet) para exibir seções empilhadas verticalmente de forma harmônica.
- **Limites**:
  - Restrito à pasta `frontend/` (`index.html`, `app.js`, `style.css`).
  - **NÃO DEVE** alterar rotas da API, lógica de banco, scrapers ou integrações de envio.
  - **NÃO DEVE** introduzir frameworks externos (React, Vue, Tailwind). Todo o código deve ser Vanilla CSS/JS.
  - Toda alteração deve respeitar a premissa de *múltiplos temas convivendo no mesmo projeto* (Vitrine Light Theme + Painel Admin Dark Theme).
