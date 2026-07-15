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
    if (!confirm('Are you sure you want to reset the cart? All items will be discarded.')) return;
    
    els.resetBtn.disabled = true;
    try {
        const res = await fetch('/api/reset', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            await fetchDashboard();
            triggerLcdFeedback("Cart Reset!", "Total: Rs.0.00");
            triggerBuzzerFeedback(2);
        }
    } catch (e) {
        console.error('Reset error:', e);
    } finally {
        els.resetBtn.disabled = false;
    }
}

// Checkout cart API call
async function checkoutCart() {
    const cart = State.activeCarts[0];
    if (!cart || cart.itemsContained === 0) {
        alert('Cart is empty. Scan items before checkout.');
        return;
    }

    if (!confirm(`Checkout Trolley #${cart.id}?\nTotal: Rs.${cart.total.toFixed(2)}`)) return;

    els.checkoutBtn.disabled = true;
    try {
        const res  = await fetch('/api/checkout', { method: 'POST' });
        const data = await res.json();

        if (data.success) {
            await fetchDashboard();
            showReceiptModal(data.total, data.items || {});
            
            // Simulator LCD feedback
            triggerLcdFeedback("Checked Out!", `Total: Rs.${parseFloat(data.total).toFixed(2)}`);
            triggerBuzzerFeedback(2);
        } else {
            alert(data.message || 'Checkout failed.');
        }
    } catch (e) {
        console.error('Checkout error:', e);
        alert('Network error during checkout.');
    } finally {
        els.checkoutBtn.disabled = false;
    }
}

// Open Receipt Dialog
function showReceiptModal(total, items) {
    if (!els.receiptModal) return;
    els.receiptAmount.textContent = `Rs.${parseFloat(total).toFixed(2)}`;

    const entries = Object.values(items);
    if (entries.length > 0) {
        els.receiptMeta.innerHTML = entries.map(item => `
            <div class="receipt-item">
                <span>${item.name} × ${item.quantity}</span>
                <span>Rs.${item.subtotal.toFixed(2)}</span>
            </div>
        `).join('');
    } else {
        els.receiptMeta.innerHTML = `<p style="color:var(--text-secondary);text-align:center">Receipt saved to transactions.</p>`;
    }

    els.receiptModal.classList.add('active');
}

function closeReceiptModal() {
    if (els.receiptModal) els.receiptModal.classList.remove('active');
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
            // Unregistered item scanned
            triggerLcdFeedback("Unknown Card!", "Check Dashboard");
            triggerBuzzerFeedback(3);
            await fetchDashboard();
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
        const res = await fetch('/api/checkout', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            triggerLcdFeedback("Checked Out!", `Total: Rs.${data.total.toFixed(2)}`);
            triggerBuzzerFeedback(2);
            await fetchDashboard();
            showReceiptModal(data.total, data.items || {});
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
