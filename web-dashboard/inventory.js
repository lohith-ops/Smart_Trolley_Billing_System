/**
 * Inventory Management & Heat Map Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let Products = [];

    const els = {
        inventoryList: document.getElementById('inventory-list'),
        addProductBtn: document.getElementById('add-product-btn'),
        heatmap: document.getElementById('stock-heatmap'),
        
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

    // Close modal on overlay click
    if (els.productModal) {
        els.productModal.addEventListener('click', (e) => {
            if (e.target === els.productModal) closeProductModal();
        });
    }
}

// Fetch products from server
async function fetchProducts() {
    try {
        const res = await fetch('/api/products');
        Products = await res.json();
        renderInventory();
        renderHeatMap();
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
        const stock = p.stock || 0;
        
        let stockClass = 'stock-high';
        if (stock < 10) stockClass = 'stock-low';
        else if (stock < 30) stockClass = 'stock-medium';
        
        cell.className = `heatmap-cell ${stockClass} glass-panel`;
        cell.innerHTML = `
            <div>${p.name.split(' ')[0]}</div>
            <strong style="margin-top: 2px;">Qty: ${stock}</strong>
            <span>${p.shelf || 'Aisle A'}</span>
        `;
        
        // Clicking cell opens product details for quick restock
        cell.addEventListener('click', () => {
            openEditModal(p.uid);
        });
        
        els.heatmap.appendChild(cell);
    });
}

// Render catalog items in UI
function renderInventory() {
    if (!els.inventoryList) return;
    
    els.inventoryList.innerHTML = '';
    
    if (Products.length === 0) {
        els.inventoryList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-boxes-stacked" style="opacity: 0.3;"></i>
                <p>No products in inventory. Click "Add Product" to create one.</p>
            </div>
        `;
        return;
    }

    Products.forEach(p => {
        const itemEl = document.createElement('div');
        itemEl.className = 'inventory-item';
        
        const stock = p.stock || 0;
        let stockColor = 'var(--accent-green)';
        if (stock < 10) stockColor = 'var(--accent-red)';
        else if (stock < 30) stockColor = '#f59e0b';

        itemEl.innerHTML = `
            <div class="item-identity" style="flex: 2.5;">
                <div class="tag-icon"><i class="fa-solid fa-tag"></i></div>
                <div class="item-info">
                    <h4>${p.name}</h4>
                    <div style="display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap;">
                        <span>UID: ${p.uid}</span>
                        <span style="background: rgba(192, 132, 252, 0.15); color: var(--accent-purple); border-radius: 4px;">${p.category || 'Grocery'}</span>
                        <span style="background: rgba(0, 0, 0, 0.3); border-radius: 4px;"><i class="fa-solid fa-map-pin" style="margin-right: 4px;"></i>${p.shelf || 'Aisle A'}</span>
                    </div>
                </div>
            </div>
            <div style="flex: 1; text-align: left; font-size: 0.9rem;">
                Stock: <strong style="color: ${stockColor}">${stock} units</strong>
            </div>
            <div style="flex: 1; font-size: 0.85rem; color: #f59e0b;">
                ${p.offer !== 'No Active Offers' && p.offer ? `<i class="fa-solid fa-gift" style="margin-right: 4px;"></i>${p.offer}` : ''}
            </div>
            <div class="item-price" style="flex: 0.8;">Rs.${p.price.toFixed(2)}</div>
            <div class="item-actions">
                <button class="btn-icon edit-btn" data-uid="${p.uid}"><i class="fa-solid fa-pen"></i></button>
                <button class="btn-icon delete-btn" data-uid="${p.uid}" style="color: var(--accent-red)"><i class="fa-solid fa-trash"></i></button>
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
    els.modalTitle.textContent = "Add New Product";
    els.prodOriginalUid.value = "";
    els.prodUid.value = "";
    els.prodUid.readOnly = false;
    els.prodUid.classList.remove('readonly-input');
    els.prodName.value = "";
    els.prodPrice.value = "";
    els.prodStock.value = "20";
    els.prodCategory.value = "Dairy";
    els.prodShelf.value = "";
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

    els.modalTitle.textContent = "Edit Product";
    els.prodOriginalUid.value = product.uid;
    els.prodUid.value = product.uid;
    els.prodUid.readOnly = true;
    els.prodUid.classList.add('readonly-input');
    
    els.prodName.value = product.name;
    els.prodPrice.value = product.price;
    els.prodStock.value = product.stock !== undefined ? product.stock : 20;
    els.prodCategory.value = product.category || "Dairy";
    els.prodShelf.value = product.shelf || "";
    els.prodOffer.value = product.offer || "";
    
    els.prodSubmitBtn.textContent = "Save Changes";
    els.productModal.classList.add('active');
    setTimeout(() => els.prodName.focus(), 100);
}

function closeProductModal() {
    if (els.productModal) els.productModal.classList.remove('active');
}

// Handle Form Submission (Add / Edit)
async function handleFormSubmit(e) {
    e.preventDefault();

    const originalUid = els.prodOriginalUid.value;
    const uid = els.prodUid.value.trim();
    const name = els.prodName.value.trim();
    const price = parseFloat(els.prodPrice.value);
    const stock = parseInt(els.prodStock.value) || 0;
    const category = els.prodCategory.value;
    const shelf = els.prodShelf.value.trim();
    const offer = els.prodOffer.value.trim() || "No Active Offers";

    if (!uid || !name || isNaN(price)) {
        alert("Please fill all fields correctly.");
        return;
    }

    els.prodSubmitBtn.disabled = true;
    els.prodSubmitBtn.textContent = "Saving...";

    const payload = { uid, name, price, stock, category, shelf, offer };

    try {
        const res = await fetch('/api/products/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.success) {
            closeProductModal();
            await fetchProducts();
            if (window.showToast) {
                window.showToast("Catalog Saved", `Product "${name}" saved successfully.`, "success");
            }
        } else {
            alert(data.message || "Failed to save product.");
        }
    } catch (err) {
        console.error("Form submit error:", err);
        alert("Network error while saving product.");
    } finally {
        els.prodSubmitBtn.disabled = false;
    }
}

// Handle Delete Request
async function deleteProduct(uid) {
    const product = Products.find(p => p.uid === uid);
    if (!product) return;

    if (!confirm(`Are you sure you want to delete "${product.name}"?\nThis cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/products/${encodeURIComponent(uid)}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
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
