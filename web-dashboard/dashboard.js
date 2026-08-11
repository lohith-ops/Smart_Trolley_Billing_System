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

// DOM elements specific to Dashboard
const els = {
    revenue: document.getElementById('stat-revenue'),
    trolleys: document.getElementById('stat-trolleys'),
    items: document.getElementById('stat-items'),
    lowstock: document.getElementById('stat-lowstock'),
    offline: document.getElementById('stat-offline'),
    pending: document.getElementById('stat-pending'),
    feedContainer: document.getElementById('transaction-feed'),
    cartsContainer: document.getElementById('active-carts-container'),
    resetBtn: document.getElementById('reset-btn'),
    checkoutBtn: document.getElementById('checkout-btn'),
    
    // Receipt Modal
    receiptModal: document.getElementById('receipt-modal'),
    receiptAmount: document.getElementById('receipt-amount'),
    receiptMeta: document.getElementById('receipt-meta'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    
    // Registration Modal
    regModal: document.getElementById('register-modal'),
    regForm: document.getElementById('register-form'),
    regUid: document.getElementById('reg-uid'),
    regName: document.getElementById('reg-name'),
    regPrice: document.getElementById('reg-price'),
    regCancelBtn: document.getElementById('reg-cancel-btn'),

    // Simulator Elements
    simPanel: document.getElementById('sim-panel'),
    simToggleBtn: document.getElementById('sim-toggle-btn'),
    simCloseBtn: document.getElementById('sim-close-btn'),
    simProductSelect: document.getElementById('sim-product-select'),
    simCustomUid: document.getElementById('sim-custom-uid'),
    simModeOpts: document.querySelectorAll('.sim-mode-opt'),
    simScanBtn: document.getElementById('sim-scan-btn'),
    simResetBtn: document.getElementById('sim-reset-btn'),
    simCheckoutBtn: document.getElementById('sim-checkout-btn'),
    simLcdLine1: document.getElementById('sim-lcd-line1'),
    simLcdLine2: document.getElementById('sim-lcd-line2'),
    simBuzzerLed: document.getElementById('sim-buzzer-led')
};

// Initialize Dashboard
async function initDashboard() {
    await fetchProducts();
    await fetchDashboard();
    
    // Start dashboard polling
    setInterval(fetchDashboard, 2000);

    // Setup action button listeners
    if (els.resetBtn) els.resetBtn.addEventListener('click', resetCart);
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
            els.simPanel.classList.add('open');
        });
    }
    if (els.simCloseBtn) {
        els.simCloseBtn.addEventListener('click', () => {
            els.simPanel.classList.remove('open');
        });
    }

    // Simulator Scan mode switch
    els.simModeOpts.forEach(opt => {
        opt.addEventListener('click', async () => {
            const selectedMode = opt.getAttribute('data-mode');
            await setSimulatorMode(selectedMode);
        });
    });

    // Simulator Scanner scan triggers
    if (els.simScanBtn) els.simScanBtn.addEventListener('click', triggerSimulatorScan);
    if (els.simResetBtn) els.simResetBtn.addEventListener('click', triggerSimulatorReset);
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
    if (els.trolleys) els.trolleys.innerText = State.activeCarts.length;
    if (els.items) els.items.innerText = State.scannedItems;
    
    // Count low stock products (stock < 10)
    const lowStockCount = Products.filter(p => p.stock < 10).length;
    if (els.lowstock) els.lowstock.innerText = lowStockCount;
    
    // Offline devices (Arduino offline = 1, otherwise 0)
    const offlineCount = State.arduinoConnected ? 0 : 1;
    if (els.offline) els.offline.innerText = offlineCount;
    
    // Pending checkouts (active carts with items > 0)
    const pendingCount = State.activeCarts.filter(c => c.itemsContained > 0).length;
    if (els.pending) els.pending.innerText = pendingCount;
}

