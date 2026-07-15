/**
 * Product Search & Finder Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let products = [];
    let activeFilter = 'all';
    let searchQuery = '';

    const els = {
        grid: document.getElementById('search-results-grid'),
        filterButtons: document.querySelectorAll('#prod-filter-container .btn'),
        searchInput: document.getElementById('prod-search-input')
    };

    async function loadProducts() {
        try {
            const res = await fetch('/api/products');
            if (res.ok) {
                products = await res.json();
                renderResults();
            }
        } catch (e) {
            console.error("Failed to load catalog products:", e);
        }
    }

    function renderResults() {
        if (!els.grid) return;

        // Apply filters
        let filtered = products;
        if (activeFilter !== 'all') {
            filtered = filtered.filter(p => p.category === activeFilter);
        }

        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            filtered = filtered.filter(p => 
                p.name.toLowerCase().includes(query) || 
                (p.category && p.category.toLowerCase().includes(query))
            );
        }

        els.grid.innerHTML = '';

        if (filtered.length === 0) {
            els.grid.innerHTML = `
                <div class="glass-panel" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-search" style="font-size: 2.2rem; color: var(--accent-cyan); margin-bottom: 12px;"></i>
                    <p>No products matched your search or filter requirements.</p>
                </div>
            `;
            return;
        }

        filtered.forEach(p => {
            const card = document.createElement('div');
            card.className = 'card glass-panel gradient-border';
            card.style.flexDirection = 'column';
            card.style.alignItems = 'stretch';
            card.style.gap = '12px';

            const stock = p.stock || 0;
            let stockBadge = 'In Stock';
            let stockClass = 'active'; // green
            if (stock === 0) {
                stockBadge = 'Out of Stock';
                stockClass = 'offline'; // red
            } else if (stock < 10) {
                stockBadge = `Low Stock (${stock})`;
                stockClass = 'idle'; // orange
            }

            const offerText = p.offer && p.offer !== 'No Active Offers' ? p.offer : '';

            card.innerHTML = `
                <div class="trolley-details-header">
                    <strong style="font-size: 1.1rem; color: var(--text-primary);">${p.name}</strong>
                    <span class="trolley-status-badge ${stockClass}">${stockBadge}</span>
                </div>
                
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary);">
                    <span>Product Category</span>
                    <span class="trolley-stat-value" style="color:var(--accent-purple); font-weight:500;">${p.category || 'Grocery'}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary);">
                    <span>Shelving Location</span>
                    <span class="trolley-stat-value" style="font-family: monospace;"><i class="fa-solid fa-map-pin" style="margin-right: 4px;"></i>${p.shelf || 'Aisle A - Shelf 1'}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary); align-items: center;">
                    <span>Unit Price</span>
                    <span style="font-size: 1.2rem; color: var(--accent-green); font-weight: 700;">Rs.${p.price.toFixed(2)}</span>
                </div>

                ${offerText ? `
                <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; color: #f59e0b; font-size: 0.8rem; font-weight: 500;">
                    <i class="fa-solid fa-gift"></i>
                    <span>${offerText}</span>
                </div>` : ''}

                <div style="margin-top: 10px;">
                    <a href="navigation.html?highlight=${encodeURIComponent(p.category || 'Grocery')}" class="btn btn-outline" style="display: block; text-align: center; font-size: 0.8rem; padding: 6px 0; text-decoration: none;">
                        <i class="fa-solid fa-map" style="margin-right: 6px;"></i> Locate on Map
                    </a>
                </div>
            `;
            els.grid.appendChild(card);
        });
    }

    // Filter clicks
    els.filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            els.filterButtons.forEach(b => b.classList.remove('active-filter', 'active'));
            btn.classList.add('active');
            activeFilter = btn.getAttribute('data-filter');
            renderResults();
        });
    });

    // Input changes
    if (els.searchInput) {
        els.searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderResults();
        });
    }

    loadProducts();
});
