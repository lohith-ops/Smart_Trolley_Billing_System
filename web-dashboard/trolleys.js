/**
 * Multi-Trolley Fleet Dashboard — trolleys.js v2.0
 * Displays real-time cards for every trolley registered in MongoDB.
 * Data source: GET /api/trolleys
 */

document.addEventListener('DOMContentLoaded', () => {
    let allTrolleys = [];
    let activeFilter = 'all';
    let searchQuery = '';

    const els = {
        container:     document.getElementById('trolleys-container'),
        filterButtons: document.querySelectorAll('#filter-container .btn'),
        searchBar:     document.getElementById('trolley-search'),
        statOnline:    document.getElementById('stat-online-count'),
        statTotal:     document.getElementById('stat-total-count'),
        statBattery:   document.getElementById('stat-avg-battery'),
        statActive:    document.getElementById('stat-active-count')
    };

    // ── Fetch & render ──────────────────────────────────────────────────────
    async function fetchTrolleys() {
        try {
            const res = await fetch('/api/trolleys');
            if (res.ok) {
                allTrolleys = await res.json();
                updateSummaryStats();
                renderTrolleys();
            }
        } catch (e) {
            console.error("Failed to fetch trolleys:", e);
        }
    }

    // ── Summary stat bar ────────────────────────────────────────────────────
    function updateSummaryStats() {
        const online  = allTrolleys.filter(t => t.status === 'online').length;
        const active  = allTrolleys.filter(t => t.item_count > 0).length;
        const battAvg = allTrolleys.length
            ? Math.round(allTrolleys.reduce((s, t) => s + (t.battery || 0), 0) / allTrolleys.length)
            : 0;

        if (els.statOnline)  els.statOnline.textContent  = online;
        if (els.statTotal)   els.statTotal.textContent   = allTrolleys.length;
        if (els.statBattery) els.statBattery.textContent = battAvg + '%';
        if (els.statActive)  els.statActive.textContent  = active;
    }

    // ── Render trolley cards ────────────────────────────────────────────────
    function renderTrolleys() {
        if (!els.container) return;

        // Filter
        let filtered = allTrolleys;
        if (activeFilter !== 'all') {
            filtered = filtered.filter(t => t.status.toLowerCase() === activeFilter);
        }
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(t =>
                t.id.toLowerCase().includes(q) ||
                (t.name || '').toLowerCase().includes(q)
            );
        }

        els.container.innerHTML = '';

        if (filtered.length === 0) {
            els.container.innerHTML = `
                <div class="glass-panel" style="grid-column:1/-1;padding:40px;text-align:center;color:var(--text-secondary);">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size:2rem;margin-bottom:12px;color:var(--accent-cyan);"></i>
                    <p>No trolleys match the current filters or search terms.</p>
                </div>`;
            return;
        }

        filtered.forEach(t => buildTrolleyCard(t));
    }

    function buildTrolleyCard(t) {
        const isOnline = t.status === 'online';
        const statusLabel = isOnline ? 'Online' : 'Offline';
        const statusClass = isOnline ? 'active' : 'offline';

        // Battery icon & color
        let batteryIcon  = 'fa-battery-full';
        let batteryColor = 'var(--accent-green)';
        const batt = t.battery || 0;
        if (batt < 20) {
            batteryIcon  = 'fa-battery-empty';
            batteryColor = 'var(--accent-red)';
        } else if (batt < 50) {
            batteryIcon  = 'fa-battery-quarter';
            batteryColor = '#f59e0b';
        } else if (batt < 75) {
            batteryIcon  = 'fa-battery-half';
            batteryColor = '#eab308';
        }

        // RSSI signal display
        const rssi = t.wifi_rssi || 0;
        let rssiLabel = 'N/A';
        let rssiColor = 'var(--text-secondary)';
        if (rssi !== 0) {
            rssiLabel = rssi + ' dBm';
            rssiColor = rssi >= -65 ? 'var(--accent-green)' : (rssi >= -80 ? '#f59e0b' : 'var(--accent-red)');
        }

        // Cart status badge
        const cartStatus = t.cart_status || 'ACTIVE';
        let cartBadge = '';
        if (cartStatus === 'BILL_GENERATED') {
            cartBadge = `<span class="trolley-status-badge idle" style="font-size:0.7rem;margin-left:8px;">Bill Pending</span>`;
        }

        const card = document.createElement('div');
        card.className = 'card glass-panel gradient-border';
        card.style.flexDirection = 'column';
        card.style.alignItems    = 'stretch';
        card.style.gap           = '12px';

        card.innerHTML = `
            <div class="trolley-details-header">
                <strong style="font-size:1.1rem;color:var(--text-primary);">
                    <i class="fa-solid fa-cart-shopping" style="margin-right:8px;"></i>${t.id}
                </strong>
                <div style="display:flex;align-items:center;gap:6px;">
                    <span class="trolley-status-badge ${statusClass}">
                        <span class="pulse-dot" style="background:${isOnline ? 'var(--accent-green)' : 'var(--accent-red)'};width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px;${isOnline ? 'box-shadow:0 0 5px var(--accent-green);animation:pulse 1.5s infinite;' : ''}"></span>
                        ${statusLabel}
                    </span>
                    ${cartBadge}
                </div>
            </div>

            <div class="trolley-stat-row">
                <span>Trolley Name</span>
                <span class="trolley-stat-value">${t.name || t.id}</span>
            </div>
            <div class="trolley-stat-row">
                <span>Cart Items</span>
                <span class="trolley-stat-value">${t.item_count || 0} units</span>
            </div>
            <div class="trolley-stat-row">
                <span>Cart Value</span>
                <span class="trolley-stat-value" style="color:var(--accent-green);font-weight:600;">
                    Rs.${(t.cart_value || 0).toFixed(2)}
                </span>
            </div>
            <div class="trolley-stat-row">
                <span>Battery</span>
                <span class="trolley-stat-value" style="color:${batteryColor}">
                    <i class="fa-solid ${batteryIcon}" style="margin-right:6px;"></i>${batt}%
                </span>
            </div>
            <div class="trolley-stat-row">
                <span>Wi-Fi Signal</span>
                <span class="trolley-stat-value" style="color:${rssiColor}">${rssiLabel}</span>
            </div>
            <div class="trolley-stat-row">
                <span>IP Address</span>
                <span class="trolley-stat-value" style="font-family:monospace;font-size:0.82rem;">
                    ${t.ip_address || '—'}
                </span>
            </div>
            <div class="trolley-stat-row">
                <span>Last Seen</span>
                <span class="trolley-stat-value">${t.last_seen_str || 'Never'}</span>
            </div>

            <div style="margin-top:10px;display:flex;gap:8px;">
                <a href="trolley-monitor.html?id=${t.id}" class="btn btn-outline"
                   style="flex:1;text-align:center;font-size:0.8rem;padding:6px 0;text-decoration:none;">
                    <i class="fa-solid fa-desktop" style="margin-right:6px;"></i>Monitor Details
                </a>
            </div>`;

        els.container.appendChild(card);
    }

    // ── Filter buttons ──────────────────────────────────────────────────────
    els.filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            els.filterButtons.forEach(b => b.classList.remove('active-filter', 'active'));
            btn.classList.add('active');
            activeFilter = btn.getAttribute('data-filter');
            renderTrolleys();
        });
    });

    // ── Search bar ──────────────────────────────────────────────────────────
    if (els.searchBar) {
        els.searchBar.addEventListener('input', e => {
            searchQuery = e.target.value;
            renderTrolleys();
        });
    }

    // ── Init & polling ──────────────────────────────────────────────────────
    fetchTrolleys();
    setInterval(fetchTrolleys, 3000);
});
