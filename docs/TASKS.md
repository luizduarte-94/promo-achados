# Plano de Tarefas (TASKS)

Esta lista detalha as tarefas para a iniciativa: **Integração avançada Shopee + Instagram e monetização agressiva**.

| ID | Título | Objetivo | Dependências | Agente Sugerido |
|---|---|---|---|---|
| **TASK-09** | Ingestão Avançada Shopee | Adaptar scrapers/APIs para puxar "Ofertas Relâmpago" e "Cupons" da Shopee com prioridade. | Nenhuma | `agent_scrapers` |
| **TASK-10** | Motor de Afiliados e Tracking | Criar módulo central (`backend/monetization/`) para converter links originais em links comissionados e adicionar UTMs/`sub_id`. | Nenhuma | `agent_monetization` |
| **TASK-11** | Automação de Instagram via Meta API | Construir a integração com Graph API para gerar e publicar Feed, Stories (com sticker) e Carrosséis. | TASK-10 | `agent_channels` |
| **TASK-12** | Ajuste nos Canais Existentes | Atualizar Telegram, WA e Site para consumir obrigatoriamente os links trackeados gerados na TASK-10. | TASK-10 | `agent_channels` |

---

## Detalhamento das Tarefas

### TASK-09: Ingestão de Promoções e Cupons da Shopee
- **Objetivo**: Garantir que o sistema encontre ativamente promoções relâmpago e identifique produtos com alta comissão.
- **Escopo**: `backend/scrapers/shopee.py`, `backend/models.py`.
- **Output Esperado**: O scraper consegue extrair informações de Cupons, validade (tempo expirando) e seta a flag `high_commission` no banco de dados.
- **Dependências**: Nenhuma.
- **Agente Ideal**: `agent_scrapers`.

### TASK-10: Geração e Rastreamento de Links de Afiliado (Motor de Monetização)
- **Objetivo**: Centralizar a conversão de links para que nenhum clique seja desperdiçado.
- **Escopo**: `backend/monetization/link_generator.py` (novo), `.env.example`, `database.py`.
- **Output Esperado**: Uma função/classe que recebe URL crua, Canal de Destino e Produto ID, e retorna a URL final de afiliado encurtada contendo marcações (ex: `&utm_source=telegram`).
- **Dependências**: Nenhuma.
- **Agente Ideal**: `agent_monetization`.

### TASK-11: Geração de Conteúdo e Publicação no Instagram
- **Objetivo**: Integrar o Instagram de forma robusta e diversificada.
- **Escopo**: `backend/channels/instagram.py`, `backend/templates/`.
- **Output Esperado**: Funções separadas para publicar no Feed (post único), publicar Carrossel (agrupando 5 ofertas) e publicar Story (anexando URL de afiliado). Necessário mock ou teste rodando contra a Meta Graph API V19+.
- **Dependências**: TASK-10.
- **Agente Ideal**: `agent_channels`.

### TASK-12: Atualização dos Canais Existentes para Monetização
- **Objetivo**: Fechar as pontas, garantindo que Telegram e WhatsApp puxem métricas.
- **Escopo**: `backend/channels/telegram.py`, `backend/channels/whatsapp.py`, `backend/copywriter.py`.
- **Output Esperado**: Ao acionar o disparo, os canais invocam a camada de monetização da TASK-10, passam seu respectivo nome (ex: `channel='whatsapp'`) e incluem flags no copy para cupons relâmpago.
- **Dependências**: TASK-10.
- **Agente Ideal**: `agent_channels`.

### TASK-13: Modelagem da Tabela de Eventos de Clique
- **Objetivo**: Criar a estrutura no Postgres para armazenar cada clique com granularidade alta.
- **Escopo**: `backend/models.py`, `db/migrations/`.
- **Output Esperado**: Tabela `click_events` criada via SQLAlchemy (colunas: `id`, `oferta_id`, `canal`, `created_at`, `ip_hash`). Arquivo SQL de migração registrado.
- **Dependências**: Nenhuma.
- **Agente Ideal**: `agent_analytics`.

### TASK-14: Serviço de Redirecionamento e Rastreamento
- **Objetivo**: Criar a rota na API que captura o clique, salva no banco de dados em *background* e redireciona o usuário (HTTP 302).
- **Escopo**: `main.py` (ou `backend/api/router.py`), `backend/analytics/tracking.py` (novo).
- **Output Esperado**: Rota `GET /r/{oferta_id}` que aceita o parâmetro `?c=telegram`. Ao ser acessada, ela registra o evento assincronamente e redireciona para a URL trackeada da Shopee gerada na TASK-10.
- **Dependências**: TASK-13.
- **Agente Ideal**: `agent_analytics`.

