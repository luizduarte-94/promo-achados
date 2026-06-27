/**
 * PROMO ACHADOS BRASIL — Dashboard v2
 * Professional UI · Sidebar Navigation · Warm Palette
 */

const API = '';

const App = {
    filtroAtual: 'todas',
    filtroDep: 'todos',
    departamentos: [],
    ofertas: [],
    currentTab: 'dashboard',
    vitrineLoja: null,     // null | 'Mercado Livre' | 'Shopee' | 'Amazon' | '__cupom__'
    vitrineTermo: '',

    // =============================================
    // INIT
    // =============================================

    async init() {
        // Verifica parâmetros de retorno da conexão do Mercado Livre
        const params = new URLSearchParams(window.location.search);
        const mlConnected = params.get('ml_connected');
        if (mlConnected === 'true') {
            this.toast('Mercado Livre conectado com sucesso! 🎉', 'success');
            window.history.replaceState({}, document.title, window.location.pathname);
        } else if (mlConnected === 'false') {
            const err = params.get('error') || 'unknown';
            this.toast(`Erro ao conectar Mercado Livre: ${err} ❌`, 'error');
            window.history.replaceState({}, document.title, window.location.pathname);
        }

        // Na VITRINE pública (#vitrine), carrega só a lista de ofertas (endpoint
        // público de leitura). Evita chamar APIs de admin protegidas — que dispara-
        // riam prompt de Basic Auth para visitantes públicos quando há senha.
        const naVitrine = location.hash === '#vitrine' || location.hash === '#site';
        if (naVitrine) {
            await this.carregarOfertas();
        } else {
            await Promise.all([
                this.carregarStats(),
                this.carregarDepartamentos(),
                this.carregarOfertas(),
                this.carregarConfig(),
                this.carregarHistorico(),
                this.carregarAnalytics(),
            ]);
            setInterval(() => this.carregarStats(), 30000);
        }

        // Roteamento simples por hash: #vitrine abre a loja pública; vazio = admin.
        window.addEventListener('hashchange', () => this._aplicarRota());
        this._aplicarRota();
    },

    // =============================================
    // NAVIGATION
    // =============================================

    switchTab(tabName, el) {
        // Update nav items
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        if (el) el.classList.add('active');

        // Update page title
        const titles = {
            dashboard: 'Dashboard',
            ofertas: 'Ofertas',
            buscar: 'Buscar Ofertas',
            historico: 'Histórico',
            recorrentes: 'Produtos Recorrentes',
            analytics: 'Analytics',
            config: 'Configurações',
        };
        document.getElementById('pageTitle').textContent = titles[tabName] || tabName;

        // Show/hide tabs
        ['Dashboard', 'Ofertas', 'Buscar', 'Historico', 'Recorrentes', 'Analytics', 'Config'].forEach(t => {
            const section = document.getElementById('tab' + t);
            if (section) section.style.display = 'none';
        });

        const target = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
        if (target) target.style.display = '';

        this.currentTab = tabName;

        if (tabName === 'historico') this.carregarHistorico();
        if (tabName === 'recorrentes') this.carregarRecorrentes();
        if (tabName === 'analytics') this.carregarAnalytics();

        // Close mobile sidebar
        document.querySelector('.sidebar')?.classList.remove('open');
    },

    // =============================================
    // STATS
    // =============================================

    async carregarStats() {
        try {
            const resp = await fetch(`${API}/api/dashboard/stats`);
            const data = await resp.json();

            document.getElementById('kpiTotal').textContent = data.total_ofertas || 0;
            document.getElementById('kpiPendentes').textContent = data.pendentes || 0;
            document.getElementById('kpiPostadas').textContent = data.postadas || 0;
            document.getElementById('kpiPostadasHoje').textContent = data.postadas_hoje || 0;
            document.getElementById('kpiDesconto').textContent = `${data.desconto_medio || 0}%`;
            document.getElementById('kpiBuscas').textContent = data.buscas_hoje || 0;

            // Badge
            const badge = document.getElementById('navBadgeOfertas');
            if (badge) {
                badge.textContent = data.pendentes > 0 ? data.pendentes : '';
                badge.style.display = data.pendentes > 0 ? '' : 'none';
            }

            // Sidebar channels
            const canais = data.canais || {};
            const footer = document.getElementById('sidebarFooter');
            footer.innerHTML = `
                <div class="sidebar-channels">
                    <div class="sidebar-channels-title">Canais</div>
                    <div class="channel-status">
                        <span class="channel-dot ${canais.telegram ? 'online' : 'offline'}"></span>
                        Telegram
                    </div>
                    <div class="channel-status">
                        <span class="channel-dot ${canais.whatsapp ? 'online' : 'offline'}"></span>
                        WhatsApp
                    </div>
                    <div class="channel-status">
                        <span class="channel-dot ${canais.instagram ? 'online' : 'offline'}"></span>
                        Instagram
                    </div>
                </div>
            `;
            // Status do Mercado Livre nas configurações
            const mlStatus = document.getElementById('mlConnectionStatus');
            const mlSubtitle = document.getElementById('mlConnectionSubtitle');
            const mlBtn = document.getElementById('btnConnectMl');
            if (mlStatus && mlSubtitle && mlBtn) {
                if (data.ml_connected) {
                    mlStatus.textContent = 'Status: Conectado ✅';
                    mlStatus.style.color = '#10b981';
                    mlSubtitle.textContent = 'O scraper do Mercado Livre usará sua conta oficial.';
                    mlBtn.style.display = 'none';
                } else {
                    mlStatus.textContent = 'Status: Não Conectado ❌';
                    mlStatus.style.color = '#ef4444';
                    mlSubtitle.textContent = 'Clique para autorizar o acesso oficial do aplicativo.';
                    mlBtn.style.display = 'inline-block';
                }
            }
        } catch (e) {
            console.error('Erro ao carregar stats:', e);
        }
    },

    // =============================================
    // OFERTAS
    // =============================================

    async carregarOfertas() {
        try {
            const resp = await fetch(`${API}/api/ofertas`);
            this.ofertas = await resp.json();
            this.renderizarOfertas();
            if (document.body.classList.contains('vitrine-ativa')) this.renderVitrine();
        } catch (e) {
            console.error('Erro ao carregar ofertas:', e);
        }
    },

    filtrar(filtro) {
        this.filtroAtual = filtro;
        document.querySelectorAll('#filterBar .chip').forEach(c => c.classList.remove('active'));
        document.querySelector(`#filterBar [data-filter="${filtro}"]`)?.classList.add('active');
        this.renderizarOfertas();
    },

    // =============================================
    // DEPARTAMENTOS
    // =============================================

    async carregarDepartamentos() {
        try {
            const resp = await fetch(`${API}/api/departamentos`);
            this.departamentos = await resp.json();
            this.renderDeptChips();
        } catch (e) {
            console.error('Erro ao carregar departamentos:', e);
        }
    },

    renderDeptChips() {
        const bar = document.getElementById('deptFilterBar');
        if (!bar) return;
        const chip = (dep, label, active) =>
            `<button class="chip ${active ? 'active' : ''}" data-dep="${dep}" onclick="App.filtrarDep('${dep}')">${label}</button>`;
        const chips = [chip('todos', 'Todos Deptos', this.filtroDep === 'todos')];
        for (const d of this.departamentos) {
            chips.push(chip(d.id, `${d.emoji} ${this._esc(d.nome)}`, String(this.filtroDep) === String(d.id)));
        }
        bar.innerHTML = chips.join('');
    },

    filtrarDep(dep) {
        this.filtroDep = dep;
        document.querySelectorAll('#deptFilterBar .chip').forEach(c => c.classList.remove('active'));
        document.querySelector(`#deptFilterBar [data-dep="${dep}"]`)?.classList.add('active');
        this.renderizarOfertas();
    },

    abrirModalDepartamento() {
        document.getElementById('modalNovoDepartamento').style.display = '';
    },
    fecharModalDepartamento() {
        document.getElementById('modalNovoDepartamento').style.display = 'none';
    },
    async salvarNovoDepartamento() {
        const nome = document.getElementById('depNome').value.trim();
        const emoji = document.getElementById('depEmoji').value.trim() || '📦';
        const palavras = document.getElementById('depPalavras').value.trim();
        if (!nome) { this.toast('Informe o nome do departamento', 'error'); return; }
        try {
            await fetch(`${API}/api/departamentos`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nome, emoji, palavras_chave: palavras }),
            });
            this.toast(`Departamento "${emoji} ${nome}" criado!`, 'success');
            this.fecharModalDepartamento();
            ['depNome', 'depEmoji', 'depPalavras'].forEach(id => document.getElementById(id).value = '');
            await this.carregarDepartamentos();
        } catch (e) { this.toast(`Erro: ${e.message}`, 'error'); }
    },

    renderizarOfertas() {
        const grid = document.getElementById('offersGrid');
        let lista = [...this.ofertas];

        if (this.filtroAtual === 'pendente') lista = lista.filter(o => o.status === 'pendente');
        else if (this.filtroAtual === 'postada') lista = lista.filter(o => o.status === 'postada');
        else if (this.filtroAtual === 'cupom') lista = lista.filter(o => o.dados_extra && o.dados_extra.cupom);
        else if (this.filtroAtual === 'ml') lista = lista.filter(o => o.loja === 'Mercado Livre');
        else if (this.filtroAtual === 'shopee') lista = lista.filter(o => o.loja === 'Shopee');

        if (this.filtroDep !== 'todos') {
            lista = lista.filter(o => String(o.departamento_id) === String(this.filtroDep));
        }

        // Atualiza titulo
        const panelTitle = document.querySelector('#tabOfertas .panel-title');
        if (panelTitle) {
            panelTitle.textContent = `Suas Ofertas (${lista.length} de ${this.ofertas.length})`;
        }

        if (lista.length === 0) {
            grid.innerHTML = `<div class="offers-grid">${this._emptyState()}</div>`;
            this.atualizarBotaoLote();
            return;
        }

        // Admin = grade simples de cards (dashboard escuro). A vitrine pública
        // (aparência de loja) é uma view separada — ver renderVitrine().
        grid.innerHTML = `<div class="offers-grid">${lista.map(o => this._cardOferta(o)).join('')}</div>`;
        this.atualizarBotaoLote();   // estado .selected/botão consistente após render
    },

    _emptyState() {
        const msgs = {
            postada: 'Nenhuma oferta postada ainda',
            cupom: 'Nenhuma oferta com cupom encontrada',
            shopee: 'Nenhuma oferta da Shopee — ative as credenciais no .env',
            ml: 'Nenhuma oferta do Mercado Livre com os filtros atuais',
            pendente: 'Todas as ofertas já foram postadas! 🎉',
        };
        const emptyMsg = msgs[this.filtroAtual] || 'Nenhuma oferta encontrada';
        return `
            <div class="empty-vitrine" style="grid-column:1/-1;">
                <div class="empty-icon">🛍️</div>
                <div class="empty-text">${emptyMsg}</div>
                <div class="empty-hint">Ajuste os filtros ou faça uma nova vitrine.</div>
                <button class="btn btn-brand btn-sm" style="margin-top:16px;"
                        onclick="App.switchTab('buscar', document.querySelector('[data-tab=buscar]'))">🔍 Buscar Ofertas</button>
            </div>
        `;
    },

    _cardOferta(o) {
        const desc = o.desconto_pct > 0 ? `<span class="badge badge-discount">-${Math.round(o.desconto_pct)}%</span>` : '';
        const storeClass = o.loja === 'Mercado Livre' ? 'ml' : (o.loja === 'Amazon' ? 'amazon' : 'shopee');
        const storeIcon = o.loja === 'Mercado Livre' ? '🟡' : (o.loja === 'Amazon' ? '📦' : '🟠');
        const freteChip = o.frete_gratis ? `<span class="offer-frete-chip">Frete grátis</span>` : '';

        const img = o.imagem_url || `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><rect fill='%231a1a30' width='200' height='200'/><text x='100' y='110' text-anchor='middle' fill='%235c5c7a' font-size='40'>📦</text></svg>`;

        const precoFmt = this.fmtPreco(o.preco);
        const origFmt = o.preco_original && o.preco_original > o.preco
            ? `<span class="offer-price-old">${this.fmtPreco(o.preco_original)}</span>` : '';

        const statusCls = o.status || 'pendente';
        const statusTxt = statusCls === 'postada' ? 'POSTADA' : 'PENDENTE';

        let cupomInfo = '';
        if (o.dados_extra && o.dados_extra.cupom) {
            let cupomText = this._esc(o.dados_extra.cupom);
            cupomText = cupomText.replace(/(R\$\s*[\d\.,]+|\d+(?:\.\d+)?%)/gi, '<strong style="color: #059669; font-size: 1.1em;">$1</strong>');
            cupomInfo = `<div class="offer-cupom">🎟️ ${cupomText}</div>`;
        }

        const monetizada = this.temLinkAfiliadoValido(o);
        const disabled = monetizada ? '' : 'disabled';
        const postTitle = monetizada ? 'Publicar oferta' : 'Adicione um link de afiliado válido antes de publicar';
        const linkBtn = `<button class="btn btn-ghost btn-icon-action" onclick="App.abrirModalLink(${o.id})"
            title="${monetizada ? 'Editar' : 'Adicionar'} link de afiliado">🔗</button>`;

        return `
            <div class="offer-card" id="card-${o.id}" style="position:relative;">
                <input type="checkbox" class="offer-checkbox" value="${o.id}" onchange="App.atualizarBotaoLote()"
                    title="${postTitle}" ${disabled}>
                <button class="offer-delete" onclick="App.deletarOferta(${o.id})" title="Remover oferta" aria-label="Remover">🗑️</button>
                <a href="${this._esc(o.link_original)}" target="_blank" style="text-decoration: none; color: inherit;">
                    <div class="offer-img-wrap">
                        <img class="offer-img" src="${img}" alt="${this._esc(o.titulo)}" loading="lazy"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 200%22><rect fill=%22%231a1a30%22 width=%22200%22 height=%22200%22/><text x=%22100%22 y=%22110%22 text-anchor=%22middle%22 fill=%22%235c5c7a%22 font-size=%2240%22>📦</text></svg>'">
                        ${desc}
                        <span class="badge badge-store ${storeClass}">${storeIcon} ${o.loja}</span>
                    </div>
                    <div class="offer-body">
                        <div class="offer-title">${this._esc(o.titulo)}</div>
                        <div class="offer-pricing">
                            <span class="offer-price-current">${precoFmt}</span>
                            ${origFmt}
                        </div>
                        ${freteChip}
                        ${cupomInfo}
                        <div class="offer-meta">
                            <span class="offer-status ${statusCls}">${statusTxt}</span>
                        </div>
                        <div class="offer-meta-secondary">
                            ${o.departamento_nome ? `<span class="offer-dept">${o.departamento_emoji || '📦'} ${this._esc(o.departamento_nome)}</span>` : ''}
                            ${o.vendedor ? `<span class="offer-seller">🏪 ${this._esc(o.vendedor)}</span>` : ''}
                        </div>
                    </div>
                </a>
                <div class="offer-footer">
                    <button class="btn btn-primary-action" id="post-telegram-${o.id}" style="background:#0088cc; color:#fff;" onclick="App.postarOferta(${o.id}, 'telegram')" title="${postTitle}" ${disabled}>📢 TG</button>
                    <button class="btn btn-icon-action" id="post-instagram-${o.id}" style="background: linear-gradient(45deg, #f09433, #dc2743, #bc1888); color:#fff;" onclick="App.postarOferta(${o.id}, 'instagram')" title="${postTitle}" ${disabled}>📸</button>
                    <button class="btn btn-ghost btn-icon-action" onclick="App.copiarWhatsApp(${o.id})" title="${postTitle}" ${disabled}>📋</button>
                    <button class="btn btn-ghost btn-icon-action" onclick="App.testarOferta(${o.id})" title="Enviar teste (canal de teste — nunca o oficial)">🧪</button>
                    ${linkBtn}
                </div>
            </div>
        `;
    },

    async copiarWhatsApp(id) {
        try {
            const resp = await fetch(`${API}/api/ofertas/${id}/mensagem?canal=whatsapp`);
            if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail || 'Falha'); }
            const data = await resp.json();
            await navigator.clipboard.writeText(data.texto);
            const rev = data.revalidacao || {};
            const oferta = this.ofertas.find(o => o.id === id);
            if (rev.status === 'sumiu') {
                this.toast('Copiado, mas ⚠️ produto sumiu do ML — confira antes de divulgar.', 'error');
            } else if (rev.status === 'subiu' || (rev.variacao_pct && Math.abs(rev.variacao_pct) >= 1)) {
                this.toast(`Copiado! Preço atualizado: R$ ${rev.preco_novo} (mudou ${rev.variacao_pct}%).`, 'info');
            } else if (oferta && !oferta.link_afiliado) {
                this.toast('Copiado! ⚠️ Sem link de afiliado — adicione antes de divulgar.', 'info');
            } else {
                this.toast('Mensagem copiada! Cole no WhatsApp 📋', 'success');
            }
        } catch (e) {
            this.toast(`Erro ao copiar: ${e.message}`, 'error');
        }
    },

    // =============================================
    // VITRINE PÚBLICA (loja separada do admin)
    // =============================================

    abrirVitrine() { location.hash = '#vitrine'; },
    sairVitrine() { location.hash = ''; },

    _aplicarRota() {
        const naVitrine = location.hash === '#vitrine' || location.hash === '#site';
        document.body.classList.toggle('vitrine-ativa', naVitrine);
        // Show/hide à prova de cache de CSS: controla display por JS (não só pela
        // classe). Evita a vitrine "vazar" crua dentro do admin se o style.css
        // estiver desatualizado no navegador.
        const ph = document.getElementById('publicHome');
        if (ph) ph.style.display = naVitrine ? 'block' : 'none';
        document.querySelectorAll('.sidebar, .sidebar-toggle, .main-content').forEach(el => {
            el.style.display = naVitrine ? 'none' : '';
        });
        if (naVitrine) this.renderVitrine();
    },

    renderVitrine() {
        this._renderPublicNav();
        this._renderPublicCategorias();
        this._renderPublicSecoes();
    },

    _renderPublicNav() {
        const nav = document.getElementById('publicNav');
        if (!nav) return;
        const itens = [
            { label: 'Marcas', loja: null },
            { label: 'Início', loja: null },
            { label: 'Amazon', loja: 'Amazon' },
            { label: 'Mercado Livre', loja: 'Mercado Livre' },
            { label: 'Shopee', loja: 'Shopee' },
            { label: 'AliExpress', loja: 'AliExpress' },
            { label: 'Temu', loja: 'Temu' },
            { label: 'Ofertas do Dia', loja: null },
            { label: 'Cupons', loja: '__cupom__' },
            { label: 'Blog', loja: null },
        ];
        nav.innerHTML = itens.map(it => {
            const ativo = (it.loja || null) === this.vitrineLoja
                || (it.label === 'Início' && !this.vitrineLoja && !this.vitrineTermo);
            return `<button class="public-nav-item ${ativo ? 'active' : ''}"
                onclick="App.vitrineNav(${it.loja ? `'${it.loja}'` : 'null'})">${it.label}</button>`;
        }).join('');
    },

    _renderPublicCategorias() {
        const box = document.getElementById('publicCategories');
        if (!box) return;
        const cats = [
            ['📱', 'Celulares'], ['💻', 'Notebooks'], ['🧺', 'Lava e Seca'], ['🍟', 'Air Fryers'],
            ['🎧', 'Eletrônicos'], ['🧽', 'Casa e Limpeza'], ['👗', 'Moda'], ['🎮', 'Games'],
        ];
        box.innerHTML = cats.map(([ic, nm]) =>
            `<div class="category-card" onclick="App.vitrineCategoria('${nm}')">
                <div class="ic">${ic}</div><div class="nm">${nm}</div>
            </div>`).join('');
    },

    _vitrineFiltrada() {
        const termo = (this.vitrineTermo || '').toLowerCase();
        return this.ofertas.filter(o => !termo || (o.titulo || '').toLowerCase().includes(termo));
    },

    _renderPublicSecoes() {
        const box = document.getElementById('publicSections');
        if (!box) return;
        const base = this._vitrineFiltrada();

        const sec = (key, titulo, desc, itens, cap) => itens.length
            ? this._publicSecaoMarketplace(key, titulo, desc, itens.slice(0, cap), itens.length)
            : '';

        let html = '';
        if (this.vitrineLoja === '__cupom__') {
            const cupons = base.filter(o => o.dados_extra && o.dados_extra.cupom);
            html = sec('cupom', 'Cupons em destaque', 'Os melhores cupons selecionados para você.', cupons, 12);
        } else if (this.vitrineLoja) {
            const itens = base.filter(o => o.loja === this.vitrineLoja);
            const meta = this._metaLoja(this.vitrineLoja);
            html = sec(meta.key, meta.titulo, meta.desc, itens, 12);
        } else {
            const ml = base.filter(o => o.loja === 'Mercado Livre');
            const shopee = base.filter(o => o.loja === 'Shopee');
            const amazon = base.filter(o => o.loja === 'Amazon');
            const outros = base.filter(o => !['Mercado Livre', 'Shopee', 'Amazon'].includes(o.loja));
            html += sec('ml', 'As Melhores Ofertas do Mercado Livre', 'Produtos de qualidade e segurança, selecionados para você.', ml, 4);
            html += sec('shopee', 'As Melhores Ofertas da Shopee', 'Achadinhos e cupons imperdíveis da Shopee.', shopee, 4);
            html += sec('amazon', 'As Melhores Ofertas da Amazon Brasil', 'Frete grátis Prime e a garantia da Amazon.', amazon, 4);
            html += sec('generic', 'Mais Ofertas', 'Seleção de ofertas de outras lojas.', outros, 4);
        }

        box.innerHTML = html || `<div class="public-empty">Nenhuma oferta encontrada. Tente outra busca ou categoria.</div>`;
    },

    _metaLoja(loja) {
        const m = {
            'Mercado Livre': { key: 'ml', titulo: 'As Melhores Ofertas do Mercado Livre', desc: 'Produtos de qualidade e segurança, selecionados para você.' },
            'Shopee': { key: 'shopee', titulo: 'As Melhores Ofertas da Shopee', desc: 'Achadinhos e cupons imperdíveis da Shopee.' },
            'Amazon': { key: 'amazon', titulo: 'As Melhores Ofertas da Amazon Brasil', desc: 'Frete grátis Prime e a garantia da Amazon.' },
        };
        return m[loja] || { key: 'generic', titulo: loja, desc: 'Ofertas selecionadas.' };
    },

    _publicSecaoMarketplace(key, titulo, desc, itens) {
        const verFiltro = ['ml', 'shopee', 'amazon', 'cupom'].includes(key);
        const lojaParaFiltro = { ml: 'Mercado Livre', shopee: 'Shopee', amazon: 'Amazon', cupom: '__cupom__' }[key] || null;
        const verTodas = verFiltro
            ? `<a class="ver-todas" onclick="App.vitrineNav('${lojaParaFiltro}')">Ver todas ›</a>`
            : '';
        return `
            <section class="marketplace-section${itens.length > 4 ? ' is-expanded' : ''}">
                <div class="marketplace-section-header">
                    <h2>${titulo}</h2>
                    ${verTodas}
                </div>
                <div class="marketplace-row">
                    <div class="marketplace-highlight-card mh-${key}">
                        <h3>${titulo.replace('As Melhores Ofertas ', '')}</h3>
                        <p>${desc}</p>
                        ${verFiltro
                            ? `<a class="mh-btn" onclick="App.vitrineNav('${lojaParaFiltro}')">VER TODAS OFERTAS</a>`
                            : `<a class="mh-btn" onclick="App.vitrineNav(null)">VER OFERTAS</a>`}
                    </div>
                    <div class="marketplace-products-grid">
                        ${itens.map(o => this._publicProductCard(o)).join('')}
                    </div>
                </div>
            </section>
        `;
    },

    _publicProductCard(o) {
        // Nunca ofereça o link original como fallback: ele não garante comissão.
        const hrefSeguro = this.temLinkAfiliadoValido(o) ? this.safeUrl(o.link_afiliado) : '';
        const cta = hrefSeguro
            ? `<a class="public-product-cta" href="${this.escapeAttr(hrefSeguro)}" target="_blank" rel="noopener">Ver oferta</a>`
            : `<a class="public-product-cta" href="#" onclick="return false" aria-disabled="true">Link em preparação</a>`;

        // Imagem: só usa a URL do scraper se for segura; senão placeholder (sem src="#").
        const imgSeguro = this.safeUrl(o.imagem_url);
        const imagem = imgSeguro
            ? `<img src="${this.escapeAttr(imgSeguro)}" alt="${this.escapeAttr(o.titulo)}" loading="lazy"
                     onerror="this.onerror=null; this.style.display='none'; this.nextElementSibling.style.display='flex';">
               <div class="public-product-noimg" style="display:none">Sem imagem</div>`
            : `<div class="public-product-noimg">Sem imagem</div>`;

        const badge = o.desconto_pct > 0 ? `-${Math.round(o.desconto_pct)}%` : 'Oferta';
        const old = (o.preco_original && o.preco_original > o.preco)
            ? `<div class="public-product-old-price">${this.fmtPreco(o.preco_original)}</div>` : '';
        const cupom = (o.dados_extra && o.dados_extra.cupom)
            ? `<div class="public-product-coupon">🎟️ ${this._esc(o.dados_extra.cupom)}</div>` : '';
        return `
            <article class="public-product-card">
                <div class="public-product-image-wrap">
                    ${imagem}
                    <span class="public-product-badge">${badge}</span>
                </div>
                <div class="public-product-body">
                    <h3>${this._esc(o.titulo)}</h3>
                    <div class="public-product-price">${this.fmtPreco(o.preco)}</div>
                    ${old}
                    ${cupom}
                </div>
                ${cta}
            </article>
        `;
    },

    vitrineNav(loja) {
        this.vitrineLoja = loja || null;
        this.vitrineTermo = '';
        const input = document.getElementById('vitrineSearch');
        if (input) input.value = '';
        this.renderVitrine();
    },

    vitrineCategoria(nome) {
        this.vitrineTermo = nome;
        this.vitrineLoja = null;
        const input = document.getElementById('vitrineSearch');
        if (input) input.value = nome;
        this.renderVitrine();
    },

    vitrineBuscar(e) {
        if (e) e.preventDefault();
        const input = document.getElementById('vitrineSearch');
        this.vitrineTermo = input ? input.value.trim() : '';
        this.vitrineLoja = null;
        this._renderPublicNav();
        this._renderPublicSecoes();
        return false;
    },

    // =============================================
    // SEARCH
    // =============================================

    async buscar() {
        const palavra = document.getElementById('searchInput').value.trim();
        if (!palavra) { this.toast('Digite uma palavra-chave', 'error'); return; }

        const btn = document.getElementById('btnBuscar');
        btn.innerHTML = '<span class="spinner"></span> ...';
        btn.disabled = true;

        const fontes = [];
        if (document.getElementById('toggleMl').classList.contains('active-ml')) fontes.push('mercadolivre');
        if (document.getElementById('toggleShopee').classList.contains('active-shopee')) fontes.push('shopee');
        if (!fontes.length) fontes.push('mercadolivre');

        try {
            const resp = await fetch(`${API}/api/buscar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ palavra_chave: palavra, fontes }),
            });
            const data = await resp.json();
            this.toast(data.mensagem || `${data.encontradas} ofertas!`, data.encontradas > 0 ? 'success' : 'info');

            if (data.encontradas > 0) {
                document.getElementById('searchResults').innerHTML = `
                    <p style="color:var(--success);font-weight:600;">
                        ✅ ${data.encontradas} novas ofertas! Veja na aba "Ofertas".
                    </p>
                `;
                await this.carregarOfertas();
                await this.carregarStats();
            } else {
                document.getElementById('searchResults').innerHTML = `
                    <p style="color:var(--text-tertiary);">Nenhuma nova oferta com os filtros atuais.</p>
                `;
            }
        } catch (e) {
            this.toast(`Erro: ${e.message}`, 'error');
        } finally {
            btn.innerHTML = 'Buscar';
            btn.disabled = false;
        }
    },

    async buscarAuto() {
        const btn = document.getElementById('btnBuscarAuto');
        if (btn) { btn.innerHTML = '<span class="spinner"></span>'; btn.disabled = true; }

        try {
            const fontes = ['mercadolivre'];
            if (document.getElementById('toggleShopee')?.classList.contains('active-shopee')) fontes.push('shopee');

            const resp = await fetch(`${API}/api/buscar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fontes }),
            });
            const data = await resp.json();
            this.toast(data.mensagem, data.encontradas > 0 ? 'success' : 'info');
            await this.carregarOfertas();
            await this.carregarStats();
        } catch (e) {
            this.toast(`Erro: ${e.message}`, 'error');
        } finally {
            if (btn) { btn.innerHTML = '⚡ Auto'; btn.disabled = false; }
        }
    },

    // =============================================
    // POST
    // =============================================

    // Prévia OBRIGATÓRIA: postar/lote abrem um modal de conferência com checkbox.
    postarOferta(id, canal = 'telegram') {
        this.abrirPreviaPost({ tipo: 'individual', id, canal });
    },

    abrirPreviaPost(pend) {
        this._postPendente = pend;
        const body = document.getElementById('previaBody');
        const chk = document.getElementById('previaConfirmado');
        if (chk) chk.checked = false;
        if (pend.tipo === 'individual') {
            const o = this.ofertas.find(x => x.id === pend.id);
            body.innerHTML = o ? this._previaCard(o, pend.canal) : '<p>Oferta não encontrada.</p>';
        } else {
            const lista = pend.ids.map(id => this.ofertas.find(x => x.id === id)).filter(Boolean);
            body.innerHTML = this._previaLote(lista);
        }
        document.getElementById('modalPreviaPost').style.display = '';
    },

    fecharPreviaPost() { document.getElementById('modalPreviaPost').style.display = 'none'; },

    confirmarPostagem() {
        const chk = document.getElementById('previaConfirmado');
        if (!chk || !chk.checked) {
            this.toast('Marque "Conferi estes dados na página do produto" para continuar.', 'error');
            return;
        }
        const pend = this._postPendente;
        this.fecharPreviaPost();
        if (!pend) return;
        if (pend.tipo === 'individual') this._executarPostarOferta(pend.id, pend.canal);
        else this._executarPostarLote(pend.ids);
    },

    _linkAfiliadoValido(o) {
        const link = (o.link_afiliado || '').trim();
        if (!link) return false;
        try {
            const u = new URL(link);
            if ((o.loja || '').toLowerCase() === 'mercado livre') {
                return u.protocol === 'https:' && u.hostname.toLowerCase() === 'meli.la' && !!u.pathname.replace(/\//g, '');
            }
            return (u.protocol === 'http:' || u.protocol === 'https:') && !!u.hostname;
        } catch { return false; }
    },

    _previaCard(o, canal) {
        const canalNome = { telegram: 'Telegram', instagram: 'Instagram' }[canal] || canal;
        const img = o.imagem_url
            ? `<img src="${this.escapeAttr(o.imagem_url)}" alt="" style="max-width:120px;max-height:120px;object-fit:contain;border-radius:8px;background:#fff;">`
            : '<div style="width:120px;height:120px;display:flex;align-items:center;justify-content:center;background:var(--bg-card);border-radius:8px;color:var(--text-tertiary);font-size:12px;">Sem imagem</div>';
        const orig = (o.preco_original && o.preco_original > o.preco)
            ? `<span style="text-decoration:line-through;color:var(--text-tertiary);margin-left:8px;">${this.fmtPreco(o.preco_original)}</span>` : '';
        const desc = o.desconto_pct > 0 ? `<span style="color:var(--danger);font-weight:700;margin-left:8px;">-${Math.round(o.desconto_pct)}%</span>` : '';
        const dx = o.dados_extra || {};
        const cupom = dx.cupom ? this._esc(dx.cupom) : '—';
        const parcel = (dx.parcelamento || dx.forma_pagamento) ? this._esc(dx.parcelamento || dx.forma_pagamento) : '—';
        const ok = this._linkAfiliadoValido(o);
        const linkLinha = ok
            ? `<div style="color:var(--success);font-size:12px;">✔ Link afiliado OK</div>`
            : `<div style="color:var(--danger);font-size:12px;">✖ Link de afiliado inválido${(o.loja || '').toLowerCase() === 'mercado livre' ? ' — Mercado Livre exige https://meli.la/…' : ''}. O servidor vai bloquear a postagem.</div>`;
        const linha = (rot, val) => `<div style="display:flex;gap:8px;font-size:13px;margin-bottom:4px;"><span style="color:var(--text-tertiary);min-width:96px;">${rot}</span><span>${val}</span></div>`;
        return `
            <div style="display:flex;gap:14px;align-items:flex-start;">
                ${img}
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:700;margin-bottom:8px;">${this._esc(o.titulo)}</div>
                    ${linha('Preço', `<b>${this.fmtPreco(o.preco)}</b>${orig}${desc}`)}
                    ${linha('Parcelamento', parcel)}
                    ${linha('Cupom', cupom)}
                    ${linha('Loja', this._esc(o.loja || '—'))}
                    ${linha('Canal', canalNome)}
                    ${linkLinha}
                </div>
            </div>
            <p style="font-size:11px;color:var(--text-tertiary);margin-top:10px;">
                O servidor revalida o preço (confirmação manual válida por 6h) e bloqueia se subiu/sumiu/expirou.
            </p>`;
    },

    _previaLote(lista) {
        if (!lista.length) return '<p>Nenhuma oferta válida selecionada.</p>';
        const invalidos = lista.filter(o => !this._linkAfiliadoValido(o)).length;
        const itens = lista.slice(0, 12).map(o =>
            `<li style="font-size:12.5px;margin-bottom:3px;">${this._esc(o.titulo)} — <b>${this.fmtPreco(o.preco)}</b>${this._linkAfiliadoValido(o) ? '' : ' <span style="color:var(--danger);">(link inválido)</span>'}</li>`
        ).join('');
        return `
            <p style="font-weight:700;margin-bottom:8px;">${lista.length} oferta(s) selecionada(s)</p>
            <ul style="margin:0 0 8px 18px;">${itens}</ul>
            ${lista.length > 12 ? `<p style="font-size:12px;color:var(--text-tertiary);">…e mais ${lista.length - 12}.</p>` : ''}
            ${invalidos ? `<p style="color:var(--danger);font-size:12px;">${invalidos} com link inválido — serão bloqueadas pelo servidor.</p>` : ''}
            <p style="font-size:11px;color:var(--text-tertiary);margin-top:8px;">
                Cada uma é revalidada no servidor (preço/cupom/link) antes do envio.
            </p>`;
    },

    async testarOferta(id) {
        try {
            const resp = await fetch(`${API}/api/ofertas/${id}/testar`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
            });
            const data = await resp.json();
            if (!resp.ok) { this.toast(data.detail || 'Falha no envio de teste', 'error'); return; }
            const r = data.resultado || {};
            this.toast(r.sucesso ? 'Teste enviado ao canal de teste! 🧪' : `Teste: ${r.resposta}`, r.sucesso ? 'success' : 'info');
        } catch (e) {
            this.toast(`Erro: ${e.message}`, 'error');
        }
    },

    async _executarPostarOferta(id, canal = 'telegram') {
        const labels = { telegram: '📢 TG', instagram: '📸 IG' };
        const btn = document.getElementById(`post-${canal}-${id}`);
        if (btn) { btn.innerHTML = '<span class="spinner"></span>'; btn.disabled = true; }

        try {
            const resp = await fetch(`${API}/api/ofertas/${id}/postar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ canais: [canal] }),
            });
            const data = await resp.json();
            if (!resp.ok) {
                // 409 = preço subiu/produto sumiu (revalidação) ou outro bloqueio
                this.toast(data.detail || 'Não foi possível postar', 'error');
                await this.carregarOfertas();
                return;
            }
            for (const r of (data.resultados || [])) {
                this.toast(r.sucesso ? `Postado no ${r.canal}!` : `Erro: ${r.resposta}`, r.sucesso ? 'success' : 'error');
            }
            await this.carregarOfertas();
            await this.carregarStats();
        } catch (e) {
            this.toast(`Erro: ${e.message}`, 'error');
        } finally {
            if (btn) { btn.innerHTML = labels[canal] || '📢 Postar'; btn.disabled = false; }
        }
    },

    // =============================================
    // POSTAGEM EM LOTE
    // =============================================

    toggleSelecionarTudo() {
        const boxes = [...document.querySelectorAll('.offer-checkbox')];
        if (!boxes.length) return;
        const marcados = boxes.filter(c => c.checked).length;
        const marcarTodos = marcados <= boxes.length / 2;   // maioria desmarcada -> marca tudo
        boxes.forEach(c => { c.checked = marcarTodos; });
        this.atualizarBotaoLote();
    },

    atualizarBotaoLote() {
        // Realça o card selecionado (não só o checkbox).
        document.querySelectorAll('.offer-checkbox').forEach(c => {
            c.closest('.offer-card')?.classList.toggle('selected', c.checked);
        });
        const n = document.querySelectorAll('.offer-checkbox:checked').length;
        const btn = document.getElementById('btnPostarLote');
        if (!btn) return;
        if (n > 0) {
            btn.style.display = 'inline-block';
            btn.textContent = `📢 Postar Selecionadas (${n})`;
        } else {
            btn.style.display = 'none';
            btn.textContent = '📢 Postar Selecionadas (0)';
        }
    },

    postarLote() {
        const ids = [...document.querySelectorAll('.offer-checkbox:checked')].map(c => parseInt(c.value, 10));
        if (!ids.length) { this.toast('Selecione ao menos uma oferta', 'error'); return; }
        this.abrirPreviaPost({ tipo: 'lote', ids });   // prévia obrigatória antes do lote
    },

    async _executarPostarLote(ids) {
        if (!ids || !ids.length) return;

        // Operador escolhe o canal: OK = Telegram, Cancelar = Instagram.
        const canal = confirm(`Postar ${ids.length} oferta(s) no TELEGRAM?\n\n(Cancelar = postar no Instagram)`)
            ? 'telegram' : 'instagram';

        const btn = document.getElementById('btnPostarLote');
        if (btn) { btn.innerHTML = '<span class="spinner"></span> Postando...'; btn.disabled = true; }

        try {
            const resp = await fetch(`${API}/api/ofertas/postar-lote`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids, canais: [canal] }),
            });
            const data = await resp.json();
            const res = data.resultados || [];
            const ok = res.filter(r => r.sucesso).length;
            this.toast(`Lote: ${ok}/${res.length} postada(s) no ${canal}`, ok > 0 ? 'success' : 'info');
            await this.carregarOfertas();
            await this.carregarStats();
        } catch (e) {
            this.toast(`Erro: ${e.message}`, 'error');
        } finally {
            if (btn) { btn.disabled = false; }
            this.atualizarBotaoLote();   // grid recarregou: checkboxes resetados -> oculta botão
        }
    },

    // =============================================
    // DELETE
    // =============================================

    async deletarOferta(id) {
        if (!confirm('Remover esta oferta?')) return;
        try {
            await fetch(`${API}/api/ofertas/${id}`, { method: 'DELETE' });
            this.toast('Oferta removida', 'info');
            await this.carregarOfertas();
            await this.carregarStats();
        } catch (e) { this.toast(`Erro: ${e.message}`, 'error'); }
    },

    // =============================================
    // MODALS
    // =============================================

    abrirModalNovaOferta() { document.getElementById('modalNovaOferta').style.display = ''; },
    fecharModal() { document.getElementById('modalNovaOferta').style.display = 'none'; },

    async salvarNovaOferta() {
        const titulo = document.getElementById('novoTitulo').value.trim();
        const preco = parseFloat(document.getElementById('novoPreco').value);
        const orig = parseFloat(document.getElementById('novoPrecoOriginal').value) || null;
        const loja = document.getElementById('novoLoja').value;
        const link = document.getElementById('novoLink').value.trim();
        const img = document.getElementById('novoImagem').value.trim();

        if (!titulo || !preco || !link) { this.toast('Preencha título, preço e link!', 'error'); return; }

        const desc = orig && orig > preco ? Math.round(((orig - preco) / orig) * 100) : 0;

        try {
            const resp = await fetch(`${API}/api/ofertas`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ titulo, preco, preco_original: orig, desconto_pct: desc, loja, link_afiliado: link, imagem_url: img || null, fonte: 'manual' }),
            });
            const data = await resp.json();
            this.toast(`Oferta #${data.id} criada!`, 'success');
            this.fecharModal();
            ['novoTitulo','novoPreco','novoPrecoOriginal','novoLink','novoImagem'].forEach(id => document.getElementById(id).value = '');
            await this.carregarOfertas();
            await this.carregarStats();
        } catch (e) { this.toast(`Erro: ${e.message}`, 'error'); }
    },

    abrirModalLink(id) {
        document.getElementById('linkOfertaId').value = id;
        const oferta = this.ofertas.find(o => String(o.id) === String(id));
        document.getElementById('inputLinkAfiliado').value = oferta?.link_afiliado || '';
        const extras = oferta?.dados_extra || {};
        document.getElementById('inputPrecoConfirmado').value = extras.preco_confirmado_manual || oferta?.preco || '';
        document.getElementById('inputParcelamentoConfirmado').value = extras.parcelamento_manual || extras.parcelamento_destaque || extras.forma_pagamento || '';
        document.getElementById('modalLink').style.display = '';
    },

    fecharModalLink() { document.getElementById('modalLink').style.display = 'none'; },

    async salvarLinkAfiliado() {
        const id = document.getElementById('linkOfertaId').value;
        const link = document.getElementById('inputLinkAfiliado').value.trim();
        const precoConfirmado = parseFloat(document.getElementById('inputPrecoConfirmado').value);
        const parcelamentoConfirmado = document.getElementById('inputParcelamentoConfirmado').value.trim();
        if (!link) { this.toast('Cole o link!', 'error'); return; }
        if (!precoConfirmado || precoConfirmado <= 0) { this.toast('Confirme o preço visto na página!', 'error'); return; }

        try {
            const resp = await fetch(`${API}/api/ofertas/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    link_afiliado: link,
                    preco_confirmado: precoConfirmado,
                    parcelamento_confirmado: parcelamentoConfirmado,
                }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Link inválido');
            this.toast('Link, preço e parcelamento confirmados!', 'success');
            this.fecharModalLink();
            await this.carregarOfertas();
        } catch (e) { this.toast(`Erro: ${e.message}`, 'error'); }
    },

    // =============================================
    // HISTORY
    // =============================================

    async carregarHistorico() {
        try {
            const resp = await fetch(`${API}/api/historico`);
            const data = await resp.json();

            const renderList = (container, items, max) => {
                const slice = items.slice(0, max || items.length);
                if (!slice.length) {
                    container.innerHTML = `<div class="empty"><div class="empty-icon">📋</div><div class="empty-text">Nenhuma postagem</div></div>`;
                    return;
                }
                container.innerHTML = slice.map(p => {
                    const icon = p.sucesso ? '✅' : '❌';
                    const cls = p.sucesso ? 'ok' : 'err';
                    const ch = { telegram: '📱', whatsapp: '💬', instagram: '📸' }[p.canal] || '📢';
                    return `
                        <li class="history-item">
                            <div class="history-dot ${cls}">${icon}</div>
                            <div class="history-info">
                                <div class="history-info-title">${this._esc(p.titulo || 'Oferta')}</div>
                                <div class="history-info-sub">${this.fmtData(p.postado_em)} · ${this.fmtPreco(p.preco)}</div>
                            </div>
                            <div class="history-channel">${ch} ${p.canal}</div>
                        </li>
                    `;
                }).join('');
            };

            const fullList = document.getElementById('historyList');
            const dashList = document.getElementById('dashboardHistory');
            if (fullList) renderList(fullList, data);
            if (dashList) renderList(dashList, data, 5);
        } catch (e) { console.error('Erro histórico:', e); }
    },

    // =============================================
    // ANALYTICS
    // =============================================

    async carregarAnalytics() {
        try {
            const resp = await fetch(`${API}/analytics/summary`);
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            const data = await resp.json();
            this.renderAnalytics(data || {});
        } catch (e) {
            console.error('Erro analytics:', e);
            this.renderAnalytics(null);
        }
    },

    renderAnalytics(data) {
        const canalEmoji = { telegram: '📱', whatsapp: '💬', instagram: '📸', site: '🌐' };

        // --- vazio / erro: zera KPIs e mostra estados vazios, sem quebrar ---
        if (!data) {
            document.getElementById('kpiCliquesTotais').textContent = '0';
            document.getElementById('kpiFaturamento').textContent = this.fmtPreco(0);
            document.getElementById('kpiOfertasClique').textContent = '0';
            const vazio = (cols, txt) => `<tr><td colspan="${cols}"><div class="empty"><div class="empty-icon">📈</div><div class="empty-text">${txt}</div></div></td></tr>`;
            document.getElementById('analyticsCanalBody').innerHTML = vazio(4, 'Sem dados de clique');
            document.getElementById('analyticsTopBody').innerHTML = vazio(4, 'Sem dados de clique');
            const note = document.getElementById('analyticsCtrNote');
            if (note) note.textContent = 'Não foi possível carregar o resumo de analytics.';
            return;
        }

        const totais = data.totais || {};
        const cliquesPorCanal = data.cliques_por_canal || {};
        const fatPorCanal = data.faturamento_estimado_por_canal || {};
        const epcPorCanal = data.epc_por_canal || {};

        // --- KPIs superiores ---
        const totalFat = Object.values(fatPorCanal)
            .reduce((s, c) => s + ((c && c.comissao_estimada) || 0), 0);
        document.getElementById('kpiCliquesTotais').textContent = totais.cliques ?? 0;
        document.getElementById('kpiFaturamento').textContent = this.fmtPreco(totalFat);
        document.getElementById('kpiOfertasClique').textContent = totais.ofertas_com_clique ?? 0;

        // --- nota de CTR (honesta: indisponível sem impressões) + atualização ---
        const note = document.getElementById('analyticsCtrNote');
        if (note) {
            const ctr = data.ctr || {};
            const atualizado = data.gerado_em ? ` · Atualizado: ${this.fmtData(data.gerado_em)}` : '';
            if (ctr.disponivel) {
                note.textContent = `CTR: ${ctr.valor}${atualizado}`;
            } else {
                note.innerHTML = `📊 <strong>CTR indisponível</strong> — ${this._esc(ctr.motivo || 'sem impressões instrumentadas.')}${atualizado}`;
            }
        }

        // --- tabela por canal (ordenada por cliques) ---
        const canalBody = document.getElementById('analyticsCanalBody');
        const canais = Object.keys(cliquesPorCanal).sort((a, b) => cliquesPorCanal[b] - cliquesPorCanal[a]);
        if (!canais.length) {
            canalBody.innerHTML = `<tr><td colspan="4"><div class="empty"><div class="empty-icon">📡</div><div class="empty-text">Nenhum clique por canal ainda</div><div class="empty-hint">Os cliques aparecem quando alguém abre um link /r/</div></div></td></tr>`;
        } else {
            canalBody.innerHTML = canais.map(canal => {
                const cliques = cliquesPorCanal[canal] || 0;
                const f = fatPorCanal[canal] || {};
                const cob = (f.cobertura_comissao_pct ?? null);
                const cobTxt = (cob === null || cob === undefined) ? '—' : `${cob}%`;
                const epc = epcPorCanal[canal];
                const epcTxt = (epc === null || epc === undefined) ? '—' : this.fmtPreco(epc);
                const ic = canalEmoji[canal] || '📢';
                return `<tr>
                    <td>${ic} ${this._esc(canal)}</td>
                    <td>${cliques}</td>
                    <td>${cobTxt}</td>
                    <td>${epcTxt}</td>
                </tr>`;
            }).join('');
        }

        // --- top ofertas por cliques ---
        const topBody = document.getElementById('analyticsTopBody');
        const top = Array.isArray(data.top_ofertas) ? data.top_ofertas : [];
        if (!top.length) {
            topBody.innerHTML = `<tr><td colspan="4"><div class="empty"><div class="empty-icon">🎯</div><div class="empty-text">Nenhuma oferta com clique</div></div></td></tr>`;
        } else {
            topBody.innerHTML = top.map((o, i) => {
                const titulo = o.removida
                    ? `<span style="opacity:.6;font-style:italic;">(oferta removida) #${o.oferta_id}</span>`
                    : this._esc(o.titulo || `Oferta #${o.oferta_id}`);
                return `<tr>
                    <td>${i + 1}</td>
                    <td>${titulo}</td>
                    <td>${this._esc(o.loja || '—')}</td>
                    <td>${o.cliques ?? 0}</td>
                </tr>`;
            }).join('');
        }
    },

    // =============================================
    // CONFIG
    // =============================================

    async carregarConfig() {
        try {
            const resp = await fetch(`${API}/api/configuracoes`);
            const cfg = await resp.json();
            document.getElementById('cfgPalavras').value = (cfg.palavras_chave || []).join(', ');
            document.getElementById('cfgIntervalo').value = cfg.intervalo_minutos || 60;
            document.getElementById('cfgDesconto').value = cfg.desconto_minimo || 15;
            document.getElementById('cfgPrecoMax').value = cfg.preco_maximo || 500;
            document.getElementById('cfgChatId').value = cfg.telegram_chat_id || '';
        } catch (e) { console.error('Erro config:', e); }
    },

    // =============================================
    // PRODUTOS RECORRENTES
    // =============================================

    async carregarRecorrentes() {
        const box = document.getElementById('recorrentesList');
        try {
            const resp = await fetch(`${API}/api/produtos-recorrentes`);
            const lista = await resp.json();
            if (!lista.length) {
                box.innerHTML = `
                    <div class="empty">
                        <div class="empty-icon">⭐</div>
                        <div class="empty-text">Nenhum produto monitorado</div>
                        <div class="empty-hint">Clique em "Monitorar Produto"</div>
                    </div>`;
                return;
            }
            box.innerHTML = `
                <table class="data-table">
                    <thead><tr>
                        <th>Produto</th><th>Loja</th><th>Alvo</th><th>Atual</th><th>Menor</th><th>Ativo</th><th></th>
                    </tr></thead>
                    <tbody>${lista.map(p => this._rowRecorrente(p)).join('')}</tbody>
                </table>`;
        } catch (e) {
            box.innerHTML = `<div class="empty"><div class="empty-text">Erro ao carregar</div></div>`;
            console.error('Erro recorrentes:', e);
        }
    },

    _rowRecorrente(p) {
        const dep = p.departamento_emoji ? `${p.departamento_emoji} ` : '';
        return `
            <tr>
                <td>${dep}${this._esc(p.titulo)}</td>
                <td>${this._esc(p.loja || '—')}</td>
                <td>${p.preco_alvo ? this.fmtPreco(p.preco_alvo) : '—'}</td>
                <td>${p.preco_atual ? this.fmtPreco(p.preco_atual) : '—'}</td>
                <td>${p.preco_minimo ? this.fmtPreco(p.preco_minimo) : '—'}</td>
                <td>
                    <button class="chip ${p.ativo ? 'active' : ''}" onclick="App.toggleRecorrente(${p.id}, ${p.ativo ? 0 : 1})">
                        ${p.ativo ? 'Sim' : 'Não'}
                    </button>
                </td>
                <td style="white-space:nowrap;">
                    <button class="btn btn-ghost btn-sm" onclick="App.verHistorico(${JSON.stringify(p.titulo)})">📊</button>
                    <button class="btn btn-danger btn-sm btn-icon" onclick="App.deletarRecorrente(${p.id})" title="Remover">🗑️</button>
                </td>
            </tr>`;
    },

    abrirModalRecorrente() { document.getElementById('modalRecorrente').style.display = ''; },
    fecharModalRecorrente() { document.getElementById('modalRecorrente').style.display = 'none'; },

    async salvarRecorrente() {
        const titulo = document.getElementById('recTitulo').value.trim();
        if (!titulo) { this.toast('Informe o título', 'error'); return; }
        const dados = {
            titulo,
            loja: document.getElementById('recLoja').value,
            preco_alvo: parseFloat(document.getElementById('recPrecoAlvo').value) || null,
            link_original: document.getElementById('recLink').value.trim() || null,
        };
        try {
            await fetch(`${API}/api/produtos-recorrentes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dados),
            });
            this.toast('Produto monitorado!', 'success');
            this.fecharModalRecorrente();
            ['recTitulo', 'recPrecoAlvo', 'recLink'].forEach(id => document.getElementById(id).value = '');
            await this.carregarRecorrentes();
        } catch (e) { this.toast(`Erro: ${e.message}`, 'error'); }
    },

    async toggleRecorrente(id, ativo) {
        try {
            await fetch(`${API}/api/produtos-recorrentes/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ativo }),
            });
            await this.carregarRecorrentes();
        } catch (e) { this.toast(`Erro: ${e.message}`, 'error'); }
    },

    async deletarRecorrente(id) {
        if (!confirm('Parar de monitorar este produto?')) return;
        try {
            await fetch(`${API}/api/produtos-recorrentes/${id}`, { method: 'DELETE' });
            this.toast('Removido', 'info');
            await this.carregarRecorrentes();
        } catch (e) { this.toast(`Erro: ${e.message}`, 'error'); }
    },

    // =============================================
    // HISTÓRICO DE PREÇOS
    // =============================================

    async verHistorico(titulo) {
        const body = document.getElementById('histPrecoBody');
        body.innerHTML = `<div class="empty"><div class="empty-icon">📊</div><div class="empty-text">Carregando...</div></div>`;
        document.getElementById('modalHistPreco').style.display = '';
        try {
            const resp = await fetch(`${API}/api/historico-precos?titulo=${encodeURIComponent(titulo)}&limite=60`);
            const dados = await resp.json();
            if (!dados.length) {
                body.innerHTML = `<div class="empty"><div class="empty-icon">📊</div><div class="empty-text">Sem histórico ainda</div><div class="empty-hint">O preço é registrado a cada busca</div></div>`;
                return;
            }
            // Ordena cronológico (API vem desc)
            const serie = [...dados].reverse();
            const precos = serie.map(d => d.preco);
            const min = Math.min(...precos), max = Math.max(...precos);
            const range = max - min || 1;
            const barras = serie.map(d => {
                const h = 10 + ((d.preco - min) / range) * 90; // 10%..100%
                const ehMin = d.preco === min;
                return `<div class="hp-bar" style="height:${h}%; background:${ehMin ? 'var(--success, #22c55e)' : 'var(--brand-primary)'};"
                            title="${this.fmtData(d.registrado_em)} · ${this.fmtPreco(d.preco)}"></div>`;
            }).join('');
            body.innerHTML = `
                <div style="font-size:13px;color:var(--text-secondary);margin-bottom:6px;">
                    ${this._esc(titulo)}
                </div>
                <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:8px;">
                    <span>📉 Menor: <strong style="color:var(--success,#22c55e)">${this.fmtPreco(min)}</strong></span>
                    <span>📈 Maior: <strong>${this.fmtPreco(max)}</strong></span>
                    <span>${serie.length} registros</span>
                </div>
                <div class="hp-chart">${barras}</div>`;
        } catch (e) {
            body.innerHTML = `<div class="empty"><div class="empty-text">Erro: ${e.message}</div></div>`;
        }
    },

    fecharModalHistPreco() { document.getElementById('modalHistPreco').style.display = 'none'; },

    // =============================================
    // TOAST
    // =============================================

    toast(msg, type = 'info') {
        const area = document.getElementById('toastArea');
        const icons = { success: '✅', error: '❌', info: 'ℹ️' };
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
        area.appendChild(el);
        setTimeout(() => {
            el.style.animation = 'toastSlideOut 0.3s ease forwards';
            setTimeout(() => el.remove(), 300);
        }, 4000);
    },

    // =============================================
    // UTILS
    // =============================================

    fmtPreco(v) {
        if (!v && v !== 0) return 'R$ —';
        return `R$ ${Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },

    fmtData(s) {
        if (!s) return '';
        try { return new Date(s).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }); }
        catch { return s; }
    },

    _esc(s) {
        if (!s) return '';
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    },

    // Escapa valor p/ uso seguro DENTRO de um atributo HTML (inclui aspas e backtick).
    escapeAttr(v) {
        return String(v == null ? '' : v)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;')
            .replace(/`/g, '&#096;');
    },

    // Valida URL p/ href/src. Devolve a URL ORIGINAL (trim) se for segura, senão ''.
    // Não reescreve/reordena/recodifica nada — query string (utm_*, sub_id) intacta.
    safeUrl(u) {
        if (u == null) return '';
        const s = String(u).trim();
        if (!s) return '';
        // Para a checagem, remove espaços/controle (pega "java\nscript:", "data :", etc).
        const probe = s.replace(/[\u0000-\u0020]+/g, '').toLowerCase();
        if (/^(javascript|data|vbscript|file|blob):/.test(probe)) return '';
        const m = probe.match(/^([a-z][a-z0-9+.\-]*):/);   // tem esquema explícito?
        if (m && m[1] !== 'http' && m[1] !== 'https') return '';
        return s;   // http/https ou relativa (/, ./, ../, path, ?query, #anchor)
    },

    temLinkAfiliadoValido(o) {
        const link = this.safeUrl(o?.link_afiliado);
        if (!link) return false;
        if ((o?.loja || '').toLowerCase() !== 'mercado livre') return true;
        try {
            return new URL(link).protocol === 'https:' && new URL(link).hostname.toLowerCase() === 'meli.la';
        } catch (_) {
            return false;
        }
    },

    // =============================================
    // MERCADO LIVRE OAUTH2
    // =============================================

    async conectarMercadoLivre() {
        try {
            const resp = await fetch(`${API}/api/ml/auth_url`);
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Falha ao obter URL de autenticação');
            }
            const data = await resp.json();
            if (data.url) {
                window.location.href = data.url;
            }
        } catch (e) {
            this.toast(`Erro: ${e.message}`, 'error');
        }
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
