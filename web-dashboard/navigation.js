/**
 * Store Navigation & Layout Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let products = [];
    let selectedCategory = '';

    const els = {
        aisles: document.querySelectorAll('.store-aisle'),
        productsCard: document.getElementById('aisle-products-card'),
        productsTitle: document.getElementById('aisle-products-title'),
        productsBody: document.getElementById('aisle-products-body'),
        
        // Stock tallies on map
        stockDairy: document.getElementById('stock-count-Dairy'),
        stockGrains: document.getElementById('stock-count-Grains'),
        stockBakery: document.getElementById('stock-count-Bakery'),
        stockProduce: document.getElementById('stock-count-Produce'),
        stockGrocery: document.getElementById('stock-count-Grocery')
    };

    // Load products
    async function loadProductsAndMap() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/products');
            if (res.ok) {
                products = await res.json();
                tallyStockLevels();
                
                // Parse URL parameter to check if pre-highlighted from Product Finder
                const urlParams = new URLSearchParams(window.location.search);
                const highlightCategory = urlParams.get('highlight') || urlParams.get('category');
                if (highlightCategory) {
                    highlightAisle(highlightCategory);
                }
            }
        } catch (e) {
            console.error("Failed to load products for map directory:", e);
        }
    }

    // Tally product counts per category
    function tallyStockLevels() {
        const counts = {
            Dairy: 0,
            Grains: 0,
            Bakery: 0,
            Produce: 0,
            Grocery: 0
        };
        
        products.forEach(p => {
            const cat = (p.category || 'Grocery').trim();
            for (const key of Object.keys(counts)) {
                if (key.toLowerCase() === cat.toLowerCase()) {
                    counts[key]++;
                    break;
                }
            }
        });

        if (els.stockDairy) els.stockDairy.textContent = `${counts.Dairy} item${counts.Dairy === 1 ? '' : 's'}`;
        if (els.stockGrains) els.stockGrains.textContent = `${counts.Grains} item${counts.Grains === 1 ? '' : 's'}`;
        if (els.stockBakery) els.stockBakery.textContent = `${counts.Bakery} item${counts.Bakery === 1 ? '' : 's'}`;
        if (els.stockProduce) els.stockProduce.textContent = `${counts.Produce} item${counts.Produce === 1 ? '' : 's'}`;
        if (els.stockGrocery) els.stockGrocery.textContent = `${counts.Grocery} item${counts.Grocery === 1 ? '' : 's'}`;
    }

    // Highlight an aisle card
    function highlightAisle(category) {
        if (!category) return;
        selectedCategory = category.trim();
        const targetLow = selectedCategory.toLowerCase();
        let matched = false;

        els.aisles.forEach(a => {
            const aCat = (a.getAttribute('data-category') || '').trim().toLowerCase();
            if (aCat === targetLow) {
                a.classList.add('active-highlight');
                matched = true;
            } else {
                a.classList.remove('active-highlight');
            }
        });

        if (!matched && els.aisles.length > 0) {
            // Default highlight to first aisle if no exact match
            selectedCategory = els.aisles[0].getAttribute('data-category') || 'Dairy';
            els.aisles[0].classList.add('active-highlight');
        }

        renderAisleProducts();
    }

    // Render products list for the highlighted aisle
    function renderAisleProducts() {
        if (!els.productsCard || !els.productsBody || !els.productsTitle) return;

        const targetLow = (selectedCategory || '').trim().toLowerCase();
        const filtered = products.filter(p => (p.category || 'Grocery').trim().toLowerCase() === targetLow);
        
        els.productsTitle.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; width: 100%;">
                <span>
                    <i class="fa-solid fa-folder-open" style="margin-right: 8px; color: var(--accent-cyan)"></i>
                    Inventory in ${selectedCategory} Aisle (${filtered.length} item${filtered.length === 1 ? '' : 's'})
                </span>
                <a href="product-search.html?category=${encodeURIComponent(selectedCategory)}" class="btn btn-outline" style="font-size: 0.8rem; padding: 6px 14px; text-decoration: none;">
                    <i class="fa-solid fa-magnifying-glass" style="margin-right: 6px;"></i> View in Product Finder
                </a>
            </div>
        `;
        
        els.productsBody.innerHTML = '';
        els.productsCard.style.display = 'block';

        if (filtered.length === 0) {
            els.productsBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: var(--text-secondary); padding: 32px;">
                        <i class="fa-solid fa-box-open" style="font-size: 1.8rem; margin-bottom: 8px; color: var(--text-secondary); display: block;"></i>
                        No items currently registered in this aisle.
                    </td>
                </tr>
            `;
            return;
        }

        filtered.forEach(p => {
            const stock = (typeof p.stock === 'number') ? p.stock : (parseInt(p.stock, 10) || 0);
            let stockBadge = 'In Stock';
            let stockClass = 'active';
            if (stock <= 0) {
                stockBadge = 'Out of Stock';
                stockClass = 'offline';
            } else if (stock < 10) {
                stockBadge = `Low Stock (${stock})`;
                stockClass = 'idle';
            } else {
                stockBadge = `In Stock (${stock})`;
            }

            const priceVal = (typeof p.price === 'number') ? p.price : (parseFloat(p.price) || 0);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:600; color: var(--text-primary);">${p.name || 'Unnamed Item'}</td>
                <td style="font-family:monospace; color: var(--accent-purple);"><i class="fa-solid fa-location-dot" style="margin-right: 6px; font-size: 0.8rem;"></i>${p.shelf || 'Aisle A - Shelf 1'}</td>
                <td><span class="trolley-status-badge ${stockClass}">${stockBadge}</span></td>
                <td style="color:var(--accent-green); font-weight:700;">Rs.${priceVal.toFixed(2)}</td>
            `;
            els.productsBody.appendChild(tr);
        });

        // Smooth scroll to table
        els.productsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Bind clicks to map aisle cards
    els.aisles.forEach(aisle => {
        aisle.addEventListener('click', () => {
            const category = aisle.getAttribute('data-category');
            highlightAisle(category);
        });
    });

    loadProductsAndMap();
});