### TASK-15: Ajuste dos Canais para usar o Redirect Próprio
- **Objetivo**: Garantir que as mensagens geradas agora apontem para o nosso serviço de redirect, e não direto para a Shopee.
- **Escopo**: `backend/channels/telegram.py`, `backend/channels/whatsapp.py`, `backend/channels/instagram.py`.
- **Output Esperado**: Em vez de usar `gerar_link_afiliado` na ponta final do copy, o copy usa o link curto da própria API (ex: `https://site.com/r/123?c=instagram`). O motor interno resolve a URL de afiliado real e a rota de tracking fará o redirecionamento para ela.
- **Dependências**: TASK-14.
- **Agente Ideal**: `agent_channels`.

### TASK-16: Motor de Relatórios e Cálculo de EPC/CTR
- **Objetivo**: Consolidar os dados brutos de cliques e cruzá-los com as ofertas.
- **Escopo**: `backend/analytics/reports.py` (novo).
- **Output Esperado**: Rota ou script que agrupa os dados e devolve: Total de Cliques por Canal, Ofertas com maior CTR, Estimativa de Faturamento (EPC).
- **Dependências**: TASK-13, TASK-14.
- **Agente Ideal**: `agent_analytics`.

---

## Fase: Refinamento UX do Painel Admin

TASKs atômicas para refinar a experiência da tela de Ofertas. Contexto completo em `docs/PROJECT.md` §6.

| ID | Título | Objetivo | Escopo | Agente |
|---|---|---|---|---|
| **TASK-17** | Hierarquia visual do card de oferta | Reorganizar o `.offer-body` em 3 níveis de informação (preço+título / desconto+status / meta sob demanda). | `app.js` (`_cardOferta`), `style.css` | `agent_frontend_ux` |
| **TASK-18** | Ações primárias vs secundárias no card | Destacar TG como ação principal (maior, cor sólida). Agrupar IG/WA/Link em overflow `•••` ou ícones menores. Separar Lixeira do grupo principal. | `app.js` (`_cardOferta`, `offer-footer`), `style.css` | `agent_frontend_ux` |
| **TASK-19** | Redução de badges sobre a imagem | Manter apenas desconto (top-left) e loja (bottom-right). Mover "FRETE GRÁTIS" para o body como chip. Reduzir tamanho/opacidade de `.badge-store`. | `app.js` (`_cardOferta`), `style.css` | `agent_frontend_ux` |
| **TASK-20** | Filtros segmentados com labels de grupo | Separar os 3 grupos de filtro com labels pequenos ("Status:", "Loja:", "Departamento:") e espaçamento visual entre eles. | `index.html` (seção `tabOfertas`), `style.css` | `agent_frontend_ux` |
| **TASK-21** | Feedback visual de seleção em lote | Card selecionado ganha borda `var(--brand-primary)` + leve glow. Barra de lote (`btnPostarLote` + `btnSelecionarTudo`) fica `position: sticky; top: 0` ao rolar. | `app.js`, `style.css` | `agent_frontend_ux` |
| **TASK-22** | Contraste e legibilidade de microtextos | Revisar os `font-size` e `color` de: `.offer-seller` (11px/tertiary), `.offer-dept` (10px), `.offer-status` (10px), cupomInfo (12px inline). Garantir ratio WCAG AA (4.5:1) contra `--bg-elevated`. | `style.css` | `agent_frontend_ux` |
| **TASK-23** | Contador de ofertas e estado vazio contextual | Exibir "Suas Ofertas (N de M)" no panel-title. Mensagem de estado vazio diferenciada por filtro ativo ("Nenhuma oferta postada" vs "Nenhuma oferta da Shopee"). | `app.js` (`renderizarOfertas`), `index.html` | `agent_frontend_ux` |

### Detalhamento das TASKs de Refinamento

### TASK-17: Hierarquia Visual do Card de Oferta
- **Objetivo**: Garantir que o operador identifique preço e título em < 1 segundo ao escanear a grid.
- **Escopo**: `frontend/js/app.js` (função `_cardOferta`), `frontend/css/style.css`.
- **O que mudar**:
  - **Nível 1**: Preço (`offer-price-current`) sobe de 22px para 24px. Título mantém 13.5px mas cor muda de `#60a5fa` (azul link) para `var(--text-primary)` (branco), para parar de parecer um link clicável.
  - **Nível 2**: Desconto, preço antigo, cupom e status permanecem visíveis, mas com `font-size` e `margin` reduzidos (~10-11px).
  - **Nível 3**: Vendedor e departamento movem para uma `div.offer-meta-secondary` com `opacity: 0.7`, que ganha `opacity: 1` no hover do card.
- **Teste**: Abrir o painel com 20+ ofertas e confirmar que preço/título dominam o primeiro olhar.
- **Dependências**: Nenhuma.

### TASK-18: Ações Primárias vs Secundárias no Card
- **Objetivo**: Eliminar fadiga de decisão. O operador deve ter 1 ação dominante e as outras acessíveis mas discretas.
- **Escopo**: `frontend/js/app.js` (`_cardOferta`, `offer-footer`), `frontend/css/style.css`.
- **O que mudar**:
  - Botão TG vira ação principal: `flex: 2`, padding maior, fonte 13px.
  - Botões IG/WA/Link viram ícones compactos (sem texto, apenas emoji, `width: 36px`), com `title` tooltip.
  - Lixeira sai do grupo principal e vai para o canto superior direito do card (aparece só no hover, como o checkbox).
