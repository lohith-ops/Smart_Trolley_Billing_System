/**
 * Product Search & Finder Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let products = [];
    let activeFilter = 'all';
    let searchQuery = '';

    const els = {
        grid: document.getElementById('search-results-grid'),
        filterContainer: document.getElementById('prod-filter-container'),
        filterButtons: document.querySelectorAll('#prod-filter-container .btn'),
        searchInput: document.getElementById('prod-search-input')
    };

    // Check URL parameters for pre-selected category or search query
    const urlParams = new URLSearchParams(window.location.search);
    const initialCategory = urlParams.get('category') || urlParams.get('filter');
    const initialQuery = urlParams.get('q') || urlParams.get('search');

    if (initialCategory) {
        activeFilter = initialCategory;
    }
    if (initialQuery && els.searchInput) {
        searchQuery = initialQuery;
        els.searchInput.value = initialQuery;
    }

    async function loadProducts() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/products');
            if (res.ok) {
                products = await res.json();
                syncActiveFilterButtons();
                renderResults();
            }
        } catch (e) {
            console.error("Failed to load catalog products:", e);
        }
    }

    function syncActiveFilterButtons() {
        if (!els.filterContainer) return;
        const buttons = els.filterContainer.querySelectorAll('.btn');
        buttons.forEach(btn => {
            const filterVal = (btn.getAttribute('data-filter') || '').toLowerCase().trim();
            const currentFilter = activeFilter.toLowerCase().trim();
            if (filterVal === currentFilter) {
                btn.classList.add('active', 'active-filter');
            } else {
                btn.classList.remove('active', 'active-filter');
            }
        });
    }

    function renderResults() {
        if (!els.grid) return;

        // Apply filters
        let filtered = products;
        if (activeFilter && activeFilter.toLowerCase() !== 'all') {
            const filterLow = activeFilter.toLowerCase().trim();
            filtered = filtered.filter(p => (p.category || 'Grocery').toLowerCase().trim() === filterLow);
        }

        if (searchQuery) {
            const query = searchQuery.toLowerCase().trim();
            filtered = filtered.filter(p => 
                (p.name && p.name.toLowerCase().includes(query)) || 
                (p.category && p.category.toLowerCase().includes(query)) ||
                (p.shelf && p.shelf.toLowerCase().includes(query)) ||
                (p.offer && p.offer.toLowerCase().includes(query))
            );
        }

        els.grid.innerHTML = '';

        if (filtered.length === 0) {
            els.grid.innerHTML = `
                <div class="glass-panel" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-search" style="font-size: 2.2rem; color: var(--accent-cyan); margin-bottom: 12px;"></i>
                    <p style="font-size: 1.05rem; color: var(--text-primary); margin-bottom: 6px;">No products found</p>
                    <p style="font-size: 0.85rem;">No items matched category "<strong>${activeFilter}</strong>"${searchQuery ? ` or search "<strong>${searchQuery}</strong>"` : ''}.</p>
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

            const stock = (typeof p.stock === 'number') ? p.stock : (parseInt(p.stock, 10) || 0);
            let stockBadge = 'In Stock';
            let stockClass = 'active'; // green
            if (stock <= 0) {
                stockBadge = 'Out of Stock';
                stockClass = 'offline'; // red
            } else if (stock < 10) {
                stockBadge = `Low Stock (${stock})`;
                stockClass = 'idle'; // orange
            } else {
                stockBadge = `In Stock (${stock})`;
            }

            const offerText = p.offer && p.offer !== 'No Active Offers' ? p.offer : '';
            const priceVal = (typeof p.price === 'number') ? p.price : (parseFloat(p.price) || 0);
            const categoryName = p.category || 'Grocery';

            card.innerHTML = `
                <div class="trolley-details-header">
                    <strong style="font-size: 1.1rem; color: var(--text-primary);">${p.name || 'Unnamed Product'}</strong>
                    <span class="trolley-status-badge ${stockClass}">${stockBadge}</span>
                </div>
                
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary);">
                    <span>Product Category</span>
                    <span class="trolley-stat-value" style="color:var(--accent-purple); font-weight:500;">${categoryName}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary);">
                    <span>Shelving Location</span>
                    <span class="trolley-stat-value" style="font-family: monospace;"><i class="fa-solid fa-map-pin" style="margin-right: 4px;"></i>${p.shelf || 'Aisle A - Shelf 1'}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary); align-items: center;">
                    <span>Unit Price</span>
                    <span style="font-size: 1.2rem; color: var(--accent-green); font-weight: 700;">Rs.${priceVal.toFixed(2)}</span>
                </div>

                ${offerText ? `
                <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; color: #f59e0b; font-size: 0.8rem; font-weight: 500;">
                    <i class="fa-solid fa-gift"></i>
                    <span>${offerText}</span>
                </div>` : ''}

                <div style="margin-top: 10px;">
                    <a href="navigation.html?highlight=${encodeURIComponent(categoryName)}" class="btn btn-outline" style="display: block; text-align: center; font-size: 0.8rem; padding: 8px 0; text-decoration: none;">
                        <i class="fa-solid fa-map-location-dot" style="margin-right: 6px;"></i> Locate on Map
                    </a>
                </div>
            `;
            els.grid.appendChild(card);
        });
    }

    // Filter button clicks
    if (els.filterContainer) {
        els.filterContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn');
            if (!btn) return;
            activeFilter = btn.getAttribute('data-filter') || 'all';
            syncActiveFilterButtons();
            renderResults();
        });
    }

    // Search input changes
    if (els.searchInput) {
        els.searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderResults();
        });
    }

    loadProducts();
});
