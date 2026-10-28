/**
 * Product Search & Finder Logic - Smart Trolley Billing System
 * Features:
 * - Dynamic category filtering (Grains, Dairy, Bakery, Produce, Beverages, Snacks, Grocery)
 * - Live real-time search across product name, category, shelving location, and RFID UID
 * - In-place editing of product details (Name, Price, Stock, Category, Shelf, Offers)
 * - Adding new products directly from Product Finder
 * - Integration with Store Directory navigation (direct aisle & item spotlighting)
 * - Integration with Member Hub wishlist
 * - Stock status color coding and offer display
 */

document.addEventListener('DOMContentLoaded', () => {
    let products = [];
    let activeFilter = 'all';
    let searchQuery = '';
    let isAddMode = false;
    let userManuallySelectedCategory = false;

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

    function getDefaultShelfForCategory(cat) {
        switch ((cat || '').toLowerCase()) {
            case 'grains': return 'Aisle A - Shelf 1';
            case 'bakery': return 'Aisle B - Shelf 1';
            case 'dairy': return 'Aisle C - Shelf 1';
            case 'produce': return 'Aisle D - Shelf 1';
            case 'beverages': return 'Aisle E - Shelf 1';
            case 'snacks': return 'Aisle F - Shelf 1';
            default: return 'Aisle A - Shelf 1';
        }
    }

    const els = {
        grid: document.getElementById('search-results-grid'),
        filterContainer: document.getElementById('prod-filter-container'),
        searchInput: document.getElementById('prod-search-input'),
        resultsBadge: document.getElementById('results-count-badge'),
        searchSummary: document.getElementById('prod-search-summary'),
        addBtn: document.getElementById('finder-add-product-btn'),

        // Modal Elements
        modal: document.getElementById('product-edit-modal'),
        form: document.getElementById('product-edit-form'),
        modalTitle: document.getElementById('modal-title'),
        modalSubTitle: document.getElementById('modal-sub-title'),
        modalIcon: document.getElementById('modal-icon-elem'),
        originalUid: document.getElementById('edit-prod-original-uid'),
        uidInput: document.getElementById('edit-prod-uid'),
        nameInput: document.getElementById('edit-prod-name'),
        priceInput: document.getElementById('edit-prod-price'),
        stockInput: document.getElementById('edit-prod-stock'),
        categoryInput: document.getElementById('edit-prod-category'),
        categoryHint: document.getElementById('edit-category-hint'),
        shelfInput: document.getElementById('edit-prod-shelf'),
        offerInput: document.getElementById('edit-prod-offer'),
        cancelBtn: document.getElementById('edit-prod-cancel-btn'),
        submitBtn: document.getElementById('edit-prod-submit-btn')
    };

    // Check URL parameters for pre-selected category or search query
    const urlParams = new URLSearchParams(window.location.search);
    const initialCategory = urlParams.get('category') || urlParams.get('filter');
    const initialQuery = urlParams.get('q') || urlParams.get('search');

    if (initialCategory) {
        activeFilter = initialCategory;
    }
    if (initialQuery && els.searchInput) {
        searchQuery = initialQuery.toLowerCase().trim();
        els.searchInput.value = initialQuery;
    }

    // ── Load Products from API ────────────────────────────────────────────────
    async function loadProducts() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/products');
            if (res.ok) {
                const data = await res.json();
                products = data.map(p => ({
                    ...p,
                    category: sanitizeCategory(p)
                }));
                syncActiveFilterButtons();
                renderResults();
            }
        } catch (e) {
            console.error("Failed to load catalog products:", e);
            if (els.resultsBadge) {
                els.resultsBadge.textContent = "Error loading products";
                els.resultsBadge.className = "trolley-status-badge offline";
            }
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

    // ── Render Products Grid ──────────────────────────────────────────────────
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
                (p.uid && p.uid.toLowerCase().includes(query)) ||
                (p.offer && p.offer.toLowerCase().includes(query))
            );
        }

        if (els.resultsBadge) {
            els.resultsBadge.textContent = `${filtered.length} item${filtered.length === 1 ? '' : 's'} found`;
            els.resultsBadge.className = filtered.length > 0 ? "trolley-status-badge active" : "trolley-status-badge idle";
        }

        els.grid.innerHTML = '';

        if (filtered.length === 0) {
            els.grid.innerHTML = `
                <div class="glass-panel" style="grid-column: 1/-1; padding: 48px 24px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-box-open" style="font-size: 2.8rem; color: var(--text-secondary); opacity: 0.3; margin-bottom: 14px; display: block;"></i>
                    <p style="font-size: 1.1rem; color: var(--text-primary); margin-bottom: 6px; font-weight: 600;">No products match your criteria</p>
                    <p style="font-size: 0.88rem; max-width: 450px; margin: 0 auto 16px;">
                        No items found in category "<strong>${activeFilter}</strong>"${searchQuery ? ` matching "<strong>${searchQuery}</strong>"` : ''}.
                    </p>
                    <button class="btn btn-outline" onclick="window.resetFinderFilters()" style="font-size: 0.85rem; padding: 6px 16px;">
                        <i class="fa-solid fa-rotate-left"></i> Reset Search & Filters
                    </button>
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

            const offerText = p.offer && p.offer !== 'No Active Offers' && p.offer !== 'Standard Price' ? p.offer : '';
            const priceVal = (typeof p.price === 'number') ? p.price : (parseFloat(p.price) || 0);
            const categoryName = p.category || 'Grocery';
            const catMeta = getCategoryMeta(categoryName);

            card.innerHTML = `
                <div class="trolley-details-header" style="align-items: flex-start;">
                    <div>
                        <strong style="font-size: 1.1rem; color: var(--text-primary); display: block; line-height: 1.3;">
                            ${p.name || 'Unnamed Product'}
                        </strong>
                        <span style="font-family: monospace; font-size: 0.72rem; color: var(--text-secondary); background: rgba(0,0,0,0.3); padding: 1px 6px; border-radius: 4px; margin-top: 4px; display: inline-block;">
                            UID: ${p.uid || 'N/A'}
                        </span>
                    </div>
                    <span class="trolley-status-badge ${stockClass}" style="white-space: nowrap;">${stockBadge}</span>
                </div>
                
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary); align-items: center;">
                    <span>Category</span>
                    <span style="background: ${catMeta.bg}; color: ${catMeta.text}; border: 1px solid ${catMeta.border}; border-radius: 6px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; display: inline-flex; align-items: center; gap: 5px;">
                        <i class="fa-solid ${catMeta.icon}"></i> ${catMeta.label}
                    </span>
                </div>

                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary); align-items: center;">
                    <span>Shelving Location</span>
                    <span class="trolley-stat-value" style="font-family: monospace; font-weight: 500;">
                        <i class="fa-solid fa-map-pin" style="margin-right: 4px; color: var(--accent-cyan);"></i>${p.shelf || 'Aisle A - Shelf 1'}
                    </span>
                </div>

                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: var(--text-secondary); align-items: center; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;">
                    <span>Unit Price</span>
                    <span style="font-size: 1.25rem; color: var(--accent-green); font-weight: 700;">Rs.${priceVal.toFixed(2)}</span>
                </div>

                ${offerText ? `
                <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 6px 10px; display: flex; align-items: center; gap: 8px; color: #f59e0b; font-size: 0.8rem; font-weight: 500;">
                    <i class="fa-solid fa-gift"></i>
                    <span>${offerText}</span>
                </div>` : ''}

                <div style="margin-top: 6px; display: flex; gap: 8px; flex-wrap: wrap;">
                    <a href="navigation.html?highlight=${encodeURIComponent(categoryName)}&product=${encodeURIComponent(p.name || '')}" 
                       class="btn btn-outline" 
                       style="flex: 1; min-width: 110px; text-align: center; font-size: 0.8rem; padding: 8px 0; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; gap: 6px;">
                        <i class="fa-solid fa-map-location-dot" style="color: var(--accent-cyan);"></i> Locate
                    </a>
                    <button class="btn btn-outline edit-product-btn" 
                            data-uid="${p.uid}" 
                            title="Edit Product Details" 
                            style="padding: 8px 12px; font-size: 0.8rem; color: var(--accent-cyan); border-color: rgba(6,182,212,0.4);">
                        <i class="fa-solid fa-pen-to-square"></i> Edit
                    </button>
                    <button class="btn btn-outline add-wishlist-btn" 
                            data-name="${p.name}" 
                            data-price="${priceVal}" 
                            data-cat="${categoryName}" 
                            data-shelf="${p.shelf || 'Aisle A'}" 
                            data-offer="${offerText || 'Standard Price'}" 
                            title="Add to Wishlist" 
                            style="padding: 8px 12px; font-size: 0.8rem; color: var(--accent-purple);">
                        <i class="fa-solid fa-heart"></i>
                    </button>
                </div>
            `;
            els.grid.appendChild(card);
        });

        // Add Edit handlers
        els.grid.querySelectorAll('.edit-product-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const uid = btn.getAttribute('data-uid');
                openEditModal(uid);
            });
        });

        // Add Wishlist handlers
        els.grid.querySelectorAll('.add-wishlist-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const name = btn.getAttribute('data-name');
                const price = parseFloat(btn.getAttribute('data-price')) || 0;
                const cat = btn.getAttribute('data-cat');
                const shelf = btn.getAttribute('data-shelf');
                const offer = btn.getAttribute('data-offer');
                addToGuestOrUserWishlist(name, price, cat, shelf, offer);
            });
        });
    }

    // ── Open Edit Modal ───────────────────────────────────────────────────────
    function openEditModal(uid) {
        if (!els.modal) return;
        const product = products.find(p => p.uid === uid);
        if (!product) return;

        isAddMode = false;
        userManuallySelectedCategory = false;

        if (els.modalTitle) els.modalTitle.textContent = "Edit Product Details";
        if (els.modalSubTitle) els.modalSubTitle.textContent = "Update price, stock, shelf location, category & promo";
        if (els.modalIcon) els.modalIcon.className = "fa-solid fa-pen-to-square";

        if (els.originalUid) els.originalUid.value = product.uid || '';
        if (els.uidInput) {
            els.uidInput.value = product.uid || '';
            els.uidInput.readOnly = true;
            els.uidInput.classList.add('readonly-input');
        }

        if (els.nameInput) els.nameInput.value = product.name || '';
        if (els.priceInput) els.priceInput.value = (product.price !== undefined) ? product.price : '';
        if (els.stockInput) els.stockInput.value = (product.stock !== undefined) ? product.stock : 25;

        let categoryVal = product.category;
        if (product.name && product.name.toLowerCase().includes('rice') && (!categoryVal || categoryVal.toLowerCase() === 'dairy')) {
            categoryVal = 'Grains';
        } else if (!categoryVal) {
            categoryVal = detectCategoryFromName(product.name);
        }

        if (els.categoryInput) els.categoryInput.value = categoryVal;
        if (els.categoryHint) {
            els.categoryHint.innerHTML = `<i class="fa-solid fa-tag"></i> Current: ${categoryVal}`;
            els.categoryHint.style.display = 'inline-block';
        }

        if (els.shelfInput) els.shelfInput.value = product.shelf || getDefaultShelfForCategory(categoryVal);
        if (els.offerInput) els.offerInput.value = (product.offer && product.offer !== 'No Active Offers' && product.offer !== 'Standard Price') ? product.offer : '';

        if (els.submitBtn) {
            els.submitBtn.innerHTML = '<i class="fa-solid fa-check" style="margin-right: 6px;"></i>Save Changes';
            els.submitBtn.disabled = false;
        }

        els.modal.classList.add('active');
        setTimeout(() => { if (els.nameInput) els.nameInput.focus(); }, 100);
    }

    // ── Open Add Modal ────────────────────────────────────────────────────────
    function openAddModal() {
        if (!els.modal) return;

        isAddMode = true;
        userManuallySelectedCategory = false;

        if (els.modalTitle) els.modalTitle.textContent = "Add New Product";
        if (els.modalSubTitle) els.modalSubTitle.textContent = "Register a new product with RFID UID, price & category";
        if (els.modalIcon) els.modalIcon.className = "fa-solid fa-plus";

        if (els.originalUid) els.originalUid.value = '';
        if (els.uidInput) {
            els.uidInput.value = '';
            els.uidInput.readOnly = false;
            els.uidInput.classList.remove('readonly-input');
        }

        if (els.nameInput) els.nameInput.value = '';
        if (els.priceInput) els.priceInput.value = '';
        if (els.stockInput) els.stockInput.value = '25';
        if (els.categoryInput) els.categoryInput.value = 'Grains';
        if (els.categoryHint) els.categoryHint.style.display = 'none';
        if (els.shelfInput) els.shelfInput.value = 'Aisle A - Shelf 1';
        if (els.offerInput) els.offerInput.value = '';

        if (els.submitBtn) {
            els.submitBtn.innerHTML = '<i class="fa-solid fa-plus" style="margin-right: 6px;"></i>Create Product';
            els.submitBtn.disabled = false;
        }

        els.modal.classList.add('active');
        setTimeout(() => { if (els.uidInput) els.uidInput.focus(); }, 100);
    }

    function closeModal() {
        if (els.modal) els.modal.classList.remove('active');
    }

    // ── Handle Form Submit ────────────────────────────────────────────────────
    async function handleEditFormSubmit(e) {
        e.preventDefault();

        const uid = (els.uidInput ? els.uidInput.value.trim() : '');
        const name = (els.nameInput ? els.nameInput.value.trim() : '');
        const price = parseFloat(els.priceInput ? els.priceInput.value : 0);
        const stock = parseInt(els.stockInput ? els.stockInput.value : 25, 10) || 0;
        let category = (els.categoryInput ? els.categoryInput.value : 'Grocery');
        const shelf = (els.shelfInput ? els.shelfInput.value.trim() : '') || getDefaultShelfForCategory(category);
        const offer = (els.offerInput ? els.offerInput.value.trim() : '') || 'No Active Offers';

        // Validation
        if (!uid) {
            alert("Please enter the RFID Card UID.");
            return;
        }
        if (!name || name.length < 2) {
            alert("Please enter a valid product name (at least 2 characters).");
            return;
        }
        if (isNaN(price) || price <= 0) {
            alert("Please enter a valid price greater than Rs. 0.00.");
            return;
        }

        // Auto-correct rice misclassification
        if (name.toLowerCase().includes('rice') && category.toLowerCase() === 'dairy') {
            category = 'Grains';
        }

        if (els.submitBtn) {
            els.submitBtn.disabled = true;
            els.submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="margin-right: 6px;"></i>Saving...';
        }

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/products/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    uid,
                    name,
                    price,
                    stock,
                    category,
                    shelf,
                    offer
                })
            });

            if (res.status === 401 || res.status === 403) {
                if (window.showToast) {
                    window.showToast("Permission Required", "Only Managers and Admins can update catalog products. Please sign in with staff credentials.", "warning");
                } else {
                    alert("Permission Required: Only Managers and Admins can update catalog products.");
                }
                if (els.submitBtn) {
                    els.submitBtn.disabled = false;
                    els.submitBtn.innerHTML = isAddMode
                        ? '<i class="fa-solid fa-plus" style="margin-right: 6px;"></i>Create Product'
                        : '<i class="fa-solid fa-check" style="margin-right: 6px;"></i>Save Changes';
                }
                return;
            }

            const data = await res.json();
            if (res.ok && data.success) {
                closeModal();
                if (window.showToast) {
                    window.showToast("Product Saved", `"${name}" details have been updated in central catalog.`, "success");
                } else {
                    alert(`Product "${name}" saved successfully.`);
                }
                await loadProducts();
            } else {
                alert(data.message || "Failed to save product.");
                if (els.submitBtn) {
                    els.submitBtn.disabled = false;
                    els.submitBtn.innerHTML = isAddMode
                        ? '<i class="fa-solid fa-plus" style="margin-right: 6px;"></i>Create Product'
                        : '<i class="fa-solid fa-check" style="margin-right: 6px;"></i>Save Changes';
                }
            }
        } catch (err) {
            console.error("Save product error:", err);
            alert("Error connecting to server. Please try again.");
            if (els.submitBtn) {
                els.submitBtn.disabled = false;
                els.submitBtn.innerHTML = isAddMode
                    ? '<i class="fa-solid fa-plus" style="margin-right: 6px;"></i>Create Product'
                    : '<i class="fa-solid fa-check" style="margin-right: 6px;"></i>Save Changes';
            }
        }
    }

    // ── Category Auto-Detection in Add Mode ───────────────────────────────────
    if (els.nameInput && els.categoryInput) {
        els.nameInput.addEventListener('input', () => {
            if (!isAddMode) return;
            const nameVal = els.nameInput.value.trim();
            if (!nameVal) {
                if (els.categoryHint) els.categoryHint.style.display = 'none';
                return;
            }
            if (!userManuallySelectedCategory) {
                const detected = detectCategoryFromName(nameVal);
                if (detected && els.categoryInput.value !== detected) {
                    els.categoryInput.value = detected;
                    if (els.shelfInput && (!els.shelfInput.value || els.shelfInput.value.startsWith('Aisle '))) {
                        els.shelfInput.value = getDefaultShelfForCategory(detected);
                    }
                    if (els.categoryHint) {
                        els.categoryHint.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Auto-selected: ${detected}`;
                        els.categoryHint.style.display = 'inline-block';
                    }
                }
            }
        });

        els.categoryInput.addEventListener('change', () => {
            userManuallySelectedCategory = true;
            if (isAddMode && els.shelfInput && (!els.shelfInput.value || els.shelfInput.value.startsWith('Aisle '))) {
                els.shelfInput.value = getDefaultShelfForCategory(els.categoryInput.value);
            }
            if (els.categoryHint) els.categoryHint.style.display = 'none';
        });
    }

    // ── Wishlist Helper ───────────────────────────────────────────────────────
    function addToGuestOrUserWishlist(name, price, category, shelf, offer) {
        try {
            const listKey = 'smart_trolley_guest_wishlist';
            let current = JSON.parse(localStorage.getItem(listKey)) || [];
            if (current.some(it => it.name.toLowerCase() === name.toLowerCase())) {
                if (window.showToast) window.showToast("Wishlist", `${name} is already in your wishlist.`, "info");
                else alert(`${name} is already in your wishlist.`);
                return;
            }
            current.push({ name, price, category, shelf, offer });
            localStorage.setItem(listKey, JSON.stringify(current));
            if (window.showToast) {
                window.showToast("Wishlist Added", `${name} added to your wishlist.`, "success");
            } else {
                alert(`Added ${name} to your wishlist.`);
            }
        } catch (e) {
            console.error("Wishlist error:", e);
        }
    }

    window.resetFinderFilters = function() {
        activeFilter = 'all';
        searchQuery = '';
        if (els.searchInput) els.searchInput.value = '';
        syncActiveFilterButtons();
        renderResults();
    };

    // ── Event Bindings ────────────────────────────────────────────────────────
    if (els.filterContainer) {
        els.filterContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn');
            if (!btn) return;
            activeFilter = btn.getAttribute('data-filter') || 'all';
            syncActiveFilterButtons();
            renderResults();
        });
    }

    if (els.searchInput) {
        els.searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value.toLowerCase().trim();
            renderResults();
        });
    }

    if (els.addBtn) {
        els.addBtn.addEventListener('click', openAddModal);
    }

    if (els.cancelBtn) {
        els.cancelBtn.addEventListener('click', closeModal);
    }

    if (els.form) {
        els.form.addEventListener('submit', handleEditFormSubmit);
    }

    // Close modal on click outside box or pressing Esc
    if (els.modal) {
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && els.modal.classList.contains('active')) {
                closeModal();
            }
        });
    }

    // Initial fetch
    loadProducts();
});
