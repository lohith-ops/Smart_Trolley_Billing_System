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
        stockProduce: document.getElementById('stock-count-Produce')
    };

    // Load products
    async function loadProductsAndMap() {
        try {
            const res = await fetch('/api/products');
            if (res.ok) {
                products = await res.json();
                tallyStockLevels();
                
                // Parse URL parameter to check if pre-highlighted
                const urlParams = new URLSearchParams(window.location.search);
                const highlightCategory = urlParams.get('highlight');
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
        const counts = { Dairy: 0, Grains: 0, Bakery: 0, Produce: 0 };
        
        products.forEach(p => {
            if (counts[p.category] !== undefined) {
                counts[p.category]++;
            }
        });

        if (els.stockDairy) els.stockDairy.textContent = `${counts.Dairy} products`;
        if (els.stockGrains) els.stockGrains.textContent = `${counts.Grains} products`;
        if (els.stockBakery) els.stockBakery.textContent = `${counts.Bakery} products`;
        if (els.stockProduce) els.stockProduce.textContent = `${counts.Produce} products`;
    }

    // Highlight an aisle card
    function highlightAisle(category) {
        selectedCategory = category;
        els.aisles.forEach(a => {
            if (a.getAttribute('data-category') === category) {
                a.classList.add('active-highlight');
            } else {
                a.classList.remove('active-highlight');
            }
        });

        renderAisleProducts();
    }

    // Render products list for the highlighted aisle
    function renderAisleProducts() {
        if (!els.productsCard || !els.productsBody || !els.productsTitle) return;

        const filtered = products.filter(p => p.category === selectedCategory);
        els.productsTitle.innerHTML = `<i class="fa-solid fa-folder-open" style="margin-right:8px; color:var(--accent-cyan)"></i>Inventory in ${selectedCategory} Aisle`;
        
        els.productsBody.innerHTML = '';
        els.productsCard.style.display = 'block';

        if (filtered.length === 0) {
            els.productsBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: var(--text-secondary); padding: 24px;">
                        No items registered in this aisle.
                    </td>
                </tr>
            `;
            return;
        }

        filtered.forEach(p => {
            const stock = p.stock || 0;
            let stockBadge = 'In Stock';
            let stockClass = 'active';
            if (stock === 0) {
                stockBadge = 'Out of Stock';
                stockClass = 'offline';
            } else if (stock < 10) {
                stockBadge = `Low Stock (${stock})`;
                stockClass = 'idle';
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:600;">${p.name}</td>
                <td style="font-family:monospace;">${p.shelf || 'Aisle A - Shelf 1'}</td>
                <td><span class="trolley-status-badge ${stockClass}">${stockBadge}</span></td>
                <td style="color:var(--accent-green); font-weight:600;">Rs.${p.price.toFixed(2)}</td>
            `;
            els.productsBody.appendChild(tr);
        });

        // Scroll to table smoothly
        els.productsCard.scrollIntoView({ behavior: 'smooth' });
    }

    // Bind clicks to map cards
    els.aisles.forEach(aisle => {
        aisle.addEventListener('click', () => {
            const category = aisle.getAttribute('data-category');
            highlightAisle(category);
        });
    });

    loadProductsAndMap();
});
