/**
 * Multi-Trolley Dashboard Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let allTrolleys = [];
    let activeFilter = 'all';
    let searchQuery = '';

    const els = {
        container: document.getElementById('trolleys-container'),
        filterButtons: document.querySelectorAll('#filter-container .btn'),
        searchBar: document.getElementById('trolley-search')
    };

    // Fetch and render
    async function fetchTrolleys() {
        try {
            const res = await fetch('/api/trolleys');
            if (res.ok) {
                allTrolleys = await res.json();
                renderTrolleys();
            }
        } catch (e) {
            console.error("Failed to fetch trolleys:", e);
        }
    }

    // Render cards
    function renderTrolleys() {
        if (!els.container) return;

        // Apply filters
        let filtered = allTrolleys;
        if (activeFilter !== 'all') {
            filtered = filtered.filter(t => t.status.toLowerCase() === activeFilter);
        }

        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            filtered = filtered.filter(t => 
                t.id.toLowerCase().includes(query) || 
                t.customer.toLowerCase().includes(query)
            );
        }

        els.container.innerHTML = '';

        if (filtered.length === 0) {
            els.container.innerHTML = `
                <div class="glass-panel" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; margin-bottom: 12px; color: var(--accent-cyan);"></i>
                    <p>No trolleys match the current filters or search terms.</p>
                </div>
            `;
            return;
        }

        filtered.forEach(t => {
            const card = document.createElement('div');
            card.className = 'card glass-panel gradient-border';
            card.style.flexDirection = 'column';
            card.style.alignItems = 'stretch';
            card.style.gap = '12px';
            
            let statusClass = t.status.toLowerCase();
            let batteryIcon = 'fa-battery-full';
            let batteryColor = 'var(--accent-green)';
            
            if (t.battery < 20) {
                batteryIcon = 'fa-battery-empty';
                batteryColor = 'var(--accent-red)';
            } else if (t.battery < 60) {
                batteryIcon = 'fa-battery-half';
                batteryColor = '#f59e0b';
            }

            card.innerHTML = `
                <div class="trolley-details-header">
                    <strong style="font-size: 1.1rem; color: var(--text-primary);"><i class="fa-solid fa-cart-shopping" style="margin-right: 8px;"></i>${t.id}</strong>
                    <span class="trolley-status-badge ${statusClass}">${t.status}</span>
                </div>
                
                <div class="trolley-stat-row">
                    <span>Shopper Name</span>
                    <span class="trolley-stat-value">${t.customer === 'None' ? 'Unassigned' : t.customer}</span>
                </div>
                <div class="trolley-stat-row">
                    <span>Cart Items</span>
                    <span class="trolley-stat-value">${t.items} units</span>
                </div>
                <div class="trolley-stat-row">
                    <span>Active Bill</span>
                    <span class="trolley-stat-value" style="color: var(--accent-green); font-weight: 600;">Rs.${t.total.toFixed(2)}</span>
                </div>
                <div class="trolley-stat-row">
                    <span>Battery Status</span>
                    <span class="trolley-stat-value" style="color: ${batteryColor}">
                        <i class="fa-solid ${batteryIcon}" style="margin-right: 6px;"></i>${t.battery}%
                    </span>
                </div>
                <div class="trolley-stat-row">
                    <span>Connection Latency</span>
                    <span class="trolley-stat-value">${t.latency > 0 ? `${t.latency}ms` : 'N/A'}</span>
                </div>

                <div style="margin-top: 10px; display: flex; gap: 8px;">
                    <a href="trolley-monitor.html?id=${t.id}" class="btn btn-outline" style="flex: 1; text-align: center; font-size: 0.8rem; padding: 6px 0; text-decoration: none;">
                        <i class="fa-solid fa-desktop" style="margin-right: 6px;"></i> Monitor Details
                    </a>
                </div>
            `;
            els.container.appendChild(card);
        });
    }

    // Filter Buttons Listeners
    els.filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            els.filterButtons.forEach(b => b.classList.remove('active-filter', 'active'));
            btn.classList.add('active');
            activeFilter = btn.getAttribute('data-filter');
            renderTrolleys();
        });
    });

    // Search bar listener
    if (els.searchBar) {
        els.searchBar.addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderTrolleys();
        });
    }

    // Init
    fetchTrolleys();
    setInterval(fetchTrolleys, 3000);
});
