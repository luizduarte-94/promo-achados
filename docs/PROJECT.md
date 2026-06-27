# Visão Geral do Sistema e Arquitetura: Promo Achados Brasil

O projeto **Promo Achados Brasil** é uma plataforma distribuída de curadoria, extração, ranqueamento e publicação automatizada de ofertas, baseada em PostgreSQL e Workers independentes. Após a estabilização da infraestrutura, o foco principal do sistema é a **Monetização Agressiva**.

## 1. Regras de Negócio de Monetização (Motor de Afiliados)

O coração da monetização está na correta ingestão e conversão de URLs originais em URLs rastreáveis de afiliado (com foco inicial no programa de afiliados da Shopee).

- **Conversão Automática**: Todo link de produto ingerido pelos scrapers deve passar por um serviço interno que gera o link de afiliado antes de salvar no banco de dados.
- **Rastreamento (Tracking) e UTMs**: Os links finais devem possuir parâmetros de tracking (UTM ou parâmetros nativos da Shopee, ex: `sub_id`) que identifiquem a origem do clique (Canal: `telegram`, `whatsapp`, `instagram`, `site`).
- **Shortlinks**: Links muito longos devem ser encurtados ou mascarados (quando a plataforma permitir) para não afugentar o clique do usuário final.
- **Flag de Alta Comissão**: Produtos da Shopee com selo de "Comissão Extra" ou cupons exclusivos devem receber uma tag especial no banco (`high_commission: boolean`) para terem prioridade na fila de publicação.

## 2. Estratégia de Publicação no Instagram (Meta Graph API)

O Instagram é tratado como um canal de topo de funil e de alto apelo visual. Toda interação com a rede deve ocorrer via **Meta Graph API** automatizada.

- **Stories**: O formato principal para cupons relâmpago e urgência. O sistema deve gerar uma imagem com o produto, preço e usar o _Link Sticker_ redirecionando direto para o link de afiliado encurtado.
- **Posts de Feed (Imagem Única)**: Focados em produtos campeões de vendas (alta demanda) ou de margem de comissão muito alta. A legenda orienta o usuário a comentar uma palavra-chave para receber o link na DM (ou link na bio).
- **Carrossel**: Publicação diária programada (ex: às 20h) com o "Top 5 Ofertas do Dia", mesclando produtos do Mercado Livre e da Shopee.

## 3. Visão de Funil de Receita por Canal

- **Telegram (Volume e Velocidade)**: Publicação frequente. Foco nos "Heavy Users" caçadores de promoção. Taxa de cliques menor, mas alto volume de disparos sem risco de banimento.
- **WhatsApp (Urgência e Conversão)**: O fundo do funil. O envio aqui é mais restrito (para não gerar spam) e reservado apenas para o _crème de la crème_ (ofertas nota 90+ do nosso motor de scoring) ou alertas de queda de preço. É onde a conversão acontece de forma quase instantânea.
- **Instagram (Topo de Funil e Marca)**: Atrai público novo pelas hashtags e engajamento visual. A monetização depende fortemente da clareza do Call-to-Action (Stories com Link).
- **Site Público (SEO e Catálogo)**: Serve como o repositório central. As pessoas buscam "Ofertas de Notebook" no Google e caem na plataforma. É a base estável da monetização.

## 4. Deploy e Migrações de Banco (Checklist)

Para garantir que o banco Postgres em produção/staging acompanhe a evolução do código, registre sempre as migrações cruciais e execute-as antes de subir a API ou os Workers.

- [ ] **Aplicar migração Shopee / high_commission no Postgres:**

  ```bash
  docker compose exec postgres psql -U promo -d promo_achados \
    -f db/migrations/2026-06-21-ofertas-high-commission.sql
  ```
