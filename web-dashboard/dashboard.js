/**
 * Dashboard & Simulator Page Logic
 */

let State = {
    revenue: 0,
    scannedItems: 0,
    activeCarts: [],
    feed: [],
    currentMode: "ADD",
    lastProcessedUnknownUID: null
};

let Products = [];

// DOM elements — populated lazily inside initDashboard() via refreshEls()
const els = {};


// Refresh DOM elements lazily to guarantee DOM load readiness
function refreshEls() {
    els.revenue = document.getElementById('stat-revenue');
    els.trolleys = document.getElementById('stat-trolleys');
    els.items = document.getElementById('stat-items');
    els.lowstock = document.getElementById('stat-lowstock');
    els.offline = document.getElementById('stat-offline');
    els.pending = document.getElementById('stat-pending');
    els.feedContainer = document.getElementById('transaction-feed');
    els.cartsContainer = document.getElementById('active-carts-container');
    els.resetBtn = document.getElementById('reset-btn');
    els.mainResetBtn = document.getElementById('main-reset-btn');
    els.checkoutBtn = document.getElementById('checkout-btn');
    
    // Receipt Modal
    els.receiptModal = document.getElementById('receipt-modal');
    els.receiptAmount = document.getElementById('receipt-amount');
    els.receiptMeta = document.getElementById('receipt-meta');
    els.modalCloseBtn = document.getElementById('modal-close-btn');
    
    // Registration Modal
    els.regModal = document.getElementById('register-modal');
    els.regForm = document.getElementById('register-form');
    els.regUid = document.getElementById('reg-uid');
    els.regName = document.getElementById('reg-name');
    els.regPrice = document.getElementById('reg-price');
    els.regCancelBtn = document.getElementById('reg-cancel-btn');

    // Simulator Elements
    els.simPanel = document.getElementById('sim-panel');
    els.simToggleBtn = document.getElementById('sim-toggle-btn');
    els.simCloseBtn = document.getElementById('sim-close-btn');
    els.simTrolleySelect = document.getElementById('sim-trolley-select');
    els.simProductSelect = document.getElementById('sim-product-select');
    els.simCustomUid = document.getElementById('sim-custom-uid');
    els.simModeOpts = document.querySelectorAll('.sim-mode-opt');
    els.simScanBtn = document.getElementById('sim-scan-btn');
    els.simResetBtn = document.getElementById('sim-reset-btn');
    els.simCheckoutBtn = document.getElementById('sim-checkout-btn');
    els.simLcdLine1 = document.getElementById('sim-lcd-line1');
    els.simLcdLine2 = document.getElementById('sim-lcd-line2');
    els.simBuzzerLed = document.getElementById('sim-buzzer-led');
}

// Initialize Dashboard
async function initDashboard() {
    refreshEls();

    await fetchProducts();
    await fetchDashboard();
    
    // Start dashboard polling
    setInterval(fetchDashboard, 2000);

    // Setup reset button listeners
    if (els.resetBtn) els.resetBtn.addEventListener('click', resetCart);
    if (els.mainResetBtn) els.mainResetBtn.addEventListener('click', resetCart);
    if (els.simResetBtn) els.simResetBtn.addEventListener('click', resetCart);
    
    if (els.checkoutBtn) els.checkoutBtn.addEventListener('click', checkoutCart);
    if (els.modalCloseBtn) els.modalCloseBtn.addEventListener('click', closeReceiptModal);
    
    if (els.receiptModal) {
        els.receiptModal.addEventListener('click', (e) => {
            if (e.target === els.receiptModal) closeReceiptModal();
        });
    }

    // Registration Modal Events
    if (els.regForm) els.regForm.addEventListener('submit', handleRegistration);
    if (els.regCancelBtn) els.regCancelBtn.addEventListener('click', closeRegistrationModal);

    // Simulator Panel Toggle & Actions
    if (els.simToggleBtn) {
        els.simToggleBtn.addEventListener('click', () => {
            if (els.simPanel) els.simPanel.classList.add('open');
        });
    }
    if (els.simCloseBtn) {
        els.simCloseBtn.addEventListener('click', () => {
            if (els.simPanel) els.simPanel.classList.remove('open');
        });
    }

    // Bind ALL Scanner action mode toggle buttons on the page (top bar & simulator)
    document.querySelectorAll('.sim-mode-opt').forEach(opt => {
        opt.addEventListener('click', async () => {
            const selectedMode = opt.getAttribute('data-mode');
            await setSimulatorMode(selectedMode);
        });
    });

    // Simulator Scanner scan triggers
    if (els.simScanBtn) els.simScanBtn.addEventListener('click', triggerSimulatorScan);
    if (els.simCheckoutBtn) els.simCheckoutBtn.addEventListener('click', triggerSimulatorCheckout);
    
    // Setup Payment Modal Handlers
    setupPaymentModalListeners();
}

