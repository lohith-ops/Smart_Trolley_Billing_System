/**
 * Trolley Telemetry Detail Monitor
 */

document.addEventListener('DOMContentLoaded', () => {
    let currentTrolleyId = 'Trolley-01';
    let trolleysList = [];

    const els = {
        select: document.getElementById('monitor-trolley-select'),
        hwTelemetry: document.getElementById('hw-telemetry-container'),
        customerProfile: document.getElementById('customer-profile-card'),
        cartTotal: document.getElementById('monitor-cart-total'),
        cartItems: document.getElementById('monitor-cart-items')
    };

    // Parse URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const urlId = urlParams.get('id');
    if (urlId) currentTrolleyId = urlId;

    async function loadData() {
        try {
            // 1. Fetch trolleys to populate select and identify status
            const resTrolleys = await fetch('/api/trolleys');
            if (resTrolleys.ok) {
                trolleysList = await resTrolleys.json();
                populateDropdown();
            }

            // 2. Identify the active trolley object
            const trolley = trolleysList.find(t => t.id === currentTrolleyId) || {
                id: currentTrolleyId,
                status: 'Offline',
                customer: 'None',
                items: 0,
                total: 0.0,
                battery: 0,
                latency: 0
            };

            // 3. Render hardware health
            renderHardwareTelemetry(trolley);

            // 4. Render customer profile
            renderCustomerProfile(trolley);

            // 5. Render cart items
            renderCartItems(trolley);

        } catch (e) {
            console.error("Failed to load monitor details:", e);
        }
    }

    function populateDropdown() {
        if (!els.select) return;
        els.select.innerHTML = '';
        trolleysList.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.id;
            if (t.id === currentTrolleyId) opt.selected = true;
            els.select.appendChild(opt);
        });
    }

    function renderHardwareTelemetry(trolley) {
        if (!els.hwTelemetry) return;

        const isOnline = trolley.status !== 'Offline';
        const latencyText = trolley.latency > 0 ? `${trolley.latency}ms` : 'N/A';
        const batteryClass = trolley.battery > 60 ? 'online' : (trolley.battery > 20 ? 'idle' : 'offline');

        els.hwTelemetry.innerHTML = `
            <div class="hardware-status-panel">
                <span>Arduino Microcontroller</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    <span class="pulse-dot" style="background:${isOnline ? 'var(--accent-green)' : 'var(--accent-red)'}"></span>
                    <span>${isOnline ? 'Connected' : 'Disconnected'}</span>
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>MFRC522 RFID Module</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    <span>${isOnline ? 'Active' : 'Inactive'}</span>
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>16x2 I2C LCD Display</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    <span>${isOnline ? 'Active' : 'Offline'}</span>
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>Subsystem Battery Level</span>
                <span class="status-text ${batteryClass}">
                    <span>${trolley.battery}%</span>
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>Connection Health (Latency)</span>
                <span>${latencyText}</span>
            </div>
        `;
    }

    function renderCustomerProfile(trolley) {
        if (!els.customerProfile) return;

        if (trolley.customer === 'None' || trolley.status === 'Offline') {
            els.customerProfile.innerHTML = `
                <div style="text-align: center; width: 100%; color: var(--text-secondary); padding: 12px 0;">
                    <i class="fa-solid fa-user-slash" style="font-size: 1.5rem; margin-bottom: 8px;"></i>
                    <p>No customer currently assigned to this trolley.</p>
                </div>
            `;
            return;
        }

        // Mock customer demographics depending on selected trolley
        let name = trolley.customer;
        let email = `${name.toLowerCase().replace(' ', '.')}@gmail.com`;
        let tier = 'Silver Member';
        let points = 230;

        if (name.includes('Lohith')) {
            tier = 'Gold Member';
            points = 380;
        } else if (name.includes('Amit')) {
            tier = 'Platinum Member';
            points = 540;
        }

        els.customerProfile.innerHTML = `
            <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=c084fc&color=fff" alt="${name}" style="border-radius: 50%; width: 64px; border: 2px solid var(--accent-purple);">
            <div>
                <h4 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">${name}</h4>
                <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 6px;">${email}</p>
                <div style="display: flex; gap: 10px;">
                    <span class="trolley-status-badge active" style="font-size: 0.7rem; padding: 2px 6px;">${tier}</span>
                    <span class="trolley-status-badge idle" style="font-size: 0.7rem; padding: 2px 6px;"><i class="fa-solid fa-star" style="margin-right: 4px;"></i>${points} Points</span>
                </div>
            </div>
        `;
    }

    async function renderCartItems(trolley) {
        if (!els.cartItems || !els.cartTotal) return;

        let items = [];
        let total = 0.0;

        // If it's Trolley-01, query Flask's real live cart
        if (trolley.id === 'Trolley-01') {
            try {
                const res = await fetch('/api/dashboard');
                if (res.ok) {
                    const data = await res.json();
                    const activeCart1 = data.activeCarts.find(c => c.id === '1');
                    if (activeCart1) {
                        items = Object.values(activeCart1.items);
                        total = activeCart1.total;
                    }
                }
            } catch (err) {
                console.error("Error reading cart_1:", err);
            }
        } else if (trolley.id === 'Trolley-04') {
            // Mock static details for Trolley-04
            items = [
                { name: 'Milk (1 Gallon)', price: 50.00, quantity: 1, subtotal: 50.00 },
                { name: 'Cheddar Cheese', price: 80.00, quantity: 1, subtotal: 80.00 },
                { name: 'Whole Wheat Bread', price: 15.00, quantity: 1, subtotal: 15.00 }
            ];
            total = 145.00;
        }

        els.cartTotal.innerText = `Rs.${total.toFixed(2)}`;
        els.cartItems.innerHTML = '';

        if (items.length === 0) {
            els.cartItems.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: var(--text-secondary); padding: 40px;">
                        <i class="fa-solid fa-basket-shopping" style="font-size: 1.8rem; margin-bottom: 10px; opacity:0.3;"></i>
                        <p>No scanned products inside this cart.</p>
                    </td>
                </tr>
            `;
            return;
        }

        items.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="font-weight: 500;">${item.name}</td>
                <td>Rs.${item.price.toFixed(2)}</td>
                <td>${item.quantity}</td>
                <td style="color: var(--accent-green); font-weight: 600;">Rs.${item.subtotal.toFixed(2)}</td>
            `;
            els.cartItems.appendChild(row);
        });
    }

    // Dropdown change listener
    if (els.select) {
        els.select.addEventListener('change', (e) => {
            currentTrolleyId = e.target.value;
            // Update URL query string
            history.pushState(null, '', `?id=${currentTrolleyId}`);
            loadData();
        });
    }

    // Init loop
    loadData();
    setInterval(loadData, 3000);
});
