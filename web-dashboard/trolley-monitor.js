/**
 * Trolley Telemetry Detail Monitor — trolley-monitor.js v2.5
 * Loads real-time telemetry and cart details from MongoDB via /api/trolleys/<id>
 * Dynamic hardware health checks, Wi-Fi telemetry, customer session, and cart lifecycle.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── State ─────────────────────────────────────────────────────────────────
    let currentTrolleyId = 'TROLLEY-001';
    let trolleysList = [];
    let isFetching = false;

    const els = {
        select: document.getElementById('monitor-trolley-select'),
        refreshBtn: document.getElementById('monitor-refresh-btn'),
        headerBadge: document.getElementById('monitor-header-badge'),
        hwHealthPill: document.getElementById('hw-health-pill'),
        hwTelemetry: document.getElementById('hw-telemetry-container'),
        deviceInfo: document.getElementById('device-info-container'),
        custSession: document.getElementById('customer-session-container'),
        cartStatusLabel: document.getElementById('monitor-cart-status-label'),
        itemCountBadge: document.getElementById('monitor-item-count-badge'),
        cartTotal: document.getElementById('monitor-cart-total'),
        cartItems: document.getElementById('monitor-cart-items'),
        summaryBox: document.getElementById('monitor-cart-summary-box'),
        summarySubtotal: document.getElementById('summary-subtotal'),
        summaryTax: document.getElementById('summary-tax'),
        summaryGrandTotal: document.getElementById('summary-grand-total'),
        resetBtn: document.getElementById('monitor-reset-btn'),
        genBillBtn: document.getElementById('monitor-genbill-btn'),
        checkoutBtn: document.getElementById('monitor-checkout-btn')
    };

    // ── Parse URL parameter ───────────────────────────────────────────────────
    const urlParams = new URLSearchParams(window.location.search);
    const urlId = urlParams.get('id');
    if (urlId) currentTrolleyId = urlId.trim().toUpperCase();

    // ── Main data loader ──────────────────────────────────────────────────────
    async function loadData() {
        if (isFetching) return;
        isFetching = true;

        try {
            const fetchFn = window.authFetch || fetch;

            // 1. Fetch all trolleys for selector dropdown
            const resList = await fetchFn('/api/trolleys');
            if (resList.ok) {
                trolleysList = await resList.json();
                populateDropdown();
            }

            // Ensure currentTrolleyId exists in fleet if list is non-empty
            if (trolleysList.length > 0 && !trolleysList.some(t => t.id === currentTrolleyId)) {
                currentTrolleyId = trolleysList[0].id;
                if (history.replaceState) {
                    history.replaceState(null, '', `?id=${encodeURIComponent(currentTrolleyId)}`);
                }
            }

            // 2. Fetch full detail for selected trolley
            const resDet = await fetchFn(`/api/trolleys/${encodeURIComponent(currentTrolleyId)}`);
            if (!resDet.ok) {
                renderOfflineState();
                isFetching = false;
                return;
            }
            const trolley = await resDet.json();

            const isOnline = Boolean(trolley.status === 'online' || trolley.connection_status === 'connected');

            // 3. Render all telemetry panels
            renderHeaderBadge(trolley, isOnline);
            renderHardwareTelemetry(trolley, isOnline);
            renderDeviceInfo(trolley, isOnline);
            renderCustomerSession(trolley);
            renderCartItems(trolley.cart || {}, trolley.current_mode, isOnline);

        } catch (e) {
            console.error("Failed to load monitor details:", e);
            renderOfflineState();
        } finally {
            isFetching = false;
        }
    }

    // ── Populate trolley selector dropdown without flicker ───────────────────
    function populateDropdown() {
        if (!els.select || trolleysList.length === 0) return;

        const currentOptions = Array.from(els.select.options);
        const needsFullRebuild = currentOptions.length !== trolleysList.length ||
            !trolleysList.every((t, i) => currentOptions[i] && currentOptions[i].value === t.id);

        if (needsFullRebuild) {
            els.select.innerHTML = '';
            trolleysList.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                const isOnline = Boolean(t.status === 'online' || t.connection_status === 'connected');
                opt.textContent = `${t.id} — ${isOnline ? '🟢 Connected' : '🔴 Offline'} (${t.assignment_status || 'AVAILABLE'})`;
                if (t.id === currentTrolleyId) opt.selected = true;
                els.select.appendChild(opt);
            });
            if (els.select.value) {
                currentTrolleyId = els.select.value;
            }
        } else {
            // Update labels without recreating options
            trolleysList.forEach((t, i) => {
                const opt = currentOptions[i];
                const isOnline = Boolean(t.status === 'online' || t.connection_status === 'connected');
                const text = `${t.id} — ${isOnline ? '🟢 Connected' : '🔴 Offline'} (${t.assignment_status || 'AVAILABLE'})`;
                if (opt.textContent !== text) opt.textContent = text;
            });
            if (els.select.value !== currentTrolleyId) {
                els.select.value = currentTrolleyId;
            }
        }
    }

    // ── Top Header Badge ──────────────────────────────────────────────────────
    function renderHeaderBadge(trolley, isOnline) {
        if (!els.headerBadge) return;
        if (isOnline) {
            const mode = trolley.current_mode || 'ADD';
            els.headerBadge.className = 'trolley-status-badge active';
            els.headerBadge.innerHTML = `<span class="pulse-dot" style="background:var(--accent-green);display:inline-block;margin-right:4px;"></span> Online (${mode})`;
        } else {
            els.headerBadge.className = 'trolley-status-badge offline';
            els.headerBadge.innerHTML = `<span class="pulse-dot" style="background:var(--accent-red);display:inline-block;margin-right:4px;"></span> Disconnected`;
        }
    }

    // ── Hardware Health Panel ─────────────────────────────────────────────────
    function renderHardwareTelemetry(trolley, isOnline) {
        if (!els.hwTelemetry) return;

        const batt = trolley.battery || 0;
        const battClass = batt > 60 ? 'online' : (batt > 20 ? 'idle' : 'offline');
        const heartbeatText = trolley.last_heartbeat_display ||
            (trolley.last_seen_24h ? `${trolley.last_seen_24h} (${trolley.last_seen_relative})` : (trolley.last_seen_str || 'Never'));

        const rfidActive = isOnline && (trolley.rfid_ready !== false);
        const lcdActive  = isOnline && (trolley.lcd_ready !== false);
        const hasHwFault = isOnline && (!rfidActive || !lcdActive);

        // Hardware health pill
        if (els.hwHealthPill) {
            if (!isOnline) {
                els.hwHealthPill.className = 'trolley-status-badge offline';
                els.hwHealthPill.textContent = 'DISCONNECTED';
            } else if (hasHwFault) {
                els.hwHealthPill.className = 'trolley-status-badge idle';
                els.hwHealthPill.textContent = trolley.hardware_health || 'HARDWARE_FAULT';
            } else {
                els.hwHealthPill.className = 'trolley-status-badge active';
                els.hwHealthPill.textContent = 'HEALTHY';
            }
        }

        let hwAlertBanner = '';
        if (hasHwFault) {
            const faultMsg = !rfidActive && !lcdActive
                ? 'RFID scanner and 16x2 LCD display are both disconnected or disabled. Trolley is operating in headless Wi-Fi mode.'
                : (!rfidActive
                    ? 'MFRC522 RFID reader is disconnected or disabled. RFID item scans will not register.'
                    : '16x2 I2C LCD screen is not responding on I2C bus (SDA:21, SCL:22).');
            hwAlertBanner = `
                <div style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:8px 12px;margin-bottom:8px;font-size:0.8rem;color:#fca5a5;display:flex;align-items:center;gap:8px;">
                    <i class="fa-solid fa-triangle-exclamation" style="color:#ef4444;font-size:1.1rem;flex-shrink:0;"></i>
                    <span><strong>Hardware Alert:</strong> ${faultMsg}</span>
                </div>`;
        }

        const rfidStatusText = !isOnline ? 'Inactive (Offline)' : (rfidActive ? 'Active & Ready' : 'Disconnected / Disabled');
        const rfidClass = !isOnline ? 'offline' : (rfidActive ? 'online' : 'offline');

        const lcdStatusText = !isOnline ? 'Offline' : (lcdActive ? 'Active (I2C 0x27)' : 'Not Detected (I2C)');
        const lcdClass = !isOnline ? 'offline' : (lcdActive ? 'online' : 'idle');

        els.hwTelemetry.innerHTML = `
            ${hwAlertBanner}
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>ESP32 Microcontroller</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    <span class="pulse-dot" style="background:${isOnline ? 'var(--accent-green)' : 'var(--accent-red)'}"></span>
                    ${isOnline ? 'Connected (Wi-Fi Online)' : 'Disconnected (Cart Saved)'}
                </span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>MFRC522 RFID Module</span>
                <span class="status-text ${rfidClass}">
                    ${rfidActive ? '<i class="fa-solid fa-circle-check" style="margin-right:4px;"></i>' : (isOnline ? '<i class="fa-solid fa-triangle-exclamation" style="margin-right:4px;color:#ef4444;"></i>' : '')}${rfidStatusText}
                </span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>16x2 I2C LCD Display</span>
                <span class="status-text ${lcdClass}">
                    ${lcdActive ? '<i class="fa-solid fa-circle-check" style="margin-right:4px;"></i>' : (isOnline ? '<i class="fa-solid fa-triangle-exclamation" style="margin-right:4px;color:#f59e0b;"></i>' : '')}${lcdStatusText}
                </span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>Piezo Audio Buzzer</span>
                <span class="status-text ${isOnline ? 'online' : 'offline'}">
                    ${isOnline ? '<i class="fa-solid fa-volume-high" style="margin-right:4px;"></i>Ready (PWM Pin 25)' : 'Offline'}
                </span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>Battery Level</span>
                <span class="status-text ${isOnline ? battClass : 'offline'}">
                    ${isOnline ? `${getBatteryIcon(batt)} ${batt}%` : '<i class="fa-solid fa-battery-slash" style="margin-right:4px;"></i>—'}
                </span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>Last Heartbeat</span>
                <span style="font-family:monospace;font-size:0.83rem;color:var(--text-secondary);">${heartbeatText}</span>
            </div>`;
    }

    // ── Device Network Info Panel ─────────────────────────────────────────────
    function renderDeviceInfo(trolley, isOnline) {
        if (!els.deviceInfo) return;

        const online = (isOnline !== undefined) ? isOnline : (trolley.status === 'online' || trolley.connection_status === 'connected');
        const rssi = trolley.wifi_rssi || 0;
        let rssiLabel = 'N/A';
        let rssiQuality = '—';
        let rssiColor = 'var(--text-secondary)';

        if (rssi !== 0) {
            rssiLabel = rssi + ' dBm';
            if (rssi >= -55) { rssiQuality = 'Excellent'; rssiColor = 'var(--accent-green)'; }
            else if (rssi >= -65) { rssiQuality = 'Good'; rssiColor = 'var(--accent-green)'; }
            else if (rssi >= -75) { rssiQuality = 'Fair'; rssiColor = '#f59e0b'; }
            else if (rssi >= -85) { rssiQuality = 'Weak'; rssiColor = '#ef4444'; }
            else { rssiQuality = 'Very Weak'; rssiColor = '#ef4444'; }
        } else if (online) {
            rssiLabel = '0 dBm';
            rssiQuality = 'Online';
            rssiColor = 'var(--accent-green)';
        } else {
            rssiLabel = 'No Signal';
            rssiQuality = 'Offline';
        }

        const connStatusBadge = online
            ? `<span style="color:var(--accent-green);font-size:0.8rem;margin-left:6px;font-weight:600;"><i class="fa-solid fa-link" style="margin-right:3px;"></i>Connected</span>`
            : `<span style="color:#ef4444;font-size:0.8rem;margin-left:6px;font-weight:600;"><i class="fa-solid fa-link-slash" style="margin-right:3px;"></i>Not Connected</span>`;

        const isAssigned = trolley.assignment_status === 'ASSIGNED';
        const currentMode = online && trolley.current_mode !== 'OFFLINE' ? (trolley.current_mode || 'ADD') : 'Disconnected (Offline)';
        const modeBadgeClass = online && trolley.current_mode !== 'OFFLINE' ? (trolley.current_mode === 'ADD' ? 'active' : 'idle') : 'offline';

        els.deviceInfo.innerHTML = `
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>Trolley Identifier</span>
                <span style="font-family:monospace;font-size:0.9rem;color:var(--accent-cyan);font-weight:600;">${trolley.id}</span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>Device IP Address</span>
                <span style="font-family:monospace;font-size:0.88rem;">${trolley.ip_address || '—'}</span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span><i class="fa-solid fa-wifi" style="margin-right:5px;"></i>Wi-Fi Signal (RSSI)</span>
                <span style="color:${rssiColor};font-weight:500;">
                    ${rssiLabel} <em style="font-size:0.78rem;opacity:0.8;">(${rssiQuality})</em> ${connStatusBadge}
                </span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>Fleet Assignment</span>
                <span class="trolley-status-badge ${isAssigned ? 'idle' : 'active'}" style="font-size:0.75rem;">
                    ${trolley.assignment_status || 'AVAILABLE'}
                </span>
            </div>
            <div class="hardware-status-panel" style="margin-bottom:0;">
                <span>Operating Mode</span>
                <span class="trolley-status-badge ${modeBadgeClass}" style="font-size:0.75rem;">
                    ${currentMode}
                </span>
            </div>`;
    }

    // ── Customer Session Panel ────────────────────────────────────────────────
    function renderCustomerSession(trolley) {
        if (!els.custSession) return;

        const isAssigned = trolley.assignment_status === 'ASSIGNED';
        const custName = trolley.assigned_customer_name || (trolley.cart && trolley.cart.customer_name) || '';
        const custId = trolley.assigned_customer_id || (trolley.cart && trolley.cart.customer_id) || '';
        const custPhone = trolley.assigned_customer_phone || (trolley.cart && trolley.cart.customer_phone) || '';
        const custEmail = trolley.assigned_customer_email || '';

        const hasCustomer = isAssigned || Boolean(custName || custId);

        if (hasCustomer) {
            els.custSession.innerHTML = `
                <div class="hardware-status-panel" style="margin-bottom:0;">
                    <span>Shopper Name</span>
                    <strong style="color:var(--accent-purple);font-size:0.95rem;">${custName || 'Registered Shopper'}</strong>
                </div>
                <div class="hardware-status-panel" style="margin-bottom:0;">
                    <span>Customer ID</span>
                    <span style="font-family:monospace;font-size:0.88rem;">${custId || '—'}</span>
                </div>
                <div class="hardware-status-panel" style="margin-bottom:0;">
                    <span>Mobile Number</span>
                    <span style="font-size:0.88rem;">${custPhone || 'Not provided'}</span>
                </div>
                ${custEmail ? `
                <div class="hardware-status-panel" style="margin-bottom:0;">
                    <span>Email Address</span>
                    <span style="font-size:0.85rem;color:var(--text-secondary);">${custEmail}</span>
                </div>` : ''}
                <div class="hardware-status-panel" style="margin-bottom:0;">
                    <span>Session Persistence</span>
                    <span class="trolley-status-badge active" style="font-size:0.72rem;background:rgba(168,85,247,0.2);color:#c084fc;">
                        <i class="fa-solid fa-database" style="margin-right:4px;"></i>Saved in MongoDB
                    </span>
                </div>
                <button id="monitor-unassign-btn" class="btn btn-outline" style="font-size:0.78rem;padding:7px 12px;color:var(--accent-red);width:100%;margin-top:6px;">
                    <i class="fa-solid fa-user-xmark" style="margin-right:6px;"></i>Unassign Shopper
                </button>`;

            // Bind unassign button
            const unassignBtn = document.getElementById('monitor-unassign-btn');
            if (unassignBtn) {
                unassignBtn.addEventListener('click', async () => {
                    if (!confirm(`Unassign customer from ${currentTrolleyId}?`)) return;
                    try {
                        const fetchFn = window.authFetch || fetch;
                        const res = await fetchFn(`/api/trolleys/${encodeURIComponent(currentTrolleyId)}/unassign`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        });
                        if (res.ok) {
                            if (window.showToast) window.showToast('Trolley Released', `${currentTrolleyId} is now available.`, 'info');
                            loadData();
                        }
                    } catch (err) {
                        console.error('Failed to unassign trolley:', err);
                    }
                });
            }
        } else {
            els.custSession.innerHTML = `
                <div style="text-align:center;color:var(--text-secondary);padding:14px 0;">
                    <i class="fa-solid fa-user-clock" style="font-size:1.5rem;margin-bottom:8px;opacity:0.4;display:block;"></i>
                    <p style="font-size:0.85rem;margin:0 0 10px 0;">Trolley is unassigned and AVAILABLE for next shopper.</p>
                    <a href="trolleys.html" class="btn btn-outline" style="font-size:0.78rem;padding:5px 12px;display:inline-block;">
                        <i class="fa-solid fa-user-plus" style="margin-right:5px;"></i>Assign Customer in Fleet
                    </a>
                </div>`;
        }
    }

    // ── Cart Items Panel ──────────────────────────────────────────────────────
    function renderCartItems(cart, currentMode, isOnline) {
        if (!els.cartItems || !els.cartTotal) return;

        const rawItems = cart.items || {};
        const itemsList = Array.isArray(rawItems) ? rawItems : Object.values(rawItems);
        const total = typeof cart.total === 'number' ? cart.total : (parseFloat(cart.total) || 0.0);
        const cartStatus = cart.status || 'ACTIVE';
        const totalItemsCount = itemsList.reduce((sum, item) => sum + (item.quantity || 1), 0);

        // Update item count badge
        if (els.itemCountBadge) {
            els.itemCountBadge.textContent = `${totalItemsCount} item${totalItemsCount !== 1 ? 's' : ''}`;
        }

        // Update mode / status label
        if (els.cartStatusLabel) {
            if (cartStatus === 'BILL_GENERATED') {
                els.cartStatusLabel.innerHTML = `<span style="color:#f59e0b;font-weight:500;"><i class="fa-solid fa-file-invoice" style="margin-right:5px;"></i>Bill Generated — Payment Pending</span>`;
            } else if (!isOnline) {
                els.cartStatusLabel.innerHTML = `<span style="color:#f87171;"><i class="fa-solid fa-power-off" style="margin-right:5px;"></i>Trolley Disconnected (Cart Preserved)</span>`;
            } else if (currentMode === 'REMOVE') {
                els.cartStatusLabel.innerHTML = `<span class="trolley-status-badge idle" style="font-size:0.75rem;"><i class="fa-solid fa-minus-circle" style="margin-right:4px;"></i>Mode: REMOVE</span>`;
            } else {
                els.cartStatusLabel.innerHTML = `<span class="trolley-status-badge active" style="font-size:0.75rem;"><i class="fa-solid fa-plus-circle" style="margin-right:4px;"></i>Mode: ADD</span>`;
            }
        }

        els.cartTotal.textContent = `Rs.${total.toFixed(2)}`;
        els.cartItems.innerHTML = '';

        if (itemsList.length === 0) {
            els.cartItems.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align:center;color:var(--text-secondary);padding:45px 20px;">
                        <i class="fa-solid fa-basket-shopping" style="font-size:2rem;margin-bottom:10px;opacity:0.3;display:block;"></i>
                        <p style="margin:0;font-size:0.9rem;">No scanned products in this cart.</p>
                        <span style="font-size:0.78rem;opacity:0.6;">Products scanned via RFID will appear here in real-time.</span>
                    </td>
                </tr>`;

            if (els.summaryBox) els.summaryBox.style.display = 'none';
            if (els.genBillBtn) els.genBillBtn.style.display = 'none';
            if (els.checkoutBtn) els.checkoutBtn.style.display = 'none';
            return;
        }

        // Render table rows
        itemsList.forEach((item, index) => {
            const price = typeof item.price === 'number' ? item.price : (parseFloat(item.price) || 0.0);
            const qty = item.quantity || 1;
            const subtotal = typeof item.subtotal === 'number' ? item.subtotal : (price * qty);

            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="color:var(--text-secondary);font-size:0.82rem;">${index + 1}</td>
                <td style="font-weight:500;">${item.name || 'Unknown Product'}</td>
                <td>Rs.${price.toFixed(2)}</td>
                <td><span style="display:inline-block;padding:2px 8px;background:rgba(255,255,255,0.06);border-radius:4px;font-weight:600;">${qty}</span></td>
                <td style="color:var(--accent-green);font-weight:600;">Rs.${subtotal.toFixed(2)}</td>`;
            els.cartItems.appendChild(row);
        });

        // Summary Breakdown (Subtotal excl. GST, Taxes, Grand Total)
        if (els.summaryBox) {
            els.summaryBox.style.display = 'block';
            const baseSubtotal = total / 1.18;
            const gstAmount = total - baseSubtotal;
            if (els.summarySubtotal) els.summarySubtotal.textContent = `Rs.${baseSubtotal.toFixed(2)}`;
            if (els.summaryTax) els.summaryTax.textContent = `Rs.${gstAmount.toFixed(2)}`;
            if (els.summaryGrandTotal) els.summaryGrandTotal.textContent = `Rs.${total.toFixed(2)}`;
        }

        // Action Buttons visibility
        if (els.genBillBtn && els.checkoutBtn) {
            if (cartStatus === 'BILL_GENERATED') {
                els.genBillBtn.style.display = 'none';
                els.checkoutBtn.style.display = 'block';
            } else {
                els.genBillBtn.style.display = 'block';
                els.checkoutBtn.style.display = 'none';
            }
        }
    }

    // ── Offline fallback ──────────────────────────────────────────────────────
    function renderOfflineState() {
        if (els.headerBadge) {
            els.headerBadge.className = 'trolley-status-badge offline';
            els.headerBadge.textContent = 'Server Offline';
        }
        if (els.hwTelemetry) {
            els.hwTelemetry.innerHTML = `
                <div style="text-align:center;color:var(--text-secondary);padding:25px 0;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size:1.6rem;margin-bottom:8px;color:var(--accent-red);display:block;"></i>
                    <p style="margin:0;">Unable to connect to server backend.</p>
                </div>`;
        }
        if (els.cartItems) {
            els.cartItems.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--text-secondary);">No data available.</td></tr>`;
        }
    }

    // ── Utility: battery icon ─────────────────────────────────────────────────
    function getBatteryIcon(pct) {
        if (pct >= 75) return '<i class="fa-solid fa-battery-full" style="color:var(--accent-green);"></i>';
        if (pct >= 50) return '<i class="fa-solid fa-battery-three-quarters" style="color:var(--accent-green);"></i>';
        if (pct >= 25) return '<i class="fa-solid fa-battery-half" style="color:#f59e0b;"></i>';
        if (pct >= 10) return '<i class="fa-solid fa-battery-quarter" style="color:#ef4444;"></i>';
        return '<i class="fa-solid fa-battery-empty" style="color:#ef4444;"></i>';
    }

    // ── Dropdown change listener ──────────────────────────────────────────────
    if (els.select) {
        els.select.addEventListener('change', e => {
            currentTrolleyId = e.target.value;
            if (history.pushState) {
                history.pushState(null, '', `?id=${encodeURIComponent(currentTrolleyId)}`);
            }
            loadData();
        });
    }

    // ── Refresh button listener ───────────────────────────────────────────────
    if (els.refreshBtn) {
        els.refreshBtn.addEventListener('click', () => {
            const icon = els.refreshBtn.querySelector('i');
            if (icon) icon.classList.add('fa-spin');
            loadData().finally(() => {
                setTimeout(() => {
                    if (icon) icon.classList.remove('fa-spin');
                }, 400);
            });
        });
    }

    // ── Reset Cart button listener ────────────────────────────────────────────
    if (els.resetBtn) {
        els.resetBtn.addEventListener('click', async () => {
            if (!confirm(`Reset cart for ${currentTrolleyId}?\nThis will restore all item stock back to global inventory.`)) return;
            try {
                const fetchFn = window.authFetch || fetch;
                const res = await fetchFn('/api/cart/reset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ trolley_id: currentTrolleyId })
                });
                if (res.ok) {
                    if (window.showToast) window.showToast('Cart Cleared', `${currentTrolleyId} cart has been reset.`, 'info');
                    loadData();
                } else {
                    const err = await res.json();
                    if (window.showToast) window.showToast('Reset Blocked', err.message || 'Failed to reset cart', 'warning');
                    else alert(err.message || 'Failed to reset cart');
                }
            } catch (e) {
                console.error('Reset failed:', e);
            }
        });
    }

    // ── Generate Bill button listener ─────────────────────────────────────────
    if (els.genBillBtn) {
        els.genBillBtn.addEventListener('click', async () => {
            try {
                const fetchFn = window.authFetch || fetch;
                const res = await fetchFn('/api/cart/generate-bill', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ trolley_id: currentTrolleyId })
                });
                if (res.ok) {
                    if (window.showToast) window.showToast('Bill Generated', `Invoice created for ${currentTrolleyId}.`, 'success');
                    loadData();
                } else {
                    const err = await res.json();
                    alert(err.message || 'Failed to generate bill');
                }
            } catch (e) {
                console.error('Generate bill failed:', e);
            }
        });
    }

    // ── Finalize Payment button listener ──────────────────────────────────────
    if (els.checkoutBtn) {
        els.checkoutBtn.addEventListener('click', async () => {
            if (!confirm(`Finalize payment and checkout ${currentTrolleyId}?`)) return;
            try {
                const fetchFn = window.authFetch || fetch;
                const res = await fetchFn('/api/cart/checkout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ trolley_id: currentTrolleyId, payment_method: 'CASH' })
                });
                if (res.ok) {
                    if (window.showToast) window.showToast('Payment Completed', `Checkout completed for ${currentTrolleyId}.`, 'success');
                    loadData();
                } else {
                    const err = await res.json();
                    alert(err.message || 'Failed to complete checkout');
                }
            } catch (e) {
                console.error('Checkout failed:', e);
            }
        });
    }

    // ── Initial load & reactive polling ───────────────────────────────────────
    loadData();
    setInterval(loadData, 3000);
});