// Fetch products for simulator selector
async function fetchProducts() {
    try {
        const res = await fetch('/api/products');
        Products = await res.json();
        populateSimulatorProducts();
    } catch (e) {
        console.error("Failed to fetch products:", e);
    }
}

// Populate simulator select element
function populateSimulatorProducts() {
    if (!els.simProductSelect) return;
    els.simProductSelect.innerHTML = '<option value="">-- Choose Existing Product --</option>';
    Products.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.uid;
        opt.textContent = `${p.name} (Rs.${p.price.toFixed(2)})`;
        els.simProductSelect.appendChild(opt);
    });
}

// Fetch dashboard statistics
async function fetchDashboard() {
    try {
        const res = await fetch('/api/dashboard');
        const data = await res.json();
        
        State.revenue = data.revenue;
        State.scannedItems = data.scannedItems;
        State.activeCarts = data.activeCarts;
        State.feed = data.feed;
        State.currentMode = data.currentMode;
        State.arduinoConnected = data.arduinoConnected;
        State.trolleyCount = data.trolleyCount;
        State.onlineTrolleys = data.onlineTrolleys;

        // Check for Unknown Scans
        if (State.feed.length > 0) {
            const latestEvent = State.feed[0];
            const now = Date.now() / 1000;
            // If unknown scan happened within 15 seconds, and not already prompted
            if (latestEvent.actionType === 'UNKNOWN_SCAN' && 
                (now - latestEvent.timestamp) < 15 && 
                State.lastProcessedUnknownUID !== latestEvent.uid) {
                
                State.lastProcessedUnknownUID = latestEvent.uid;
                showRegistrationModal(latestEvent.uid);
            }
        }

        updateStatsUI();
        renderActiveCartAndItems();
        renderFeed();
        updateSimulatorModeUI();
    } catch (e) {
        console.error("Failed to fetch dashboard data:", e);
    }
}

// Update Top level statistics counters
function updateStatsUI() {
    if (els.revenue) els.revenue.innerText = `Rs.${State.revenue.toFixed(2)}`;
    if (els.trolleys) els.trolleys.innerText = State.trolleyCount || State.activeCarts.length;
    if (els.items) els.items.innerText = State.scannedItems;
    
    // Count low stock products (stock < 10)
    const lowStockCount = Products.filter(p => p.stock < 10).length;
    if (els.lowstock) els.lowstock.innerText = lowStockCount;
    
    // Offline devices
    const totalCount = State.trolleyCount || 3;
    const onlineCount = State.onlineTrolleys !== undefined ? State.onlineTrolleys : (State.arduinoConnected ? 1 : 0);
    const offlineCount = Math.max(0, totalCount - onlineCount);
    if (els.offline) els.offline.innerText = offlineCount;
    
    // Pending checkouts (active carts with items > 0)
    const pendingCount = State.activeCarts.filter(c => c.itemsContained > 0).length;
    if (els.pending) els.pending.innerText = pendingCount;
}

