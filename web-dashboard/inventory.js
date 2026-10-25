/**
 * Inventory Management & Heat Map Logic - Smart Trolley Billing System
 * Features:
 * - Dynamic category detection and auto-suggestion (Grains, Dairy, Bakery, Produce, etc.)
 * - Automatic correction of misclassifications (e.g. Rice marked as Dairy -> Grains)
 * - Real-time sync with MongoDB central catalog
 * - Authenticated CRUD operations via authFetch
 * - Interactive stock heat map with low-stock alerts
 */

document.addEventListener('DOMContentLoaded', () => {
    let Products = [];
    let searchQuery = '';
    let categoryFilter = 'all';
    let userManuallySelectedCategory = false;

    // Visual design tokens per category
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

    /**
     * Smart category detection based on product name keywords
     */
    function detectCategoryFromName(name) {
        if (!name) return 'Grains';
        const nl = name.toLowerCase().trim();
        if (/rice|basmati|wheat|grain|oat|flour|atta|dal|pulse|quinoa|cereal|pasta|sugar|brown rice|jeera rice/.test(nl)) return 'Grains';
        if (/milk|cheese|cheddar|butter|curd|yogurt|ghee|paneer|cream|dairy|egg/.test(nl)) return 'Dairy';
        if (/bread|toast|bun|cake|muffin|bakery|croissant|pastry|bagel|cookie/.test(nl)) return 'Bakery';
        if (/apple|banana|orange|fruit|vegetable|tomato|potato|onion|produce|berry|mango/.test(nl)) return 'Produce';
        if (/juice|soda|water|tea|coffee|drink|cola|pepsi|sprite|beverage/.test(nl)) return 'Beverages';
        if (/chip|chips|snack|chocolate|candy|cracker|biscuit|namkeen/.test(nl)) return 'Snacks';
        return 'Grocery';
    }

    const els = {
        inventoryList: document.getElementById('inventory-list'),
        addProductBtn: document.getElementById('add-product-btn'),
        heatmap: document.getElementById('stock-heatmap'),
        searchInput: document.getElementById('inventory-search'),
        categoryFilter: document.getElementById('inventory-category-filter'),
        countLabel: document.getElementById('inventory-count-label'),

        // Modal Elements
        productModal: document.getElementById('product-modal'),
        productForm: document.getElementById('product-form'),
        modalTitle: document.getElementById('modal-title'),
        prodOriginalUid: document.getElementById('prod-original-uid'),
        prodUid: document.getElementById('prod-uid'),
        prodName: document.getElementById('prod-name'),
        prodPrice: document.getElementById('prod-price'),
        prodStock: document.getElementById('prod-stock'),
        prodCategory: document.getElementById('prod-category'),
        categoryAutoHint: document.getElementById('category-auto-hint'),
        prodShelf: document.getElementById('prod-shelf'),
        prodOffer: document.getElementById('prod-offer'),
        prodCancelBtn: document.getElementById('prod-cancel-btn'),
        prodSubmitBtn: document.getElementById('prod-submit-btn')
    };

    // Initialize Inventory
    async function initInventory() {
        await fetchProducts();

        if (els.addProductBtn) els.addProductBtn.addEventListener('click', openAddModal);
        if (els.prodCancelBtn) els.prodCancelBtn.addEventListener('click', closeProductModal);
        if (els.productForm) els.productForm.addEventListener('submit', handleFormSubmit);

        // Auto-detection of category as user types product name in modal
        if (els.prodName && els.prodCategory) {
            els.prodName.addEventListener('input', () => {
                const nameVal = els.prodName.value.trim();
                if (!nameVal) {
                    if (els.categoryAutoHint) els.categoryAutoHint.style.display = 'none';
                    return;
                }
                if (!userManuallySelectedCategory) {
                    const detected = detectCategoryFromName(nameVal);
                    if (detected && els.prodCategory.value !== detected) {
                        els.prodCategory.value = detected;
                        if (els.categoryAutoHint) {
                            els.categoryAutoHint.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Auto-selected: ${detected}`;
                            els.categoryAutoHint.style.display = 'inline-block';
                        }
                    }
                }
            });

            els.prodCategory.addEventListener('change', () => {
                userManuallySelectedCategory = true;
                if (els.categoryAutoHint) els.categoryAutoHint.style.display = 'none';
            });
        }

        // Search & Category Filters
        if (els.searchInput) {
            els.searchInput.addEventListener('input', (e) => {
                searchQuery = e.target.value.trim().toLowerCase();
                renderInventory();
            });
        }
        if (els.categoryFilter) {
            els.categoryFilter.addEventListener('change', (e) => {
                categoryFilter = e.target.value;
                renderInventory();
            });
        }

        // Close modal on overlay click
        if (els.productModal) {
            els.productModal.addEventListener('click', (e) => {
                if (e.target === els.productModal) closeProductModal();
            });
        }

        // Auto-refresh inventory & heat map in real time (every 4s)
        setInterval(fetchProducts, 4000);
    }

    // Fetch products from server
    async function fetchProducts() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/products');
            if (res.ok) {
                const data = await res.json();
                
                // Client-side sanitation: ensure Rice is never classified as Dairy in memory
                Products = data.map(p => {
                    let cat = p.category;
                    if (p.name && p.name.toLowerCase().includes('rice') && (!cat || cat.toLowerCase() === 'dairy')) {
                        cat = 'Grains';
                    } else if (!cat) {
                        cat = detectCategoryFromName(p.name);
                    }
                    return { ...p, category: cat };
                });

                // Do not redraw DOM if user is actively filling out the product modal
                const isModalOpen = els.productModal && els.productModal.classList.contains('active');
                if (!isModalOpen) {
                    renderInventory();
                    renderHeatMap();
                }
            }
        } catch (e) {
            console.error("Failed to fetch products:", e);
        }
    }

    // Render stock heat map
    function renderHeatMap() {
        if (!els.heatmap) return;

        els.heatmap.innerHTML = '';

        if (Products.length === 0) {
            els.heatmap.innerHTML = `
                <div style="grid-column: 1/-1; padding: 20px; text-align: center; color: var(--text-secondary);">
                    No shelving data. Populate catalog first.
                </div>
            `;
            return;
        }

        Products.forEach(p => {
            const cell = document.createElement('div');
            const stock = (typeof p.stock === 'number') ? p.stock : (parseInt(p.stock, 10) || 0);
            const meta = getCategoryMeta(p.category);

            let stockClass = 'stock-high';
            if (stock < 10) stockClass = 'stock-low';
            else if (stock < 30) stockClass = 'stock-medium';

            cell.className = `heatmap-cell ${stockClass} glass-panel`;
            cell.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
                    <span style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${p.name.split(' ')[0]}</span>
                    <i class="fa-solid ${meta.icon}" style="font-size:0.75rem; color:${meta.text}; opacity:0.8;"></i>
                </div>
                <strong style="margin-top: 4px; font-size:0.95rem;">Qty: ${stock}</strong>
                <span style="font-size:0.7rem; color:var(--text-secondary); margin-top:2px;">
                    <i class="fa-solid fa-map-pin" style="margin-right:3px;"></i>${p.shelf || 'Aisle A'}
                </span>
            `;

            // Clicking cell opens product details for quick restock
            cell.title = `Click to edit ${p.name} (${p.category}) on ${p.shelf}`;
            cell.addEventListener('click', () => {
                openEditModal(p.uid);
            });

            els.heatmap.appendChild(cell);
        });
    }

    // Render catalog items in UI
    function renderInventory() {
        if (!els.inventoryList) return;

        let filtered = Products;
        if (categoryFilter !== 'all') {
            filtered = filtered.filter(p => (p.category || 'Grocery').toLowerCase() === categoryFilter.toLowerCase());
        }

        if (searchQuery) {
            filtered = filtered.filter(p =>
                (p.name || '').toLowerCase().includes(searchQuery) ||
                (p.uid || '').toLowerCase().includes(searchQuery) ||
                (p.category || '').toLowerCase().includes(searchQuery) ||
                (p.shelf || '').toLowerCase().includes(searchQuery) ||
                (p.offer || '').toLowerCase().includes(searchQuery)
            );
        }

        if (els.countLabel) {
            els.countLabel.textContent = `Showing ${filtered.length} of ${Products.length} catalog items`;
        }

        els.inventoryList.innerHTML = '';

        if (filtered.length === 0) {
            els.inventoryList.innerHTML = `
                <div class="empty-state" style="padding:40px; text-align:center;">
                    <i class="fa-solid fa-boxes-stacked" style="font-size:2.5rem; opacity:0.3; margin-bottom:12px;"></i>
                    <p style="color:var(--text-secondary); font-size:0.95rem;">No products match the selected category or search term.</p>
                </div>
            `;
            return;
        }

        filtered.forEach(p => {
            const itemEl = document.createElement('div');
            itemEl.className = 'inventory-item';

            const stock = (typeof p.stock === 'number') ? p.stock : (parseInt(p.stock, 10) || 0);
            let stockColor = 'var(--accent-green)';
            let stockBadgeText = `${stock} in stock`;
            if (stock < 10) {
                stockColor = 'var(--accent-red)';
                stockBadgeText = `${stock} low stock`;
            } else if (stock < 30) {
                stockColor = '#f59e0b';
                stockBadgeText = `${stock} moderate`;
            }

            const catMeta = getCategoryMeta(p.category);
            const price = Number(p.price || 0);

            itemEl.innerHTML = `
                <div class="item-identity" style="flex: 2.5;">
                    <div class="tag-icon" style="color: ${catMeta.text}; background: ${catMeta.bg}; border: 1px solid ${catMeta.border};">
                        <i class="fa-solid ${catMeta.icon}"></i>
                    </div>
                    <div class="item-info">
                        <h4 style="margin: 0; font-size: 1.05rem; display: flex; align-items: center; gap: 8px;">
                            <span>${p.name}</span>
                        </h4>
                        <div style="display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; align-items: center;">
                            <span style="font-family: monospace; background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">
                                UID: ${p.uid}
                            </span>
                            <span style="background: ${catMeta.bg}; color: ${catMeta.text}; border: 1px solid ${catMeta.border}; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
                                <i class="fa-solid ${catMeta.icon}"></i> ${catMeta.label}
                            </span>
                            <span style="background: rgba(255, 255, 255, 0.05); border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; color: var(--text-secondary);">
                                <i class="fa-solid fa-map-pin" style="margin-right: 4px; color: var(--accent-cyan);"></i>${p.shelf || 'Aisle A - Shelf 1'}
                            </span>
                        </div>
                    </div>
                </div>
                <div style="flex: 1.1; text-align: left; font-size: 0.88rem;">
                    <span style="color: var(--text-secondary); font-size: 0.75rem; display: block;">Inventory</span>
                    <strong style="color: ${stockColor}; font-size: 0.95rem;">${stockBadgeText}</strong>
                </div>
                <div style="flex: 1.2; font-size: 0.85rem; color: #f59e0b;">
                    ${p.offer && p.offer !== 'No Active Offers' && p.offer !== 'Standard Price' ? `
                        <span style="background: rgba(245, 158, 11, 0.12); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(245, 158, 11, 0.3); display: inline-flex; align-items: center; gap: 4px;">
                            <i class="fa-solid fa-gift"></i> ${p.offer}
                        </span>
                    ` : '<span style="color: var(--text-secondary); font-size: 0.75rem;">Standard Price</span>'}
                </div>
                <div class="item-price" style="flex: 0.9; text-align: right;">
                    <div style="font-size: 0.72rem; color: var(--text-secondary); font-weight: normal;">Unit Price</div>
                    Rs.${price.toFixed(2)}
                </div>
                <div class="item-actions">
                    <button class="btn-icon edit-btn" data-uid="${p.uid}" title="Edit product"><i class="fa-solid fa-pen"></i></button>
                    <button class="btn-icon delete-btn" data-uid="${p.uid}" title="Delete product" style="color: var(--accent-red)"><i class="fa-solid fa-trash"></i></button>
                </div>
            `;
            els.inventoryList.appendChild(itemEl);
        });

        // Add button listeners
        document.querySelectorAll('.edit-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const uid = btn.getAttribute('data-uid');
                openEditModal(uid);
            });
        });

        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const uid = btn.getAttribute('data-uid');
                deleteProduct(uid);
            });
        });
    }

    // Open modal in Add Mode
    function openAddModal() {
        if (!els.productModal) return;
        userManuallySelectedCategory = false;
        els.modalTitle.textContent = "Add New Product";
        els.prodOriginalUid.value = "";
        els.prodUid.value = "";
        els.prodUid.readOnly = false;
        els.prodUid.classList.remove('readonly-input');
        els.prodName.value = "";
        els.prodPrice.value = "";
        els.prodStock.value = "25";
        els.prodCategory.value = "Grains";
        if (els.categoryAutoHint) els.categoryAutoHint.style.display = 'none';
        els.prodShelf.value = "Aisle A - Shelf 1";
        els.prodOffer.value = "";
        els.prodSubmitBtn.textContent = "Create Product";
        els.productModal.classList.add('active');
        setTimeout(() => els.prodUid.focus(), 100);
    }

    // Open modal in Edit Mode
    function openEditModal(uid) {
        if (!els.productModal) return;

        const product = Products.find(p => p.uid === uid);
        if (!product) return;

        userManuallySelectedCategory = false;
        els.modalTitle.textContent = "Edit Product";
        els.prodOriginalUid.value = product.uid;
        els.prodUid.value = product.uid;
        els.prodUid.readOnly = true;
        els.prodUid.classList.add('readonly-input');

        els.prodName.value = product.name;
        els.prodPrice.value = product.price;
        els.prodStock.value = product.stock !== undefined ? product.stock : 20;

        // Auto-correct Rice if previously set to Dairy, or detect appropriate category
        let categoryVal = product.category;
        if (product.name && product.name.toLowerCase().includes('rice') && (!categoryVal || categoryVal.toLowerCase() === 'dairy')) {
            categoryVal = 'Grains';
        } else if (!categoryVal) {
            categoryVal = detectCategoryFromName(product.name);
        }

        els.prodCategory.value = categoryVal;
        if (els.categoryAutoHint) {
            els.categoryAutoHint.innerHTML = `<i class="fa-solid fa-tag"></i> Current: ${categoryVal}`;
            els.categoryAutoHint.style.display = 'inline-block';
        }

        els.prodShelf.value = product.shelf || "";
        els.prodOffer.value = (product.offer && product.offer !== 'No Active Offers') ? product.offer : "";

        els.prodSubmitBtn.textContent = "Save Changes";
        els.productModal.classList.add('active');
        setTimeout(() => els.prodName.focus(), 100);
    }

    function closeProductModal() {
        if (els.productModal) els.productModal.classList.remove('active');
    }

    // Handle Form Submission (Add / Edit) with authenticated fetch
    async function handleFormSubmit(e) {
        e.preventDefault();

        const uid = els.prodUid.value.trim();
        const name = els.prodName.value.trim();
        const price = parseFloat(els.prodPrice.value);
        const stock = parseInt(els.prodStock.value, 10) || 0;
        let category = els.prodCategory.value;
        const shelf = els.prodShelf.value.trim() || "Aisle A - Shelf 1";
        const offer = els.prodOffer.value.trim() || "No Active Offers";

        // Double check: Never let Rice be saved as Dairy
        if (name.toLowerCase().includes('rice') && category.toLowerCase() === 'dairy') {
            category = 'Grains';
        }

        if (!uid || !name || isNaN(price)) {
            alert("Please fill RFID UID, Product Name, and valid Price.");
            return;
        }

        els.prodSubmitBtn.disabled = true;
        els.prodSubmitBtn.textContent = "Saving...";

        const payload = { uid, name, price, stock, category, shelf, offer };

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/products/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (res.ok && data.success) {
                closeProductModal();
                await fetchProducts();
                if (window.showToast) {
                    window.showToast("Catalog Saved", `Product "${name}" saved in category ${category}.`, "success");
                }
            } else {
                alert(data.message || "Failed to save product.");
            }
        } catch (err) {
            console.error("Form submit error:", err);
            alert("Network error while saving product.");
        } finally {
            els.prodSubmitBtn.disabled = false;
            els.prodSubmitBtn.textContent = "Save Product";
        }
    }

    // Handle Delete Request with authenticated fetch
    async function deleteProduct(uid) {
        const product = Products.find(p => p.uid === uid);
        if (!product) return;

        if (!confirm(`Are you sure you want to delete "${product.name}"?\nThis cannot be undone.`)) {
            return;
        }

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn(`/api/products/${encodeURIComponent(uid)}`, {
                method: 'DELETE'
            });
            const data = await res.json();
            if (res.ok && data.success) {
                await fetchProducts();
                if (window.showToast) {
                    window.showToast("Product Deleted", `Removed "${product.name}" from catalog.`, "info");
                }
            } else {
                alert(data.message || "Failed to delete product.");
            }
        } catch (err) {
            console.error("Delete error:", err);
            alert("Network error while deleting product.");
        }
    }

    initInventory();
});