// Render active cart details AND its scanned items
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
        // Render items inside the cart
        const itemsList = Object.values(cart.items);
        let itemsHtml = '';
        
        if (itemsList.length > 0) {
            itemsHtml = `
                <div class="cart-items-detail">
                    ${itemsList.map(item => `
                        <div class="cart-detail-row">
                            <span><span class="qty">${item.quantity}x</span> ${item.name}</span>
                            <span>Rs.${item.subtotal.toFixed(2)}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            itemsHtml = `
                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 8px; font-style: italic; text-align: center;">
                    Cart is empty. Scan products.
                </div>
            `;
        }

        return `
            <div class="active-cart">
                <div class="cart-header-row">
                    <div class="cart-info">
                        <h4><div class="cart-status"></div> Trolley #${cart.id}</h4>
                        <p>${cart.itemsContained} items · ${cart.lastActive}</p>
                    </div>
                    <div class="cart-total">Rs.${cart.total.toFixed(2)}</div>
                </div>
                ${itemsHtml}
            </div>
        `;
    }).join('');
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
        
        if (item.actionType === 'ADD') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-add"><i class="fa-solid fa-plus"></i></div>
                    <div class="tx-details">
                        <h4>Added ${item.productName}</h4>
                        <span>Trolley #1 · ${timeString}</span>
                    </div>
                    <div class="tx-amount positive">+Rs.${item.productPrice.toFixed(2)}</div>
                </div>
            `;
        } else if (item.actionType === 'REMOVE') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-remove"><i class="fa-solid fa-minus"></i></div>
                    <div class="tx-details">
                        <h4>Removed ${item.productName}</h4>
                        <span>Trolley #1 · ${timeString}</span>
                    </div>
                    <div class="tx-amount negative">-Rs.${item.productPrice.toFixed(2)}</div>
                </div>
            `;
        } else if (item.actionType === 'CHECKOUT') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-checkout"><i class="fa-solid fa-check"></i></div>
                    <div class="tx-details">
                        <h4>Trolley Checked Out</h4>
                        <span>${timeString}</span>
                    </div>
                    <div class="tx-amount positive">Rs.${item.total.toFixed(2)}</div>
                </div>
            `;
        } else if (item.actionType === 'UNKNOWN_SCAN') {
            return `
                <div class="transaction-item" style="border-color: rgba(59, 130, 246, 0.3);">
                    <div class="tx-icon tx-remove" style="background: rgba(59, 130, 246, 0.15); color: #3b82f6;"><i class="fa-solid fa-question"></i></div>
                    <div class="tx-details">
                        <h4>Unknown Card Scanned</h4>
                        <span>UID: ${item.uid} · ${timeString}</span>
                    </div>
                    <div class="tx-amount" style="color: #3b82f6; font-size: 0.8rem;">Register needed</div>
                </div>
            `;
        } else if (item.actionType === 'RESET') {
            return `
                <div class="transaction-item">
                    <div class="tx-icon tx-reset"><i class="fa-solid fa-rotate-left"></i></div>
                    <div class="tx-details">
                        <h4>Cart Reset</h4>
                        <span>Trolley #1 · ${timeString}</span>
                    </div>
                    <div class="tx-amount negative">-Rs.${item.total.toFixed(2)}</div>
                </div>
            `;
        }
        return '';
    }).join('');
}

// Update simulator UI scan modes
function updateSimulatorModeUI() {
    els.simModeOpts.forEach(opt => {
        const optMode = opt.getAttribute('data-mode');
        if (optMode === State.currentMode) {
            opt.classList.add('active');
        } else {
            opt.classList.remove('active');
        }
    });
}

// Set scanner mode (ADD or REMOVE) via backend API
async function setSimulatorMode(mode) {
    try {
        const res = await fetch('/api/simulator/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
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

// Reset cart API call
async function resetCart() {
    if (els.resetBtn) els.resetBtn.disabled = true;
    try {
        const res = await fetch('/api/reset', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            await fetchDashboard();
            triggerLcdFeedback("Cart Reset!", "Total: Rs.0.00");
            triggerBuzzerFeedback(2);
            if (window.showToast) window.showToast("Cart Reset", "Active cart has been cleared.", "info");
        }
    } catch (e) {
        console.error('Reset error:', e);
    } finally {
        if (els.resetBtn) els.resetBtn.disabled = false;
    }
}

// Checkout cart API call
let currentBill = null;

// Checkout cart API call (Generate Bill)
async function checkoutCart() {
    const cart = State.activeCarts[0];
    if (!cart || cart.itemsContained === 0) {
        if (window.showToast) window.showToast("Cart Empty", "Scan items before generating a bill.", "warning");
        else alert('Cart is empty. Scan items before generating bill.');
        return;
    }

    if (els.checkoutBtn) els.checkoutBtn.disabled = true;
    try {
        const res  = await fetch('/api/cart/generate-bill', { method: 'POST' });
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
    try {
        const res = await fetch('/api/cart/cancel-bill', { method: 'POST' });
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
            btn.disabled = true;
            const origText = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;
            
            try {
                const res = await fetch('/api/cart/pay', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paymentMethod: method })
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
                uid: uid
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
    els.simResetBtn.disabled = true;
    try {
        const res = await fetch('/api/reset', { method: 'POST' });
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
    const cart = State.activeCarts[0];
    if (!cart || cart.itemsContained === 0) {
        triggerLcdFeedback("Cart is Empty!", "Scan items first");
        triggerBuzzerFeedback(3);
        return;
    }

    els.simCheckoutBtn.disabled = true;
    try {
        const res = await fetch('/api/cart/generate-bill', { method: 'POST' });
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

// Mock LCD character display writes
function triggerLcdFeedback(line1, line2 = "") {
    if (els.simLcdLine1 && els.simLcdLine2) {
        els.simLcdLine1.textContent = line1.padEnd(16).substring(0, 16);
        els.simLcdLine2.textContent = line2.padEnd(16).substring(0, 16);
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