// Render active cart details AND its scanned items with interactive Add, Remove, and Delete controls
function renderActiveCartAndItems() {
    if (!els.cartsContainer) return;

    if (State.activeCarts.length === 0) {
        els.cartsContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-cart-shopping" style="opacity: 0.3;"></i>
                <p>No active trolleys on shop floor.</p>
            </div>
        `;
        return;
    }

    // Render carts details
    els.cartsContainer.innerHTML = State.activeCarts.map(cart => {
        const itemsEntries = Object.entries(cart.items || {});
        const trolleyId = cart.trolley_id || `TROLLEY-00${cart.id}`;
        let itemsHtml = '';
        
        if (itemsEntries.length > 0) {
            itemsHtml = `
                <div class="cart-items-detail" style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
                    ${itemsEntries.map(([uidKey, item]) => `
                        <div class="cart-detail-row" style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px;">
                            <div style="display: flex; flex-direction: column;">
                                <span style="font-weight: 600; font-size: 0.9rem; color: var(--text-primary);">${item.name}</span>
                                <span style="font-size: 0.75rem; color: var(--text-secondary);">Rs.${item.price.toFixed(2)} / unit</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <div style="display: flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 6px;">
                                    <button class="btn-qty-sub" data-uid="${uidKey}" data-trolley-id="${trolleyId}" title="Remove 1 item" style="background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); color: var(--accent-red); width: 26px; height: 26px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold;">-</button>
                                    <span style="font-weight: 700; min-width: 20px; text-align: center; color: #fff;">${item.quantity}</span>
                                    <button class="btn-qty-add" data-uid="${uidKey}" data-trolley-id="${trolleyId}" title="Add 1 item" style="background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.4); color: var(--accent-green); width: 26px; height: 26px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-weight: bold;">+</button>
                                </div>
                                <span style="font-weight: 700; color: var(--accent-green); font-size: 0.9rem; min-width: 65px; text-align: right;">Rs.${item.subtotal.toFixed(2)}</span>
                                <button class="btn-qty-del" data-uid="${uidKey}" data-trolley-id="${trolleyId}" title="Remove all of this product" style="background: none; border: none; color: var(--accent-red); cursor: pointer; padding: 4px; font-size: 0.9rem;"><i class="fa-solid fa-trash"></i></button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            itemsHtml = `
                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 12px; font-style: italic; text-align: center; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                    Cart is empty. Use Quick Add below or hardware buttons to scan items.
                </div>
            `;
        }

        const productOptions = Products.map(p => `<option value="${p.uid}">${p.name} — Rs.${p.price.toFixed(2)}</option>`).join('');

        return `
            <div class="active-cart" style="padding: 16px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; margin-bottom: 16px;">
                <div class="cart-header-row" style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="cart-info">
                        <h4 style="font-size: 1.05rem; font-weight: 600; display: flex; align-items: center; gap: 8px;"><div class="cart-status"></div> ${trolleyId}</h4>
                        <p style="font-size: 0.8rem; color: var(--text-secondary);">${cart.itemsContained} items · ${cart.lastActive}</p>
                    </div>
                    <div class="cart-total" style="font-size: 1.3rem; font-weight: 700; color: var(--accent-green);">Rs.${cart.total.toFixed(2)}</div>
                </div>

                ${itemsHtml}

                <div class="cart-quick-controls" data-trolley-id="${trolleyId}" style="margin-top: 14px; padding-top: 12px; border-top: 1px dashed rgba(255,255,255,0.1); display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                    <select class="form-input cart-quick-select" style="flex: 1; min-width: 180px; padding: 6px 10px; font-size: 0.85rem; background: rgba(0,0,0,0.4); color: #fff; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;">
                        <option value="">-- Choose Product to Add --</option>
                        ${productOptions}
                    </select>
                    <button class="btn btn-outline cart-quick-add-btn" data-trolley-id="${trolleyId}" style="padding: 6px 14px; font-size: 0.85rem; background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border-color: rgba(16, 185, 129, 0.4);">
                        <i class="fa-solid fa-plus" style="margin-right: 4px;"></i> Add Item
                    </button>
                    <button class="btn btn-outline cart-quick-rem-btn" data-trolley-id="${trolleyId}" style="padding: 6px 14px; font-size: 0.85rem; background: rgba(239, 68, 68, 0.15); color: var(--accent-red); border-color: rgba(239, 68, 68, 0.4);">
                        <i class="fa-solid fa-minus" style="margin-right: 4px;"></i> Remove
                    </button>
                </div>
            </div>
        `;
    }).join('');

    // Attach button listeners to generated controls
    bindCartControlListeners();
}

// Bind event listeners for cart item modification buttons
function bindCartControlListeners() {
    // Add 1 quantity button (+)
    document.querySelectorAll('.btn-qty-add').forEach(btn => {
        btn.addEventListener('click', () => {
            const uid = btn.getAttribute('data-uid');
            const trolleyId = btn.getAttribute('data-trolley-id');
            modifyCartItem(uid, 'ADD', trolleyId);
        });
    });

    // Sub 1 quantity button (-)
    document.querySelectorAll('.btn-qty-sub').forEach(btn => {
        btn.addEventListener('click', () => {
            const uid = btn.getAttribute('data-uid');
            const trolleyId = btn.getAttribute('data-trolley-id');
            modifyCartItem(uid, 'REMOVE', trolleyId);
        });
    });

    // Delete product button (trash icon)
    document.querySelectorAll('.btn-qty-del').forEach(btn => {
        btn.addEventListener('click', () => {
            const uid = btn.getAttribute('data-uid');
            const trolleyId = btn.getAttribute('data-trolley-id');
            modifyCartItem(uid, 'REMOVE_ALL', trolleyId);
        });
    });

    // Quick Add button
    document.querySelectorAll('.cart-quick-add-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const container = btn.closest('.cart-quick-controls');
            const select = container ? container.querySelector('.cart-quick-select') : null;
            const trolleyId = btn.getAttribute('data-trolley-id') || (container ? container.getAttribute('data-trolley-id') : 'TROLLEY-001');
            if (select && select.value) {
                modifyCartItem(select.value, 'ADD', trolleyId);
            } else {
                if (window.showToast) window.showToast("Select Product", "Please choose a product from the dropdown to add.", "warning");
                else alert("Please choose a product from the dropdown.");
            }
        });
    });

    // Quick Remove button
    document.querySelectorAll('.cart-quick-rem-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const container = btn.closest('.cart-quick-controls');
            const select = container ? container.querySelector('.cart-quick-select') : null;
            const trolleyId = btn.getAttribute('data-trolley-id') || (container ? container.getAttribute('data-trolley-id') : 'TROLLEY-001');
            if (select && select.value) {
                modifyCartItem(select.value, 'REMOVE', trolleyId);
            } else {
                if (window.showToast) window.showToast("Select Product", "Please choose a product from the dropdown to remove.", "warning");
                else alert("Please choose a product from the dropdown.");
            }
        });
    });
}

// Modify cart item handler (API call)
async function modifyCartItem(uid, action, trolleyId) {
    if (!uid) return;
    const targetTrolley = trolleyId || (els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001');
    try {
        const res = await fetch('/api/cart/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, uid, trolley_id: targetTrolley })
        });
        const data = await res.json();
        if (data.success) {
            await fetchDashboard();
            triggerLcdFeedback(
                `${action === 'ADD' ? '+' : '-'} ${data.product.name}`.substring(0, 16),
                `Total: Rs.${data.cart.total.toFixed(2)}`,
                3000
            );
            triggerBuzzerFeedback(1);
            if (window.showToast) {
                const actTitle = action === 'ADD' ? 'Item Added' : (action === 'REMOVE_ALL' ? 'Item Removed' : 'Item Decremented');
                window.showToast(actTitle, `${data.product.name} updated in ${targetTrolley}.`, "success");
            }
        } else {
            if (window.showToast) window.showToast("Action Blocked", data.message || "Could not modify cart.", "error");
            else alert(data.message || "Could not modify cart.");
        }
    } catch (err) {
        console.error("Cart item modification error:", err);
    }
}

// Render recent checkout feeds
function renderFeed() {
    if (!els.feedContainer) return;
    
    if (!State.feed || State.feed.length === 0) {
        els.feedContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-regular fa-clock"></i>
                <p>Waiting for scan activity...</p>
            </div>
        `;
        return;
    }

    els.feedContainer.innerHTML = State.feed.map(item => {
        const d = new Date(item.timestamp * 1000);
        const timeString = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const trolleyLabel = item.trolley_id ? item.trolley_id.replace('TROLLEY-00', 'Trolley #').replace('TROLLEY-', 'Trolley #') : 'Trolley #1';
        const priceStr = (typeof item.productPrice === 'number') ? item.productPrice.toFixed(2) : (item.productPrice ? Number(item.productPrice).toFixed(2) : '0.00');
        const totalStr = (typeof item.total === 'number') ? item.total.toFixed(2) : (item.total ? Number(item.total).toFixed(2) : '0.00');
        
        if (item.actionType === 'ADD') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-add"><i class="fa-solid fa-plus"></i></div>
                    <div class="tx-details">
                        <h4>Added ${item.productName || 'Product'}</h4>
                        <span>${trolleyLabel} · ${timeString}</span>
                    </div>
                    <div class="tx-amount positive">+Rs.${priceStr}</div>
                </div>
            `;
        } else if (item.actionType === 'REMOVE') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-remove"><i class="fa-solid fa-minus"></i></div>
                    <div class="tx-details">
                        <h4>Removed ${item.productName || 'Product'}</h4>
                        <span>${trolleyLabel} · ${timeString}</span>
                    </div>
                    <div class="tx-amount negative">-Rs.${priceStr}</div>
                </div>
            `;
        } else if (item.actionType === 'CHECKOUT' || item.actionType === 'BILL_PAID') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-checkout"><i class="fa-solid fa-check"></i></div>
                    <div class="tx-details">
                        <h4>${trolleyLabel} Checked Out</h4>
                        <span>${timeString}</span>
                    </div>
                    <div class="tx-amount positive">Rs.${totalStr}</div>
                </div>
            `;
        } else if (item.actionType === 'BILL_GENERATED') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon" style="background: rgba(234, 179, 8, 0.15); color: #eab308;"><i class="fa-solid fa-file-invoice-dollar"></i></div>
                    <div class="tx-details">
                        <h4>Bill Generated (${trolleyLabel})</h4>
                        <span>${timeString}</span>
                    </div>
                    <div class="tx-amount" style="color: #eab308;">Rs.${totalStr}</div>
                </div>
            `;
        } else if (item.actionType === 'BILL_CANCELLED') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-remove"><i class="fa-solid fa-ban"></i></div>
                    <div class="tx-details">
                        <h4>Bill Cancelled (${trolleyLabel})</h4>
                        <span>${timeString}</span>
                    </div>
                    <div class="tx-amount negative">Rs.${totalStr}</div>
                </div>
            `;
        } else if (item.actionType === 'OUT_OF_STOCK') {
            return `
                <div class="transaction-item" style="border-color: rgba(239, 68, 68, 0.3);">
                    <div class="tx-icon tx-remove" style="background: rgba(239, 68, 68, 0.15); color: #ef4444;"><i class="fa-solid fa-triangle-exclamation"></i></div>
                    <div class="tx-details">
                        <h4>Out of Stock: ${item.productName || 'Item'}</h4>
                        <span>${trolleyLabel} · ${timeString}</span>
                    </div>
                    <div class="tx-amount" style="color: #ef4444; font-size: 0.8rem;">Blocked</div>
                </div>
            `;
        } else if (item.actionType === 'UNKNOWN_SCAN') {
            return `
                <div class="transaction-item" style="border-color: rgba(59, 130, 246, 0.3);">
                    <div class="tx-icon tx-remove" style="background: rgba(59, 130, 246, 0.15); color: #3b82f6;"><i class="fa-solid fa-question"></i></div>
                    <div class="tx-details">
                        <h4>Unknown Card Scanned</h4>
                        <span>UID: ${item.uid} · ${trolleyLabel} · ${timeString}</span>
                    </div>
                    <div class="tx-amount" style="color: #3b82f6; font-size: 0.8rem;">Register needed</div>
                </div>
            `;
        } else if (item.actionType === 'RESET') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-reset"><i class="fa-solid fa-rotate-left"></i></div>
                    <div class="tx-details">
                        <h4>Cart Reset (${trolleyLabel})</h4>
                        <span>${timeString}</span>
                    </div>
                    <div class="tx-amount negative">-Rs.${totalStr}</div>
                </div>
            `;
        } else if (item.actionType === 'PRODUCT_REGISTERED') {
            return `
                <div class="transaction-item" style="border-color: rgba(16, 185, 129, 0.3);">
                    <div class="tx-icon tx-add" style="background: rgba(16, 185, 129, 0.15); color: #10b981;"><i class="fa-solid fa-box-open"></i></div>
                    <div class="tx-details">
                        <h4>Catalog: ${item.productName || 'New Item'}</h4>
                        <span>UID: ${item.uid || '-'} · ${timeString}</span>
                    </div>
                    <div class="tx-amount positive">Rs.${priceStr}</div>
                </div>
            `;
        }
        return '';
    }).join('');
}

