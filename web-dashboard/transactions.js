/**
 * Transaction History Logic
 */

let Transactions = [];

const els = {
    transactionsList: document.getElementById('transactions-list'),
    txSearch: document.getElementById('tx-search'),
    
    // Modal
    receiptModal: document.getElementById('receipt-modal'),
    receiptDate: document.getElementById('receipt-date'),
    receiptAmount: document.getElementById('receipt-amount'),
    receiptItemsContainer: document.getElementById('receipt-items-container'),
    modalCloseBtn: document.getElementById('modal-close-btn')
};

// Initialize
async function initTransactions() {
    await fetchTransactions();

    if (els.txSearch) els.txSearch.addEventListener('input', filterTransactions);
    if (els.modalCloseBtn) els.modalCloseBtn.addEventListener('click', closeReceiptModal);
    
    if (els.receiptModal) {
        els.receiptModal.addEventListener('click', (e) => {
            if (e.target === els.receiptModal) closeReceiptModal();
        });
    }
}

// Fetch logs
async function fetchTransactions() {
    try {
        const res = await fetch('/api/transactions');
        Transactions = await res.json();
        renderTransactions(Transactions);
    } catch (e) {
        console.error("Failed to fetch transactions:", e);
    }
}

// Render records table
function renderTransactions(list) {
    if (!els.transactionsList) return;

    els.transactionsList.innerHTML = '';

    if (list.length === 0) {
        els.transactionsList.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; color: var(--text-secondary); padding: 40px;">
                    <i class="fa-solid fa-receipt" style="font-size: 2rem; opacity: 0.3; display: block; margin-bottom: 12px;"></i>
                    No checkout transactions found.
                </td>
            </tr>
        `;
        return;
    }

    list.forEach((tx, idx) => {
        const d = new Date(tx.timestamp * 1000);
        const dateStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        // Count total quantities
        const items = Object.values(tx.items);
        const totalItemsCount = items.reduce((sum, item) => sum + item.quantity, 0);

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${dateStr}</td>
            <td>${totalItemsCount} item(s)</td>
            <td style="font-weight:600; color:var(--accent-green);">Rs.${tx.total.toFixed(2)}</td>
            <td style="text-align: right;">
                <button class="btn btn-outline view-receipt-btn" data-idx="${idx}"><i class="fa-solid fa-receipt"></i> View Receipt</button>
            </td>
        `;
        els.transactionsList.appendChild(row);
    });

    // Add button listeners
    document.querySelectorAll('.view-receipt-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = btn.getAttribute('data-idx');
            // Check if we are using the filtered list
            const currentList = els.txSearch.value.trim() ? getFilteredList() : Transactions;
            openReceiptModal(currentList[idx]);
        });
    });
}

// Get filtered transactions based on current search input
function getFilteredList() {
    const query = els.txSearch.value.toLowerCase().trim();
    if (!query) return Transactions;
    
    return Transactions.filter(tx => {
        const d = new Date(tx.timestamp * 1000);
        const dateStr = d.toLocaleDateString().toLowerCase() + ' ' + d.toLocaleTimeString().toLowerCase();
        const items = Object.values(tx.items);
        const matchItems = items.some(item => item.name.toLowerCase().includes(query));
        return dateStr.includes(query) || matchItems || tx.total.toString().includes(query);
    });
}

// Filter transaction listings
function filterTransactions() {
    renderTransactions(getFilteredList());
}

// Open Receipt details overlay
function openReceiptModal(tx) {
    if (!els.receiptModal) return;

    const d = new Date(tx.timestamp * 1000);
    els.receiptDate.textContent = d.toLocaleDateString() + ' · ' + d.toLocaleTimeString();
    els.receiptAmount.textContent = `Rs.${tx.total.toFixed(2)}`;

    const items = Object.values(tx.items);
    els.receiptItemsContainer.innerHTML = items.map(item => `
        <div class="receipt-item">
            <span>${item.name} × ${item.quantity}</span>
            <span>Rs.${item.subtotal.toFixed(2)}</span>
        </div>
    `).join('');

    els.receiptModal.classList.add('active');
}

function closeReceiptModal() {
    if (els.receiptModal) els.receiptModal.classList.remove('active');
}

document.addEventListener('DOMContentLoaded', initTransactions);
