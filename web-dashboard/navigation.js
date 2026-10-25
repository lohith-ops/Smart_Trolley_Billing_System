/**
 * Store Navigation & Floor Map Logic - Smart Trolley Billing System
 * Features:
 * - Interactive aisle cards with live inventory tallies and unit counts
 * - Seamless deep-linking from Product Finder with automatic aisle & item spotlighting
 * - Category synchronization (Grains, Dairy, Bakery, Produce, Beverages, Snacks, Grocery)
 * - Quick inspection links to Product Finder and session wishlist integration
 */

document.addEventListener('DOMContentLoaded', () => {
    let products = [];
    let selectedCategory = '';
    let targetProductName = '';

    const CATEGORY_META = {
        'grains':    { label: 'Grains',    bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)', icon: 'fa-wheat-awn' },
        'dairy':     { label: 'Dairy',     bg: 'rgba(6, 182, 212, 0.15)',  text: '#06b6d4', border: 'rgba(6, 182, 212, 0.3)',  icon: 'fa-cow' },
        'bakery':    { label: 'Bakery',    bg: 'rgba(249, 115, 22, 0.15)', text: '#f97316', border: 'rgba(249, 115, 22, 0.3)', icon: 'fa-bread-slice' },
        'produce':   { label: 'Produce',   bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: 'rgba(16, 185, 129, 0.3)', icon: 'fa-apple-whole' },
        'beverages': { label: 'Beverages', bg: 'rgba(139, 92, 246, 0.15)', text: '#a78bfa', border: 'rgba(139, 92, 246, 0.3)', icon: 'fa-bottle-water' },
        'snacks':    { label: 'Snacks',    bg: 'rgba(236, 72, 153, 0.15)', text: '#f472b6', border: 'rgba(236, 72, 153, 0.3)', icon: 'fa-cookie' },
        'grocery':   { label: 'Grocery',   bg: 'rgba(148, 163, 184, 0.15)', text: '#94a3b8', border: 'rgba(148, 163, 184, 0.3)', icon: 'fa-basket-shopping' }
    };

    function getCategoryMeta(cat) {
        const key = (cat || 'grocery').toLowerCase().trim();
        return CATEGORY_META[key] || CATEGORY_META['grocery'];
    }

    function sanitizeCategory(p) {
        let cat = (p.category || '').trim();
        if (p.name && p.name.toLowerCase().includes('rice') && (!cat || cat.toLowerCase() === 'dairy')) {
            return 'Grains';
        }
        return cat || 'Grocery';
    }

    const els = {
        aisles: document.querySelectorAll('.store-aisle'),
        productsCard: document.getElementById('aisle-products-card'),
        productsTitle: document.getElementById('aisle-products-title'),
        productsBody: document.getElementById('aisle-products-body')
    };

    // Load products
    async function loadProductsAndMap() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/products');
            if (res.ok) {
                const data = await res.json();
                products = data.map(p => ({
                    ...p,
                    category: sanitizeCategory(p)
                }));
                tallyStockLevels();
                
                // Parse URL parameters for pre-selected category and targeted product
                const urlParams = new URLSearchParams(window.location.search);
                const highlightCategory = urlParams.get('highlight') || urlParams.get('category');
                targetProductName = (urlParams.get('product') || urlParams.get('item') || '').toLowerCase().trim();

                if (highlightCategory) {
                    highlightAisle(highlightCategory);
                } else if (els.aisles.length > 0) {
                    // Default to first aisle (Grains)
                    const defaultCat = els.aisles[0].getAttribute('data-category') || 'Grains';
                    highlightAisle(defaultCat);
                }
            }
        } catch (e) {
            console.error("Failed to load products for map directory:", e);
        }
    }

    // Tally product counts and units per category dynamically
    function tallyStockLevels() {
        const counts = {};

        // Initialize counts for all defined aisles
        els.aisles.forEach(a => {
            const cat = a.getAttribute('data-category');
            if (cat) {
                counts[cat.toLowerCase()] = { items: 0, units: 0 };
            }
        });

        products.forEach(p => {
            const catKey = (p.category || 'grocery').toLowerCase().trim();
            const stock = (typeof p.stock === 'number') ? p.stock : (parseInt(p.stock, 10) || 0);

            if (!counts[catKey]) {
                counts[catKey] = { items: 0, units: 0 };
            }
            counts[catKey].items++;
            counts[catKey].units += stock;
        });

        // Update DOM for each aisle element
        els.aisles.forEach(a => {
            const cat = a.getAttribute('data-category');
            if (!cat) return;
            const countEl = document.getElementById(`stock-count-${cat}`);
            if (countEl) {
                const data = counts[cat.toLowerCase()] || { items: 0, units: 0 };
                if (data.items === 0) {
                    countEl.textContent = '0 items currently stocked';
                } else {
                    countEl.textContent = `${data.items} item${data.items === 1 ? '' : 's'} (${data.units} units)`;
                }
            }
        });
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
            selectedCategory = els.aisles[0].getAttribute('data-category') || 'Grains';
            els.aisles[0].classList.add('active-highlight');
        }

        renderAisleProducts();
    }

    // Render products list for the highlighted aisle
    function renderAisleProducts() {
        if (!els.productsCard || !els.productsBody || !els.productsTitle) return;

        const targetLow = (selectedCategory || '').trim().toLowerCase();
        const filtered = products.filter(p => (p.category || 'Grocery').trim().toLowerCase() === targetLow);
        const catMeta = getCategoryMeta(selectedCategory);

        els.productsTitle.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; width: 100%;">
                <span style="display: flex; align-items: center; gap: 10px;">
                    <span style="background: ${catMeta.bg}; color: ${catMeta.text}; border: 1px solid ${catMeta.border}; padding: 4px 10px; border-radius: 8px; font-size: 0.95rem; font-weight: 600;">
                        <i class="fa-solid ${catMeta.icon}"></i> ${selectedCategory}
                    </span>
                    <span>Shelved Products (${filtered.length} item${filtered.length === 1 ? '' : 's'})</span>
                </span>
                <div style="display: flex; gap: 8px;">
                    <a href="product-search.html?category=${encodeURIComponent(selectedCategory)}" class="btn btn-outline" style="font-size: 0.8rem; padding: 6px 14px; text-decoration: none;">
                        <i class="fa-solid fa-magnifying-glass" style="margin-right: 6px; color: var(--accent-cyan);"></i> View in Product Finder
                    </a>
                </div>
            </div>
        `;
        
        els.productsBody.innerHTML = '';
        els.productsCard.style.display = 'block';

        if (filtered.length === 0) {
            els.productsBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 36px;">
                        <i class="fa-solid fa-boxes-packing" style="font-size: 2rem; margin-bottom: 10px; color: var(--text-secondary); opacity: 0.4; display: block;"></i>
                        No products are currently recorded in the <strong>${selectedCategory}</strong> aisle.
                    </td>
                </tr>
            `;
            return;
        }

        let spotlightedElement = null;

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
            const isSpotlight = targetProductName && p.name && p.name.toLowerCase().includes(targetProductName);

            const tr = document.createElement('tr');
            if (isSpotlight) {
                tr.className = 'spotlight-product-row';
                spotlightedElement = tr;
            }

            tr.innerHTML = `
                <td style="font-weight:600; color: var(--text-primary);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span>${p.name || 'Unnamed Item'}</span>
                        ${isSpotlight ? '<span class="trolley-status-badge active" style="font-size: 0.7rem; padding: 2px 6px;"><i class="fa-solid fa-bullseye"></i> Target Item</span>' : ''}
                        ${p.offer && p.offer !== 'No Active Offers' && p.offer !== 'Standard Price' ? `
                            <span style="font-size: 0.72rem; color: #f59e0b; background: rgba(245, 158, 11, 0.12); padding: 2px 6px; border-radius: 4px;">
                                <i class="fa-solid fa-gift"></i> ${p.offer}
                            </span>
                        ` : ''}
                    </div>
                    <div style="font-size: 0.72rem; color: var(--text-secondary); font-family: monospace; margin-top: 2px;">
                        UID: ${p.uid || 'N/A'}
                    </div>
                </td>
                <td>
                    <span style="background: ${catMeta.bg}; color: ${catMeta.text}; border: 1px solid ${catMeta.border}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">
                        <i class="fa-solid ${catMeta.icon}"></i> ${p.category}
                    </span>
                </td>
                <td style="font-family:monospace; color: var(--accent-cyan); font-weight: 500;">
                    <i class="fa-solid fa-map-pin" style="margin-right: 6px;"></i>${p.shelf || 'Aisle A - Shelf 1'}
                </td>
                <td><span class="trolley-status-badge ${stockClass}">${stockBadge}</span></td>
                <td style="color:var(--accent-green); font-weight:700; font-size: 0.95rem;">Rs.${priceVal.toFixed(2)}</td>
                <td style="text-align: right;">
                    <a href="product-search.html?q=${encodeURIComponent(p.name)}" class="btn btn-outline" style="font-size: 0.75rem; padding: 4px 10px; text-decoration: none;" title="Locate in Finder">
                        <i class="fa-solid fa-magnifying-glass"></i>
                    </a>
                </td>
            `;
            els.productsBody.appendChild(tr);
        });

        // Smooth scroll to table or spotlighted element
        setTimeout(() => {
            if (spotlightedElement) {
                spotlightedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                els.productsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }, 150);
    }

    // Bind clicks to map aisle cards
    els.aisles.forEach(aisle => {
        aisle.addEventListener('click', () => {
            const category = aisle.getAttribute('data-category');
            targetProductName = ''; // Clear spotlight on manual aisle selection
            highlightAisle(category);
        });
    });

    loadProductsAndMap();
});