// Update ALL mode toggle buttons on the page (top bar + simulator panel)
function updateSimulatorModeUI() {
    document.querySelectorAll('.sim-mode-opt').forEach(opt => {
        const optMode = opt.getAttribute('data-mode');
        if (optMode === State.currentMode) {
            opt.classList.add('active');
            opt.style.background = 'linear-gradient(135deg, var(--accent-cyan, #22d3ee), #6366f1)';
            opt.style.color = '#fff';
            opt.style.boxShadow = '0 0 12px rgba(34,211,238,0.35)';
        } else {
            opt.classList.remove('active');
            opt.style.background = 'transparent';
            opt.style.color = 'var(--text-secondary, #94a3b8)';
            opt.style.boxShadow = 'none';
        }
    });

    if (typeof lcdTimeout === 'undefined' || !lcdTimeout) {
        triggerLcdFeedback(`Mode: ${State.currentMode}`, "Scan card...");
    }
}

// Set scanner mode (ADD or REMOVE) via backend API
async function setSimulatorMode(mode) {
    const targetTrolley = els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001';
    try {
        const res = await fetch('/api/simulator/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode, trolley_id: targetTrolley })
        });
        const data = await res.json();
        if (data.success) {
            State.currentMode = data.mode;
            updateSimulatorModeUI();
            
            // Sim LCD feedback
            triggerLcdFeedback(`Mode: ${data.mode}`, "Scan card...");
            triggerBuzzerFeedback(1);
        }
    } catch (e) {
        console.error("Failed to update simulator mode:", e);
    }
}

