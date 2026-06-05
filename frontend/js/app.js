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

        await Promise.all([
            this.carregarStats(),
            this.carregarDepartamentos(),
            this.carregarOfertas(),
            this.carregarConfig(),
            this.carregarHistorico(),
        ]);
        setInterval(() => this.carregarStats(), 30000);
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
            config: 'Configurações',
        };
        document.getElementById('pageTitle').textContent = titles[tabName] || tabName;

        // Show/hide tabs
        ['Dashboard', 'Ofertas', 'Buscar', 'Historico', 'Recorrentes', 'Config'].forEach(t => {
            const section = document.getElementById('tab' + t);
            if (section) section.style.display = 'none';
        });

        const target = document.getElementById('tab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
        if (target) target.style.display = '';

        this.currentTab = tabName;

        if (tabName === 'historico') this.carregarHistorico();
        if (tabName === 'recorrentes') this.carregarRecorrentes();

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

        if (lista.length === 0) {
            grid.innerHTML = `
                <div class="empty" style="grid-column:1/-1;">
                    <div class="empty-icon">📦</div>
                    <div class="empty-text">Nenhuma oferta encontrada</div>
                    <div class="empty-hint">Use "Buscar Ofertas" para encontrar promoções</div>
                </div>
            `;
            return;
        }

        grid.innerHTML = lista.map(o => this._cardOferta(o)).join('');
    },

    _cardOferta(o) {
        const desc = o.desconto_pct > 0 ? `<span class="badge badge-discount">-${Math.round(o.desconto_pct)}%</span>` : '';
        const frete = o.frete_gratis ? `<span class="badge badge-frete">FRETE GRÁTIS</span>` : '';
        const storeClass = o.loja === 'Mercado Livre' ? 'ml' : 'shopee';
        const storeIcon = o.loja === 'Mercado Livre' ? '🟡' : '🟠';

        const img = o.imagem_url || `data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><rect fill='%231a1a30' width='200' height='200'/><text x='100' y='110' text-anchor='middle' fill='%235c5c7a' font-size='40'>📦</text></svg>`;

        const precoFmt = this.fmtPreco(o.preco);
        const origFmt = o.preco_original && o.preco_original > o.preco
            ? `<span class="offer-price-old">${this.fmtPreco(o.preco_original)}</span>` : '';

        const statusCls = o.status || 'pendente';
        const statusTxt = statusCls === 'postada' ? 'POSTADA' : 'PENDENTE';
        const hasLink = o.link_afiliado;

        let cupomInfo = '';
        if (o.dados_extra && o.dados_extra.cupom) {
            let cupomText = this._esc(o.dados_extra.cupom);
            // Destaca R$ XX ou XX% com verde neon e negrito
            cupomText = cupomText.replace(/(R\$\s*[\d\.,]+|\d+(?:\.\d+)?%)/gi, '<strong style="color: #34d399; font-size: 1.15em;">$1</strong>');
            cupomInfo = `
                <div style="margin-top: 8px; font-size: 12px; color: #c4b5fd; background: rgba(139, 92, 246, 0.15); padding: 6px 10px; border-radius: 6px; display: inline-block; border: 1px dashed #8b5cf6;">
                    🎟️ ${cupomText}
                </div>
            `;
        }

        const linkBtn = hasLink
            ? `<button class="btn btn-ghost btn-sm" onclick="window.open('${this._esc(o.link_afiliado)}','_blank')">🔗 Link</button>`
            : `<button class="btn btn-ghost btn-sm" onclick="App.abrirModalLink(${o.id})">🔗 Add Link</button>`;

        return `
            <div class="offer-card" id="card-${o.id}">
                <a href="${this._esc(o.link_original)}" target="_blank" style="text-decoration: none; color: inherit;">
                    <div class="offer-img-wrap">
                        <img class="offer-img" src="${img}" alt="${this._esc(o.titulo)}" loading="lazy"
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 200 200%22><rect fill=%22%231a1a30%22 width=%22200%22 height=%22200%22/><text x=%22100%22 y=%22110%22 text-anchor=%22middle%22 fill=%22%235c5c7a%22 font-size=%2240%22>📦</text></svg>'">
                        ${desc}
                        ${frete}
                        <span class="badge badge-store ${storeClass}">${storeIcon} ${o.loja}</span>
                    </div>
                    <div class="offer-body">
                        <div class="offer-title" style="color: #60a5fa; cursor: pointer;">${this._esc(o.titulo)}</div>
                        <div class="offer-pricing">
                            <span class="offer-price-current">${precoFmt}</span>
                            ${origFmt}
                        </div>
                        ${cupomInfo}
                        <div class="offer-meta">
                            <span class="offer-status ${statusCls}">${statusTxt}</span>
                            ${o.departamento_nome ? `<span class="offer-dept">${o.departamento_emoji || '📦'} ${this._esc(o.departamento_nome)}</span>` : ''}
                            ${o.vendedor ? `<span class="offer-seller">🏪 ${this._esc(o.vendedor)}</span>` : ''}
                        </div>
                    </div>
                </a>
                <div class="offer-footer">
                    <button class="btn btn-success btn-sm" onclick="App.postarOferta(${o.id})">📢 Postar</button>
                    ${linkBtn}
                    <button class="btn btn-danger btn-sm btn-icon" onclick="App.deletarOferta(${o.id})" title="Remover">🗑️</button>
                </div>
            </div>
        `;
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

    async postarOferta(id) {
        const card = document.getElementById(`card-${id}`);
        const btn = card?.querySelector('.btn-success');
        if (btn) { btn.innerHTML = '<span class="spinner"></span>'; btn.disabled = true; }

        try {
            const resp = await fetch(`${API}/api/ofertas/${id}/postar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ canais: ['telegram'] }),
            });
            const data = await resp.json();
            for (const r of (data.resultados || [])) {
                this.toast(r.sucesso ? `Postado no ${r.canal}!` : `Erro: ${r.resposta}`, r.sucesso ? 'success' : 'error');
            }
            await this.carregarOfertas();
            await this.carregarStats();
        } catch (e) {
            this.toast(`Erro: ${e.message}`, 'error');
        } finally {
            if (btn) { btn.innerHTML = '📢 Postar'; btn.disabled = false; }
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
        document.getElementById('inputLinkAfiliado').value = '';
        document.getElementById('modalLink').style.display = '';
    },

    fecharModalLink() { document.getElementById('modalLink').style.display = 'none'; },

    async salvarLinkAfiliado() {
        const id = document.getElementById('linkOfertaId').value;
        const link = document.getElementById('inputLinkAfiliado').value.trim();
        if (!link) { this.toast('Cole o link!', 'error'); return; }

        try {
            await fetch(`${API}/api/ofertas/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ link_afiliado: link }),
            });
            this.toast('Link salvo!', 'success');
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
