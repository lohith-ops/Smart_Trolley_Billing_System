/**
 * Inventory Management Logic
 */

let Products = [];

const els = {
    inventoryList: document.getElementById('inventory-list'),
    addProductBtn: document.getElementById('add-product-btn'),
    
    // Modal Elements
    productModal: document.getElementById('product-modal'),
    productForm: document.getElementById('product-form'),
    modalTitle: document.getElementById('modal-title'),
    prodOriginalUid: document.getElementById('prod-original-uid'),
    prodUid: document.getElementById('prod-uid'),
    prodName: document.getElementById('prod-name'),
    prodPrice: document.getElementById('prod-price'),
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
    } catch (e) {
        console.error("Failed to fetch products:", e);
    }
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
        itemEl.innerHTML = `
            <div class="item-identity">
                <div class="tag-icon"><i class="fa-solid fa-tag"></i></div>
                <div class="item-info">
                    <h4>${p.name}</h4>
                    <span>UID: ${p.uid}</span>
                </div>
            </div>
            <div class="item-price">Rs.${p.price.toFixed(2)}</div>
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
    els.prodUid.readOnly = true; // prevent changing UID during edit, or handle it
    els.prodUid.classList.add('readonly-input');
    
    els.prodName.value = product.name;
    els.prodPrice.value = product.price;
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

    if (!uid || !name || isNaN(price)) {
        alert("Please fill all fields correctly.");
        return;
    }

    els.prodSubmitBtn.disabled = true;
    els.prodSubmitBtn.textContent = "Saving...";

    const payload = { uid, name, price };

    try {
        // If the user modified the UID or it is edit mode, let's use the register endpoint
        const res = await fetch('/api/products/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.success) {
            closeProductModal();
            await fetchProducts();
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
        } else {
            alert(data.message || "Failed to delete product.");
        }
    } catch (e) {
        console.error("Delete error:", e);
        alert("Network error while deleting product.");
    }
}

document.addEventListener('DOMContentLoaded', initInventory);