// Reset cart API call — clears all active cart items
async function resetCart(trolleyId) {
    const targetTrolley = (typeof trolleyId === 'string' && trolleyId) ? trolleyId : (els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001');
    if (!confirm(`Reset the cart for ${targetTrolley}? All scanned items will be removed.`)) return;

    // Disable ALL reset buttons during the request
    const allResetBtns = document.querySelectorAll('#reset-btn, #main-reset-btn, #sim-reset-btn');
    allResetBtns.forEach(b => { b.disabled = true; b.style.opacity = '0.5'; });

    try {
        const res = await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trolley_id: targetTrolley })
        });
        const data = await res.json();
        if (data.success) {
            await fetchDashboard();
            triggerLcdFeedback("Cart Reset!", "Total: Rs.0.00", 3000);
            triggerBuzzerFeedback(2);
            if (window.showToast) window.showToast("Cart Reset", `All items cleared from ${targetTrolley}.`, "info");
        } else {
            if (window.showToast) window.showToast("Reset Failed", data.message || "Could not reset cart.", "error");
        }
    } catch (e) {
        console.error('Reset error:', e);
        if (window.showToast) window.showToast("Network Error", "Could not connect to server.", "error");
    } finally {
        // Re-enable all reset buttons
        allResetBtns.forEach(b => { b.disabled = false; b.style.opacity = ''; });
    }
}

// Checkout cart API call
let currentBill = null;

