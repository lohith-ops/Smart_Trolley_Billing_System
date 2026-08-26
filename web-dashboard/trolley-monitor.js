/**
 * Trolley Telemetry Detail Monitor — trolley-monitor.js v2.0
 * Loads real-time data from /api/trolleys/<id> and /api/trolleys/<id>/cart
 * All data is live from MongoDB — no hardcoded mock objects.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── State ─────────────────────────────────────────────────────────────────
    let currentTrolleyId = 'TROLLEY-001';
    let trolleysList = [];

    const els = {
        select:          document.getElementById('monitor-trolley-select'),
        hwTelemetry:     document.getElementById('hw-telemetry-container'),
        deviceInfo:      document.getElementById('device-info-container'),
        cartStatusLabel: document.getElementById('monitor-cart-status-label'),
        cartTotal:       document.getElementById('monitor-cart-total'),
        cartItems:       document.getElementById('monitor-cart-items'),
        resetBtn:        document.getElementById('monitor-reset-btn')
    };

    // ── Parse URL parameter ───────────────────────────────────────────────────
    const urlParams = new URLSearchParams(window.location.search);
    const urlId = urlParams.get('id');
    if (urlId) currentTrolleyId = urlId;

    // ── Main data loader ──────────────────────────────────────────────────────
    async function loadData() {
        try {
            // 1. Fetch all trolleys for dropdown population
            const resList = await fetch('/api/trolleys');
            if (resList.ok) {
                trolleysList = await resList.json();
                populateDropdown();
            }

            // 2. Fetch full detail for selected trolley
            const resDet = await fetch(`/api/trolleys/${encodeURIComponent(currentTrolleyId)}`);
            if (!resDet.ok) {
                renderOfflineState();
                return;
            }
            const trolley = await resDet.json();

            // 3. Render panels
            renderHardwareTelemetry(trolley);
            renderDeviceInfo(trolley);
            renderCartItems(trolley.cart || {}, trolley.current_mode || 'ADD');

        } catch (e) {
            console.error("Failed to load monitor details:", e);
            renderOfflineState();
        }
    }

    // ── Populate trolley selector dropdown ────────────────────────────────────
    function populateDropdown() {
        if (!els.select) return;
        els.select.innerHTML = '';
        trolleysList.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = `${t.id} — ${t.status === 'online' ? '🟢' : '🔴'} ${t.status}`;
            if (t.id === currentTrolleyId) opt.selected = true;
            els.select.appendChild(opt);
        });
    }

    // ── Hardware Health Panel ─────────────────────────────────────────────────
    function renderHardwareTelemetry(trolley) {
        if (!els.hwTelemetry) return;
        const isOnline = trolley.status === 'online';
        const batt = trolley.battery || 0;
        const battClass = batt > 60 ? 'online' : (batt > 20 ? 'idle' : 'offline');

        els.hwTelemetry.innerHTML = `
            <div class="hardware-status-panel">
                <span>ESP32 Microcontroller</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    <span class="pulse-dot" style="background:${isOnline ? 'var(--accent-green)' : 'var(--accent-red)'}"></span>
                    ${isOnline ? 'Connected' : 'Disconnected'}
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>MFRC522 RFID Module</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    ${isOnline ? 'Active & Ready' : 'Inactive'}
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>16x2 I2C LCD Display</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    ${isOnline ? 'Active' : 'Offline'}
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>Piezo Buzzer</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    ${isOnline ? 'Ready' : 'Offline'}
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>Battery Level</span>
                <span class="status-text ${battClass}">
                    ${getBatteryIcon(batt)} ${batt}%
                </span>
            </div>
            <div class="hardware-status-panel">
                <span>Last Heartbeat</span>
                <span>${trolley.last_seen_str || 'Never'}</span>
            </div>`;
    }

    // ── Device Network Info Panel ─────────────────────────────────────────────
    function renderDeviceInfo(trolley) {
        if (!els.deviceInfo) return;
        const rssi = trolley.wifi_rssi || 0;
        let rssiLabel = 'N/A';
        let rssiQuality = '—';
        let rssiColor = 'var(--text-secondary)';

        if (rssi !== 0) {
            rssiLabel = rssi + ' dBm';
            if (rssi >= -55) { rssiQuality = 'Excellent'; rssiColor = 'var(--accent-green)'; }
            else if (rssi >= -65) { rssiQuality = 'Good';      rssiColor = 'var(--accent-green)'; }
            else if (rssi >= -75) { rssiQuality = 'Fair';       rssiColor = '#f59e0b'; }
            else if (rssi >= -85) { rssiQuality = 'Weak';       rssiColor = '#ef4444'; }
            else { rssiQuality = 'Very Weak'; rssiColor = '#ef4444'; }
        }

        els.deviceInfo.innerHTML = `
            <div class="hardware-status-panel">
                <span>Trolley ID</span>
                <span style="font-family:monospace;font-size:0.9rem;color:var(--accent-cyan);">${trolley.id}</span>
            </div>
            <div class="hardware-status-panel">
                <span>IP Address</span>
                <span style="font-family:monospace;font-size:0.9rem;">${trolley.ip_address || '—'}</span>
            </div>
            <div class="hardware-status-panel">
                <span>Wi-Fi RSSI</span>
                <span style="color:${rssiColor}">${rssiLabel} <em style="font-size:0.78rem;opacity:0.75;">(${rssiQuality})</em></span>
            </div>
            <div class="hardware-status-panel">
                <span>Firmware Version</span>
                <span>v${trolley.firmware_version || '—'}</span>
            </div>
            <div class="hardware-status-panel">
                <span>Current Mode</span>
                <span class="trolley-status-badge ${trolley.current_mode === 'ADD' ? 'active' : 'idle'}" style="font-size:0.75rem;">
                    ${trolley.current_mode || 'ADD'}
                </span>
            </div>`;
    }

    // ── Cart Items Panel ──────────────────────────────────────────────────────
    function renderCartItems(cart, currentMode) {
        if (!els.cartItems || !els.cartTotal) return;

        const items = cart.items || {};
        const total = cart.total || 0.0;
        const cartStatus = cart.status || 'ACTIVE';

        // Update mode label
        if (els.cartStatusLabel) {
            let modeHtml = `Mode: <strong>${currentMode}</strong>`;
            if (cartStatus === 'BILL_GENERATED') {
                modeHtml = `<span style="color:#f59e0b;"><i class="fa-solid fa-file-invoice" style="margin-right:5px;"></i>Bill Generated — Payment Pending</span>`;
            }
            els.cartStatusLabel.innerHTML = modeHtml;
        }

        els.cartTotal.textContent = `Rs.${total.toFixed(2)}`;
        els.cartItems.innerHTML = '';

        const itemValues = Object.values(items);
        if (itemValues.length === 0) {
            els.cartItems.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align:center;color:var(--text-secondary);padding:40px;">
                        <i class="fa-solid fa-basket-shopping" style="font-size:1.8rem;margin-bottom:10px;opacity:0.3;display:block;"></i>
                        <p>No scanned products in this cart.</p>
                    </td>
                </tr>`;
            return;
        }

        itemValues.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="font-weight:500;">${item.name}</td>
                <td>Rs.${item.price.toFixed(2)}</td>
                <td>${item.quantity}</td>
                <td style="color:var(--accent-green);font-weight:600;">Rs.${item.subtotal.toFixed(2)}</td>`;
            els.cartItems.appendChild(row);
        });
    }

    // ── Offline fallback ──────────────────────────────────────────────────────
    function renderOfflineState() {
        if (els.hwTelemetry) {
            els.hwTelemetry.innerHTML = `
                <div style="text-align:center;color:var(--text-secondary);padding:20px 0;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size:1.5rem;margin-bottom:8px;color:var(--accent-red);display:block;"></i>
                    <p>Unable to load trolley data. Server may be unreachable.</p>
                </div>`;
        }
        if (els.cartItems) {
            els.cartItems.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:30px;color:var(--text-secondary);">No data available.</td></tr>`;
        }
    }

    // ── Utility: battery icon ─────────────────────────────────────────────────
    function getBatteryIcon(pct) {
        if (pct >= 75) return '<i class="fa-solid fa-battery-full"></i>';
        if (pct >= 50) return '<i class="fa-solid fa-battery-three-quarters"></i>';
        if (pct >= 25) return '<i class="fa-solid fa-battery-half"></i>';
        if (pct >= 10) return '<i class="fa-solid fa-battery-quarter"></i>';
        return '<i class="fa-solid fa-battery-empty" style="color:var(--accent-red);"></i>';
    }

    // ── Dropdown change ───────────────────────────────────────────────────────
    if (els.select) {
        els.select.addEventListener('change', e => {
            currentTrolleyId = e.target.value;
            history.pushState(null, '', `?id=${currentTrolleyId}`);
            loadData();
        });
    }

    // ── Reset button ──────────────────────────────────────────────────────────
    if (els.resetBtn) {
        els.resetBtn.addEventListener('click', async () => {
            if (!confirm(`Reset cart for ${currentTrolleyId}? This will restore all stock.`)) return;
            try {
                const res = await fetch('/api/cart/reset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ trolley_id: currentTrolleyId })
                });
                if (res.ok) {
                    if (window.showToast) window.showToast('Cart Reset', `${currentTrolleyId} cart has been cleared.`, 'info');
                    loadData();
                }
            } catch (e) {
                console.error('Reset failed:', e);
            }
        });
    }

    // ── Init & polling ────────────────────────────────────────────────────────
    loadData();
    setInterval(loadData, 3000);
});