- **Teste**: Clicar em TG deve ser o gesto mais natural. Confirmar que IG/WA/Link ainda funcionam via ícone.
- **Dependências**: Nenhuma.

### TASK-19: Redução de Badges sobre a Imagem
- **Objetivo**: Liberar área visual da foto do produto (principal gatilho de compra por impulso).
- **Escopo**: `frontend/js/app.js` (`_cardOferta`), `frontend/css/style.css`.
- **O que mudar**:
  - Badge de desconto (`-XX%`) permanece em `top-left` (é a informação mais relevante sobre a imagem).
  - Badge de loja (`MERCADO LIVRE` / `SHOPEE`) fica com `opacity: 0.6` e fonte menor (8px) para não competir.
  - Badge de "FRETE GRÁTIS" sai da imagem e vira um chip pequeno ao lado do preço no `.offer-body`.
- **Teste**: Verificar que a imagem do produto é mais visível com menos sobreposição.
- **Dependências**: Nenhuma.

### TASK-20: Filtros Segmentados com Labels de Grupo
- **Objetivo**: O operador deve saber instantaneamente qual filtro está ativo em cada camada.
- **Escopo**: `frontend/index.html`, `frontend/css/style.css`.
- **O que mudar**:
  - Adicionar labels `<span class="filter-label">Status:</span>`, `<span class="filter-label">Loja:</span>`, `<span class="filter-label">Categoria:</span>` antes de cada grupo de chips.
  - CSS `.filter-label`: font-size 10px, text-transform uppercase, color `var(--text-tertiary)`, letter-spacing 1px, margin-right 6px.
  - Separar os 3 blocos com `gap: 16px` entre eles (verticalmente).
- **Teste**: Filtrar por "Pendentes" + "Mercado Livre" + "Fitness & Academia" e confirmar que os 3 filtros ativos são visualmente distinguíveis.
- **Dependências**: Nenhuma.

### TASK-21: Feedback Visual de Seleção em Lote
- **Objetivo**: Deixar claro quais cards estão selecionados e manter a barra de ações acessível ao rolar.
- **Escopo**: `frontend/js/app.js`, `frontend/css/style.css`.
- **O que mudar**:
  - Quando o checkbox é marcado, adicionar classe `.selected` no card via JS (`onchange`). CSS: `.offer-card.selected { border-color: var(--brand-primary); box-shadow: var(--shadow-glow-brand); }`.
  - Barra de ações em lote (contendo `btnSelecionarTudo` e `btnPostarLote`) envolvida em uma `div.lote-bar` com `position: sticky; top: 0; z-index: 10; background: var(--bg-card); padding: 12px 0; border-bottom: 1px solid var(--border-subtle);`.
- **Teste**: Selecionar 5 ofertas, rolar a lista e confirmar que a barra de lote permanece visível no topo.
- **Dependências**: Nenhuma.

### TASK-22: Contraste e Legibilidade de Microtextos
- **Objetivo**: Garantir que os textos menores não desapareçam contra o fundo escuro.
- **Escopo**: `frontend/css/style.css`.
- **O que mudar**:
  - `.offer-seller`: subir de `var(--text-tertiary)` (#5c5c7a) para `var(--text-secondary)` (#9d9db8).
  - `.offer-status`: subir padding para `4px 10px`, font-size para `11px`.
  - Cupom (inline style): migrar para classe CSS `.offer-cupom` com cor `#d4bfff` (mais legível que `#c4b5fd`).
- **Teste**: Verificar contraste mínimo 4.5:1 com ferramentas do DevTools (Accessibility).
- **Dependências**: Nenhuma.

### TASK-23: Contador de Ofertas e Estado Vazio Contextual
- **Objetivo**: O operador deve saber quantas ofertas está vendo e por que a lista está vazia.
- **Escopo**: `frontend/js/app.js` (`renderizarOfertas`).
- **O que mudar**:
  - Após aplicar os filtros, atualizar o `.panel-title` com `Suas Ofertas (${lista.length} de ${this.ofertas.length})`.
  - Quando `lista.length === 0`, customizar a mensagem vazia com base no filtro ativo:
    - filtroAtual === 'postada' → "Nenhuma oferta postada ainda"
    - filtroAtual === 'cupom' → "Nenhuma oferta com cupom encontrada"
    - filtroAtual === 'shopee' → "Nenhuma oferta da Shopee — ative as credenciais no .env"
  - **Não** customizar para cada combinação; apenas para os filtros de primeiro nível.
- **Teste**: Filtrar por "Shopee" com credenciais vazias e verificar a mensagem contextual.
- **Dependências**: Nenhuma.