// Checkout cart API call (Generate Bill)
async function checkoutCart(trolleyId) {
    const targetTrolley = (typeof trolleyId === 'string' && trolleyId) ? trolleyId : (els.simTrolleySelect ? els.simTrolleySelect.value : (State.activeCarts[0]?.trolley_id || 'TROLLEY-001'));
    const cart = State.activeCarts.find(c => (c.trolley_id === targetTrolley || c.id === targetTrolley || `TROLLEY-00${c.id}` === targetTrolley)) || State.activeCarts[0];
    if (!cart || cart.itemsContained === 0) {
        if (window.showToast) window.showToast("Cart Empty", "Scan items before generating a bill.", "warning");
        else alert('Cart is empty. Scan items before generating bill.');
        return;
    }

    if (els.checkoutBtn) els.checkoutBtn.disabled = true;
    try {
        const res  = await fetch('/api/cart/generate-bill', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trolley_id: cart.trolley_id || targetTrolley })
        });
        const data = await res.json();

        if (data.success) {
            await fetchDashboard();
            showBillingModal(data);
        } else {
            if (window.showToast) window.showToast("Error", data.message || 'Failed to generate bill.', "error");
            else alert(data.message || 'Failed to generate bill.');
        }
    } catch (e) {
        console.error('Bill generation error:', e);
        if (window.showToast) window.showToast("Network Error", "Failed to generate bill. Check connection.", "error");
        else alert('Network error during bill generation.');
    } finally {
        if (els.checkoutBtn) els.checkoutBtn.disabled = false;
    }
}

// Show multi-stage billing modal
function showBillingModal(billData) {
    currentBill = billData;
    
    // Reset stages
    document.querySelectorAll('.payment-stage').forEach(el => el.style.display = 'none');
    const stage1 = document.getElementById('payment-stage-1');
    if (stage1) stage1.style.display = 'block';
    
    // Reset payment tabs
    const tabs = document.querySelectorAll('.pay-tab');
    tabs.forEach((t, i) => {
        t.classList.remove('active');
        t.style.background = 'none';
        t.style.color = 'var(--text-secondary)';
        if (i === 0) {
            t.classList.add('active');
            t.style.background = 'rgba(255,255,255,0.08)';
            t.style.color = 'var(--text-primary)';
        }
    });
    document.querySelectorAll('.pay-panel').forEach(p => p.style.display = 'none');
    const upiPanel = document.getElementById('pay-panel-upi');
    if (upiPanel) upiPanel.style.display = 'block';

    // Populate Stage 1 Breakdown
    const itemsListContainer = document.getElementById('billing-items-list');
    if (itemsListContainer) {
        const entries = Object.values(billData.items);
        if (entries.length > 0) {
            itemsListContainer.innerHTML = entries.map(item => `
                <div style="display:flex; justify-content:space-between; font-size:0.9rem; border-bottom:1px solid rgba(255,255,255,0.03); padding-bottom:4px; width:100%;">
                    <span>${item.name} × ${item.quantity}</span>
                    <span style="font-weight:600;">Rs.${item.subtotal.toFixed(2)}</span>
                </div>
            `).join('');
        } else {
            itemsListContainer.innerHTML = `<p style="color:var(--text-secondary); text-align:center; font-size:0.85rem; margin:0;">No items found.</p>`;
        }
    }
    
    const subtotalEl = document.getElementById('bill-subtotal');
    const cgstEl = document.getElementById('bill-cgst');
    const sgstEl = document.getElementById('bill-sgst');
    const totalEl = document.getElementById('bill-total');
    
    if (subtotalEl) subtotalEl.textContent = `Rs.${billData.subtotal.toFixed(2)}`;
    if (cgstEl) cgstEl.textContent = `Rs.${billData.cgst.toFixed(2)}`;
    if (sgstEl) sgstEl.textContent = `Rs.${billData.sgst.toFixed(2)}`;
    if (totalEl) totalEl.textContent = `Rs.${billData.total.toFixed(2)}`;
    
    // Show Modal
    if (els.receiptModal) els.receiptModal.classList.add('active');
}

// Cancel bill & release cart
async function cancelBill() {
    const targetTrolley = (currentBill && currentBill.trolley_id) ? currentBill.trolley_id : (els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001');
    try {
        const res = await fetch('/api/cart/cancel-bill', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trolley_id: targetTrolley })
        });
        const data = await res.json();
        if (data.success) {
            if (els.receiptModal) els.receiptModal.classList.remove('active');
            await fetchDashboard();
            triggerLcdFeedback("Bill Cancelled", `Total: Rs.${data.total.toFixed(2)}`);
            triggerBuzzerFeedback(1);
            if (window.showToast) window.showToast("Bill Cancelled", "Returned to scanning mode.", "info");
        } else {
            if (window.showToast) window.showToast("Error", data.message || 'Failed to cancel bill.', "error");
            else alert(data.message || 'Failed to cancel bill.');
        }
    } catch (err) {
        console.error('Cancel bill error:', err);
    }
}

function closeReceiptModal() {
    const stage3 = document.getElementById('payment-stage-3');
    if (stage3 && stage3.style.display === 'block') {
        if (els.receiptModal) els.receiptModal.classList.remove('active');
    } else {
        cancelBill();
    }
}

