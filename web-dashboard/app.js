/**
 * Smart Trolley App Logic - MongoDB Integrated
 */

// Global State
let State = {
    revenue: 0,
    scannedItems: 0,
    activeCarts: [],
    feed: [],
    lastProcessedUnknownUID: null
};

let Products = [];

// UI Elements
const els = {
    revenue: document.getElementById('stat-revenue'),
    trolleys: document.getElementById('stat-trolleys'),
    items: document.getElementById('stat-items'),
    feedContainer: document.getElementById('transaction-feed'),
    cartsContainer: document.getElementById('active-carts-container'),
    resetBtn: document.getElementById('reset-btn'),
    checkoutBtn: document.getElementById('checkout-btn'),
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
    regCancelBtn: document.getElementById('reg-cancel-btn')
};

// Application Initialize
async function initApp() {
    await fetchProducts();
    if (els.revenue) {
        await fetchDashboard();
        setInterval(fetchDashboard, 2000);

        if (els.resetBtn)      els.resetBtn.addEventListener('click', resetCart);
        if (els.checkoutBtn)   els.checkoutBtn.addEventListener('click', checkoutCart);
        if (els.modalCloseBtn) els.modalCloseBtn.addEventListener('click', closeReceiptModal);
        // Close modal on overlay click
        if (els.receiptModal)  els.receiptModal.addEventListener('click', (e) => {
            if (e.target === els.receiptModal) closeReceiptModal();
        });
        
        // Registration Events
        if (els.regForm) els.regForm.addEventListener('submit', handleRegistration);
        if (els.regCancelBtn) els.regCancelBtn.addEventListener('click', closeRegistrationModal);
    }
}

async function fetchProducts() {
    try {
        const res = await fetch('/api/products');
        Products = await res.json();
    } catch (e) {
        console.error("Failed to fetch products:", e);
    }
}

async function fetchDashboard() {
    try {
        const res = await fetch('/api/dashboard');
        const data = await res.json();
        State.revenue = data.revenue;
        State.scannedItems = data.scannedItems;
        State.activeCarts = data.activeCarts;
        State.feed = data.feed;
        
        // Check for Unknown Scans
        if (State.feed.length > 0) {
            const latestEvent = State.feed[0];
            const now = Date.now() / 1000;
            if (latestEvent.actionType === 'UNKNOWN_SCAN' && 
                (now - latestEvent.timestamp) < 5 && 
                State.lastProcessedUnknownUID !== latestEvent.uid) {
                State.lastProcessedUnknownUID = latestEvent.uid;
            }
        }

        updateStatsUI();
        renderCarts();
        renderFeed();
    } catch (e) {
        console.error("Failed to fetch dashboard:", e);
    }
}

// Update Dashboard Top Numbers
function updateStatsUI() {
    els.revenue.innerText = `Rs.${State.revenue.toFixed(2)}`;
    els.trolleys.innerText = State.activeCarts.length;
    els.items.innerText = State.scannedItems;
}

// Render Active Carts Array
function renderCarts() {
    if (!els.cartsContainer) return;

    if (State.activeCarts.length === 0) {
        els.cartsContainer.innerHTML = `<p style="color: var(--text-secondary)">No active trolleys.</p>`;
        return;
    }

    els.cartsContainer.innerHTML = State.activeCarts.map(cart => `
        <div class="active-cart">
            <div class="cart-info">
                <h4><div class="cart-status"></div> Trolley #${cart.id}</h4>
                <p>Items: ${cart.itemsContained} · ${cart.lastActive}</p>
            </div>
            <div class="cart-total">Rs.${cart.total.toFixed(2)}</div>
        </div>
    `).join('');
}

// Render the live feed from State.feed
function renderFeed() {
    if (!els.feedContainer) return;
    
    if (!State.feed || State.feed.length === 0) {
        if (!els.feedContainer.querySelector('.transaction-item')) {
            els.feedContainer.innerHTML = `<div class="empty-state">No recent activity</div>`;
        }
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
                <div class="transaction-item" style="opacity: 0.7;">
                    <div class="tx-icon tx-remove" style="background: #3b82f6; color: white;"><i class="fa-solid fa-question"></i></div>
                    <div class="tx-details">
                        <h4>Unknown Card Scanned</h4>
                        <span>UID: ${item.uid} · ${timeString}</span>
                    </div>
                    <div class="tx-amount">---</div>
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


// RESET CART - Discard all items without saving a transaction
async function resetCart() {
    if (!confirm('Are you sure you want to reset the cart? All items will be discarded.')) return;
    
    els.resetBtn.disabled = true;
    try {
        const res = await fetch('/api/reset', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            await fetchDashboard();
        }
    } catch (e) {
        console.error('Reset error:', e);
    } finally {
        els.resetBtn.disabled = false;
    }
}

// CHECKOUT — Save cart as transaction and show receipt modal
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

// Show receipt modal with total and item breakdown
function showReceiptModal(total, items) {
    if (!els.receiptModal) return;

    els.receiptAmount.textContent = `Rs.${parseFloat(total).toFixed(2)}`;

    // Build item breakdown table
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

// ── REGISTRATION LOGIC ──────────────────────────────────────────────────
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
            // Refetch products so the frontend knows about the new one
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

document.addEventListener('DOMContentLoaded', initApp);