// Bind modal listeners
function setupPaymentModalListeners() {
    // Stage 1 -> Stage 2
    const proceedBtn = document.getElementById('btn-proceed-to-payment');
    if (proceedBtn) {
        proceedBtn.addEventListener('click', () => {
            document.querySelectorAll('.payment-stage').forEach(el => el.style.display = 'none');
            const stage2 = document.getElementById('payment-stage-2');
            if (stage2) stage2.style.display = 'block';
            
            const upiQrImg = document.getElementById('payment-upi-qr');
            if (upiQrImg && currentBill) {
                const totalAmount = currentBill.total.toFixed(2);
                const upiString = `upi://pay?pa=smartsupermarket@okaxis&pn=SmartSupermarket&am=${totalAmount}&cu=INR&tn=SmartTrolleySettle`;
                upiQrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(upiString)}`;
            }
        });
    }

    // Stage 2 -> Stage 1
    const backBtn = document.getElementById('btn-back-to-invoice');
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            document.querySelectorAll('.payment-stage').forEach(el => el.style.display = 'none');
            const stage1 = document.getElementById('payment-stage-1');
            if (stage1) stage1.style.display = 'block';
        });
    }

    // Cancel buttons
    document.querySelectorAll('.btn-cancel-bill').forEach(btn => {
        btn.addEventListener('click', cancelBill);
    });
    
    const closeXBtn = document.getElementById('modal-close-x-btn');
    if (closeXBtn) {
        closeXBtn.addEventListener('click', cancelBill);
    }

    // Tabs switching
    const tabs = document.querySelectorAll('.pay-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => {
                t.classList.remove('active');
                t.style.background = 'none';
                t.style.color = 'var(--text-secondary)';
            });
            tab.classList.add('active');
            tab.style.background = 'rgba(255,255,255,0.08)';
            tab.style.color = 'var(--text-primary)';
            
            const target = tab.dataset.tab;
            document.querySelectorAll('.pay-panel').forEach(p => p.style.display = 'none');
            const activePanel = document.getElementById(`pay-panel-${target}`);
            if (activePanel) activePanel.style.display = 'block';
        });
    });

    // Simulated payments success
    document.querySelectorAll('.btn-pay-success').forEach(btn => {
        btn.addEventListener('click', async () => {
            const method = btn.dataset.method;
            const targetTrolley = (currentBill && currentBill.trolley_id) ? currentBill.trolley_id : (els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001');
            btn.disabled = true;
            const origText = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;
            
            try {
                const res = await fetch('/api/cart/pay', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paymentMethod: method, trolley_id: targetTrolley })
                });
                const data = await res.json();
                if (data.success) {
                    document.querySelectorAll('.payment-stage').forEach(el => el.style.display = 'none');
                    const stage3 = document.getElementById('payment-stage-3');
                    if (stage3) stage3.style.display = 'block';
                    
                    const successAmount = document.getElementById('success-billed-amount');
                    const successMethod = document.getElementById('success-payment-method');
                    if (successAmount) successAmount.textContent = `Rs.${data.total.toFixed(2)}`;
                    if (successMethod) successMethod.textContent = `Paid via ${method}`;
                    
                    const receiptLink = document.getElementById('modal-receipt-link');
                    if (receiptLink) {
                        receiptLink.href = `receipt.html?timestamp=${data.timestamp}`;
                    }
                    
                    triggerLcdFeedback("Checked Out!", "Total: Rs.0.00");
                    triggerBuzzerFeedback(2);
                    await fetchDashboard();
                } else {
                    alert(data.message || 'Payment failed.');
                }
            } catch (err) {
                console.error('Payment error:', err);
                alert('Network error while processing payment.');
            } finally {
                btn.disabled = false;
                btn.innerHTML = origText;
            }
        });
    });
}

// Open Product Register Modal
function showRegistrationModal(uid) {
    if (!els.regModal) return;
    els.regUid.value = uid;
    els.regName.value = '';
    els.regPrice.value = '';
    els.regModal.classList.add('active');
    setTimeout(() => els.regName.focus(), 100);
}

function closeRegistrationModal() {
    if (els.regModal) els.regModal.classList.remove('active');
}

// Submit Product registration form
async function handleRegistration(e) {
    e.preventDefault();
    
    const submitBtn = els.regForm.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerText = "Saving...";
    
    const payload = {
        uid: els.regUid.value,
        name: els.regName.value,
        price: parseFloat(els.regPrice.value)
    };
    
    try {
        const res = await fetch('/api/products/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (data.success) {
            closeRegistrationModal();
            triggerLcdFeedback("Registered!", payload.name.substring(0,16));
            triggerBuzzerFeedback(1);
            await fetchProducts();
            await fetchDashboard();
        } else {
            alert(data.message || 'Failed to register product');
        }
    } catch (err) {
        console.error('Registration Error:', err);
        alert('Network error while registering product');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = "Save Product";
    }
}

// ── SIMULATOR FUNCTIONS (Digital Twin) ───────────────────────────────────

// Trigger simulated RFID card scan
async function triggerSimulatorScan() {
    const selectedUid = els.simProductSelect.value;
    const customUid = els.simCustomUid.value.trim();
    const uid = customUid || selectedUid;
    const targetTrolley = els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001';

    if (!uid) {
        alert("Please select a product or enter a custom RFID tag UID.");
        return;
    }

    els.simScanBtn.disabled = true;
    
    try {
        const res = await fetch('/api/cart/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: State.currentMode,
                uid: uid,
                trolley_id: targetTrolley
            })
        });
        
        const data = await res.json();
        if (data.success) {
            const actionSymbol = State.currentMode === "ADD" ? "+" : "-";
            triggerLcdFeedback(
                `${actionSymbol} ${data.product.name}`.substring(0, 16),
                `Total: Rs.${data.cart.total.toFixed(2)}`
            );
            triggerBuzzerFeedback(1);
            els.simCustomUid.value = ''; // clear custom uid
            await fetchDashboard();
        } else {
            if (res.status === 400 && data.message && data.message.includes("locked")) {
                alert(data.message);
                triggerLcdFeedback("Cart Locked!", "Pay or Cancel");
                triggerBuzzerFeedback(3);
            } else {
                // Unregistered item scanned
                triggerLcdFeedback("Unknown Card!", "Check Dashboard");
                triggerBuzzerFeedback(3);
                await fetchDashboard();
            }
        }
    } catch (e) {
        console.error("Simulation scan error:", e);
        triggerLcdFeedback("Scan Error", "Check connection");
    } finally {
        els.simScanBtn.disabled = false;
    }
}

// Trigger simulated physical reset button press
async function triggerSimulatorReset() {
    const targetTrolley = els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001';
    els.simResetBtn.disabled = true;
    try {
        const res = await fetch('/api/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trolley_id: targetTrolley })
        });
        const data = await res.json();
        if (data.success) {
            triggerLcdFeedback("Cart Reset!", "Total: Rs.0.00");
            triggerBuzzerFeedback(2);
            await fetchDashboard();
        }
    } catch (e) {
        console.error("Simulation reset error:", e);
    } finally {
        els.simResetBtn.disabled = false;
    }
}

// Trigger simulated checkout process
async function triggerSimulatorCheckout() {
    const targetTrolley = els.simTrolleySelect ? els.simTrolleySelect.value : 'TROLLEY-001';
    const cart = State.activeCarts.find(c => (c.trolley_id === targetTrolley || c.id === targetTrolley || `TROLLEY-00${c.id}` === targetTrolley)) || State.activeCarts[0];
    if (!cart || cart.itemsContained === 0) {
        triggerLcdFeedback("Cart is Empty!", "Scan items first");
        triggerBuzzerFeedback(3);
        return;
    }

    els.simCheckoutBtn.disabled = true;
    try {
        const res = await fetch('/api/cart/generate-bill', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trolley_id: cart.trolley_id || targetTrolley })
        });
        const data = await res.json();
        if (data.success) {
            triggerLcdFeedback("Bill Generated", `Total: Rs.${data.total.toFixed(2)}`);
            triggerBuzzerFeedback(1);
            await fetchDashboard();
            showBillingModal(data);
        } else {
            alert(data.message || 'Failed to generate bill.');
        }
    } catch (e) {
        console.error("Simulation checkout error:", e);
    } finally {
        els.simCheckoutBtn.disabled = false;
    }
}

let lcdTimeout = null;

// Mock LCD character display writes with timer support
function triggerLcdFeedback(line1, line2 = "", durationMs = 0) {
    if (lcdTimeout) {
        clearTimeout(lcdTimeout);
        lcdTimeout = null;
    }
    
    if (els.simLcdLine1) {
        els.simLcdLine1.textContent = line1.substring(0, 16);
    }
    if (els.simLcdLine2) {
        els.simLcdLine2.textContent = line2.substring(0, 16);
    }

    if (durationMs > 0) {
        lcdTimeout = setTimeout(() => {
            if (els.simLcdLine1) {
                els.simLcdLine1.textContent = `Mode: ${State.currentMode}`;
            }
            if (els.simLcdLine2) {
                els.simLcdLine2.textContent = "Scan card...";
            }
            lcdTimeout = null;
        }, durationMs);
    }
}

// Mock Buzzer click sounds/flashes
function triggerBuzzerFeedback(count) {
    if (!els.simBuzzerLed) return;
    
    let delay = 0;
    for (let i = 0; i < count; i++) {
        setTimeout(() => {
            els.simBuzzerLed.classList.add('beep');
            // Mock sound (short beep)
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = audioCtx.createOscillator();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(2000, audioCtx.currentTime); // 2000Hz frequency
                osc.connect(audioCtx.destination);
                osc.start();
                setTimeout(() => osc.stop(), 100);
            } catch(e) {}
            
            setTimeout(() => {
                els.simBuzzerLed.classList.remove('beep');
            }, 100);
        }, delay);
        delay += 200;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});
