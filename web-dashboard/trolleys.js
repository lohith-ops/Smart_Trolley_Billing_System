/**
 * Multi-Trolley Fleet Dashboard — trolleys.js v2.0
 * Displays real-time cards for every trolley registered in MongoDB.
 * Allows Store Admins to dynamically add or decommission trolleys from the UI.
 */

document.addEventListener('DOMContentLoaded', () => {
    let allTrolleys = [];
    let activeFilter = 'all';
    let searchQuery = '';

    const els = {
        container: document.getElementById('trolleys-container'),
        filterButtons: document.querySelectorAll('#filter-container .btn'),
        searchBar: document.getElementById('trolley-search'),
        statOnline: document.getElementById('stat-online-count'),
        statTotal: document.getElementById('stat-total-count'),
        statBattery: document.getElementById('stat-avg-battery'),
        statActive: document.getElementById('stat-active-count'),

        // Modal Elements
        addBtn: document.getElementById('add-trolley-btn'),
        modal: document.getElementById('trolley-modal'),
        form: document.getElementById('trolley-form'),
        trolleyId: document.getElementById('modal-trolley-id'),
        trolleyName: document.getElementById('modal-trolley-name'),
        trolleySection: document.getElementById('modal-trolley-section'),
        trolleyFw: document.getElementById('modal-trolley-fw'),
        cancelBtn: document.getElementById('modal-trolley-cancel'),
        submitBtn: document.getElementById('modal-trolley-submit')
    };

    // ── Fetch & render ──────────────────────────────────────────────────────
    async function fetchTrolleys() {
        try {
            const res = await fetch('/api/trolleys');
            if (res.ok) {
                allTrolleys = await res.json();
                updateSummaryStats();
                renderTrolleys();
            }
        } catch (e) {
            console.error("Failed to fetch trolleys:", e);
        }
    }

    // ── Summary stat bar ────────────────────────────────────────────────────
    function updateSummaryStats() {
        const online = allTrolleys.filter(t => t.status === 'online').length;
        const active = allTrolleys.filter(t => t.item_count > 0).length;
        const battAvg = allTrolleys.length
            ? Math.round(allTrolleys.reduce((s, t) => s + (t.battery || 0), 0) / allTrolleys.length)
            : 0;

        if (els.statOnline) els.statOnline.textContent = online;
        if (els.statTotal) els.statTotal.textContent = allTrolleys.length;
        if (els.statBattery) els.statBattery.textContent = battAvg + '%';
        if (els.statActive) els.statActive.textContent = active;
    }

    // ── Render trolley cards ────────────────────────────────────────────────
    function renderTrolleys() {
        if (!els.container) return;

        // Filter
        let filtered = allTrolleys;
        if (activeFilter === 'online') {
            filtered = filtered.filter(t => t.status === 'online' || t.connection_status === 'connected');
        } else if (activeFilter === 'offline') {
            filtered = filtered.filter(t => t.status !== 'online' && t.connection_status !== 'connected');
        } else if (activeFilter === 'available') {
            filtered = filtered.filter(t => t.assignment_status !== 'ASSIGNED');
        } else if (activeFilter === 'assigned') {
            filtered = filtered.filter(t => t.assignment_status === 'ASSIGNED');
        }

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(t =>
                t.id.toLowerCase().includes(q) ||
                (t.name || '').toLowerCase().includes(q) ||
                (t.assigned_customer_name || '').toLowerCase().includes(q) ||
                (t.assigned_customer_id || '').toLowerCase().includes(q) ||
                (t.assigned_customer_phone || '').toLowerCase().includes(q)
            );
        }

        els.container.innerHTML = '';

        if (filtered.length === 0) {
            els.container.innerHTML = `
                <div class="glass-panel" style="grid-column:1/-1;padding:40px;text-align:center;color:var(--text-secondary);">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size:2rem;margin-bottom:12px;color:var(--accent-cyan);"></i>
                    <p>No trolleys match the current filters or search terms.</p>
                </div>`;
            return;
        }

        filtered.forEach(t => buildTrolleyCard(t));
    }

    function buildTrolleyCard(t) {
        const isOnline = t.status === 'online' || t.connection_status === 'connected';
        const isAssigned = t.assignment_status === 'ASSIGNED';
        const statusLabel = isOnline ? 'Connected' : 'Offline';
        const statusClass = isOnline ? 'active' : 'offline';

        const assignBadge = isAssigned ?
            `<span class="trolley-status-badge" style="background:rgba(168,85,247,0.2);color:#c084fc;border:1px solid rgba(168,85,247,0.4);font-size:0.72rem;"><i class="fa-solid fa-user-check" style="margin-right:4px;"></i>Assigned</span>` :
            `<span class="trolley-status-badge" style="background:rgba(59,130,246,0.15);color:#93c5fd;border:1px solid rgba(59,130,246,0.3);font-size:0.72rem;"><i class="fa-solid fa-user-clock" style="margin-right:4px;"></i>Available</span>`;

        // Battery icon & color
        let batteryIcon = 'fa-battery-full';
        let batteryColor = 'var(--accent-green)';
        const batt = t.battery || 0;
        if (batt < 20) {
            batteryIcon = 'fa-battery-empty';
            batteryColor = 'var(--accent-red)';
        } else if (batt < 50) {
            batteryIcon = 'fa-battery-quarter';
            batteryColor = '#f59e0b';
        } else if (batt < 75) {
            batteryIcon = 'fa-battery-half';
            batteryColor = '#eab308';
        }

        // RSSI signal display
        const rssi = t.wifi_rssi || 0;
        let rssiLabel = 'N/A';
        let rssiColor = 'var(--text-secondary)';
        if (rssi !== 0) {
            rssiLabel = rssi + ' dBm';
            rssiColor = rssi >= -65 ? 'var(--accent-green)' : (rssi >= -80 ? '#f59e0b' : 'var(--accent-red)');
        }

        // Cart status badge
        const cartStatus = t.cart_status || 'ACTIVE';
        let cartBadge = '';
        if (cartStatus === 'BILL_GENERATED') {
            cartBadge = `<span class="trolley-status-badge idle" style="font-size:0.7rem;margin-left:4px;">Bill Pending</span>`;
        }

        const heartbeatDisplay = t.last_heartbeat_display || (t.last_seen_24h ? `${t.last_seen_24h} (${t.last_seen_relative})` : (t.last_seen_str || 'Never'));

        let customerBlock = '';
        if (isAssigned) {
            customerBlock = `
                <div class="trolley-stat-row" style="background:rgba(168,85,247,0.08);padding:6px 10px;border-radius:6px;border-left:3px solid #a855f7;margin:4px 0;">
                    <span style="color:#c084fc;font-weight:600;"><i class="fa-solid fa-user" style="margin-right:5px;"></i>Shopper</span>
                    <span class="trolley-stat-value" style="font-weight:600;color:#fff;">${t.assigned_customer_name || 'Customer'} <small style="color:var(--text-secondary);">(${t.assigned_customer_id})</small></span>
                </div>
                ${t.assigned_customer_phone ? `
                <div class="trolley-stat-row">
                    <span>Mobile</span>
                    <span class="trolley-stat-value">${t.assigned_customer_phone}</span>
                </div>` : ''}
            `;
        }

        let assignActionBtn = isAssigned ?
            `<button class="btn btn-outline unassign-trolley-btn" data-id="${t.id}" title="Unassign Customer" style="flex:1.2;font-size:0.8rem;padding:6px 0;border-color:rgba(239,68,68,0.4);color:#f87171;cursor:pointer;"><i class="fa-solid fa-user-xmark" style="margin-right:4px;"></i>Unassign</button>` :
            `<button class="btn btn-outline assign-trolley-btn" data-id="${t.id}" title="Assign Customer" style="flex:1.2;font-size:0.8rem;padding:6px 0;border-color:rgba(168,85,247,0.4);color:#c084fc;cursor:pointer;"><i class="fa-solid fa-user-plus" style="margin-right:4px;"></i>Assign</button>`;

        const card = document.createElement('div');
        card.className = 'card glass-panel gradient-border';
        card.style.flexDirection = 'column';
        card.style.alignItems = 'stretch';
        card.style.gap = '10px';

        card.innerHTML = `
            <div class="trolley-details-header">
                <strong style="font-size:1.1rem;color:var(--text-primary);">
                    <i class="fa-solid fa-cart-shopping" style="margin-right:8px;"></i>${t.id}
                </strong>
                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                    <span class="trolley-status-badge ${statusClass}">
                        <span class="pulse-dot" style="background:${isOnline ? 'var(--accent-green)' : 'var(--accent-red)'};width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px;${isOnline ? 'box-shadow:0 0 5px var(--accent-green);animation:pulse 1.5s infinite;' : ''}"></span>
                        ${statusLabel}
                    </span>
                    ${assignBadge}
                    ${cartBadge}
                </div>
            </div>

            ${customerBlock}

            <div class="trolley-stat-row">
                <span>Trolley Name</span>
                <span class="trolley-stat-value">${t.name || t.id}</span>
            </div>
            <div class="trolley-stat-row">
                <span>Cart Items</span>
                <span class="trolley-stat-value">${t.item_count || 0} units</span>
            </div>
            <div class="trolley-stat-row">
                <span>Cart Value</span>
                <span class="trolley-stat-value" style="color:var(--accent-green);font-weight:600;">
                    Rs.${(t.cart_value || 0).toFixed(2)}
                </span>
            </div>
            <div class="trolley-stat-row">
                <span>Battery</span>
                <span class="trolley-stat-value" style="color:${batteryColor}">
                    <i class="fa-solid ${batteryIcon}" style="margin-right:6px;"></i>${batt}%
                </span>
            </div>
            <div class="trolley-stat-row">
                <span>Wi-Fi Signal</span>
                <span class="trolley-stat-value" style="color:${rssiColor}">${rssiLabel}</span>
            </div>
            <div class="trolley-stat-row">
                <span>IP Address</span>
                <span class="trolley-stat-value" style="font-family:monospace;font-size:0.82rem;">
                    ${t.ip_address || '—'}
                </span>
            </div>
            <div class="trolley-stat-row">
                <span><i class="fa-regular fa-clock" style="margin-right:4px;"></i>Last Heartbeat</span>
                <span class="trolley-stat-value" style="font-family:monospace;font-size:0.78rem;">${heartbeatDisplay}</span>
            </div>

            <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;">
                ${assignActionBtn}
                <a href="trolley-monitor.html?id=${t.id}" class="btn btn-outline"
                   style="flex:1.5;text-align:center;font-size:0.8rem;padding:6px 0;text-decoration:none;">
                    <i class="fa-solid fa-desktop" style="margin-right:6px;"></i>Monitor
                </a>
                <button class="btn btn-danger delete-trolley-btn" data-id="${t.id}" title="Remove Trolley from Fleet"
                   style="width:36px;font-size:0.8rem;padding:6px 0;">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>`;

        els.container.appendChild(card);
    }

    // Delegate delete trolley action
    if (els.container) {
        els.container.addEventListener('click', async (e) => {
            const delBtn = e.target.closest('.delete-trolley-btn');
            if (delBtn) {
                const tid = delBtn.getAttribute('data-id');
                if (confirm(`Are you sure you want to remove "${tid}" from the active fleet?`)) {
                    try {
                        const res = await fetch(`/api/trolleys/${encodeURIComponent(tid)}`, {
                            method: 'DELETE'
                        });
                        const data = await res.json();
                        if (res.ok && data.success) {
                            if (window.showToast) {
                                window.showToast("Trolley Removed", data.message || `Removed ${tid}.`, "info");
                            }
                            await fetchTrolleys();
                        } else {
                            alert(data.message || "Failed to remove trolley.");
                        }
                    } catch (err) {
                        console.error("Delete trolley error:", err);
                        alert("Unable to reach server to delete trolley.");
                    }
                }
                return;
            }

            const assignBtn = e.target.closest('.assign-trolley-btn');
            if (assignBtn) {
                const tid = assignBtn.getAttribute('data-id');
                openCustAssignModal(tid);
                return;
            }

            const unassignBtn = e.target.closest('.unassign-trolley-btn');
            if (unassignBtn) {
                const tid = unassignBtn.getAttribute('data-id');
                if (confirm(`Unassign customer from ${tid} and release trolley back to AVAILABLE?`)) {
                    try {
                        const res = await fetch(`/api/trolleys/${encodeURIComponent(tid)}/unassign`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        });
                        const data = await res.json();
                        if (res.ok && data.success) {
                            if (window.showToast) window.showToast("Trolley Released", data.message, "info");
                            await fetchTrolleys();
                        } else {
                            alert(data.message || "Failed to unassign trolley.");
                        }
                    } catch (err) {
                        console.error("Unassign error:", err);
                        alert("Network error unassigning trolley.");
                    }
                }
                return;
            }
        });
    }

    // ── Modal Handling ──────────────────────────────────────────────────────
    function openModal() {
        if (!els.modal) return;
        els.trolleyId.value = '';
        els.trolleyName.value = '';
        if (els.trolleyFw) els.trolleyFw.value = '2.0';
        els.modal.classList.add('active');
        setTimeout(() => els.trolleyId.focus(), 100);
    }

    function closeModal() {
        if (els.modal) els.modal.classList.remove('active');
    }

    if (els.addBtn) els.addBtn.addEventListener('click', openModal);
    if (els.cancelBtn) els.cancelBtn.addEventListener('click', closeModal);

    if (els.modal) {
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeModal();
        });
    }

    // Auto-fill friendly name as ID is typed
    if (els.trolleyId && els.trolleyName) {
        els.trolleyId.addEventListener('input', () => {
            const raw = els.trolleyId.value.trim().toUpperCase();
            if (raw.startsWith('TROLLEY-') || raw.startsWith('TROLLEY')) {
                const num = raw.replace(/\D/g, '');
                if (num && !els.trolleyName.dataset.userEdited) {
                    els.trolleyName.value = `Smart Trolley ${num.padStart(3, '0')}`;
                }
            }
        });
        els.trolleyName.addEventListener('input', () => {
            els.trolleyName.dataset.userEdited = 'true';
        });
    }

    // Handle Form Submit
    if (els.form) {
        els.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const tid = els.trolleyId.value.trim().toUpperCase();
            const name = els.trolleyName.value.trim() || tid;
            const section = els.trolleySection ? els.trolleySection.value : 'General';
            const fw = els.trolleyFw ? els.trolleyFw.value.trim() : '2.0';

            if (!tid) {
                alert("Please specify a Trolley ID (e.g. TROLLEY-004).");
                return;
            }

            try {
                const res = await fetch('/api/trolleys', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trolley_id: tid,
                        name: name,
                        section: section,
                        firmware_version: fw
                    })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    closeModal();
                    if (window.showToast) {
                        window.showToast("Trolley Registered", `Added ${tid} (${name}) to active fleet.`, "success");
                    }
                    await fetchTrolleys();
                } else {
                    alert(data.message || "Failed to register trolley.");
                }
            } catch (err) {
                console.error("Save trolley error:", err);
                alert("Unable to reach server to save trolley.");
            }
        });
    }

    // ── Customer Assignment Modal Handling ──────────────────────────────────
    let custAssignTab = 'existing';
    const custAssignModal = document.getElementById('customer-assign-modal');
    const openCustAssignModalBtn = document.getElementById('open-cust-assign-modal-btn');
    const custAssignCancelBtn = document.getElementById('customer-assign-cancel');
    const custAssignForm = document.getElementById('customer-assign-form');
    const tabExisting = document.getElementById('tab-assign-existing');
    const tabNew = document.getElementById('tab-assign-new');

    function switchCustTab(tab) {
        custAssignTab = tab;
        const secExisting = document.getElementById('section-assign-existing');
        const secNew = document.getElementById('section-assign-new');
        const submitBtn = document.getElementById('customer-assign-submit');

        if (tab === 'existing') {
            if (tabExisting) { tabExisting.style.background = 'var(--grad-primary)'; tabExisting.style.color = '#fff'; }
            if (tabNew) { tabNew.style.background = 'transparent'; tabNew.style.color = 'var(--text-secondary)'; }
            if (secExisting) secExisting.style.display = 'block';
            if (secNew) secNew.style.display = 'none';
            if (submitBtn) submitBtn.innerHTML = '<i class="fa-solid fa-link"></i> Confirm Assignment';
        } else {
            if (tabNew) { tabNew.style.background = 'var(--grad-primary)'; tabNew.style.color = '#fff'; }
            if (tabExisting) { tabExisting.style.background = 'transparent'; tabExisting.style.color = 'var(--text-secondary)'; }
            if (secExisting) secExisting.style.display = 'none';
            if (secNew) secNew.style.display = 'block';
            if (submitBtn) submitBtn.innerHTML = '<i class="fa-solid fa-user-plus"></i> Register & Assign';
        }
    }

    if (tabExisting && tabNew) {
        tabExisting.addEventListener('click', () => switchCustTab('existing'));
        tabNew.addEventListener('click', () => switchCustTab('new'));
    }

    async function openCustAssignModal(preselectedId) {
        if (!custAssignModal) return;
        const alertBox = document.getElementById('assign-error-alert');
        if (alertBox) alertBox.style.display = 'none';

        // Populate trolleys in select
        const trolleySel = document.getElementById('modal-assign-trolley-select');
        if (trolleySel) {
            trolleySel.innerHTML = allTrolleys.map(t => {
                const isSel = (preselectedId && t.id === preselectedId) ? 'selected' : '';
                const tag = t.assigned_customer_name ? ` (Assigned: ${t.assigned_customer_name})` : ' (Available)';
                return `<option value="${t.id}" ${isSel}>${t.id}${tag}</option>`;
            }).join('');
            if (preselectedId) trolleySel.value = preselectedId;
        }

        // Populate registered customers
        const custSel = document.getElementById('modal-assign-customer-select');
        if (custSel) {
            try {
                const res = await fetch('/api/customers');
                if (res.ok) {
                    const custs = await res.json();
                    custSel.innerHTML = '<option value="">-- Choose Registered Customer --</option>' +
                        custs.map(c => `<option value="${c.id}">${c.name} (${c.phone || c.email || 'No phone'}) - ${c.id}${c.assigned_trolley ? ` [Has ${c.assigned_trolley}]` : ''}</option>`).join('');
                }
            } catch (err) {
                console.error("Load customers error:", err);
            }
        }

        // Clear new customer inputs
        const nameIn = document.getElementById('modal-new-cust-name');
        const phoneIn = document.getElementById('modal-new-cust-phone');
        const emailIn = document.getElementById('modal-new-cust-email');
        const idIn = document.getElementById('modal-new-cust-id');
        if (nameIn) nameIn.value = '';
        if (phoneIn) phoneIn.value = '';
        if (emailIn) emailIn.value = '';
        if (idIn) idIn.value = '';

        switchCustTab('existing');
        custAssignModal.classList.add('active');
        custAssignModal.style.display = 'flex';
    }

    function closeCustAssignModal() {
        if (custAssignModal) {
            custAssignModal.classList.remove('active');
            custAssignModal.style.display = 'none';
        }
    }

    if (openCustAssignModalBtn) openCustAssignModalBtn.addEventListener('click', () => openCustAssignModal());
    if (custAssignCancelBtn) custAssignCancelBtn.addEventListener('click', closeCustAssignModal);
    if (custAssignModal) {
        custAssignModal.addEventListener('click', (e) => {
            if (e.target === custAssignModal) closeCustAssignModal();
        });
    }

    if (custAssignForm) {
        custAssignForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const alertBox = document.getElementById('assign-error-alert');
            const alertText = document.getElementById('assign-error-text');
            if (alertBox) alertBox.style.display = 'none';

            const trolleySel = document.getElementById('modal-assign-trolley-select');
            const trolleyId = trolleySel ? trolleySel.value : '';
            let customerIdToAssign = '';

            if (custAssignTab === 'existing') {
                const custSel = document.getElementById('modal-assign-customer-select');
                customerIdToAssign = custSel ? custSel.value : '';
                if (!customerIdToAssign) {
                    if (alertBox && alertText) {
                        alertText.textContent = "Please select a registered customer or switch to '+ New Customer'.";
                        alertBox.style.display = 'block';
                    }
                    return;
                }
            } else {
                const name = (document.getElementById('modal-new-cust-name')?.value || '').trim();
                const phone = (document.getElementById('modal-new-cust-phone')?.value || '').trim();
                const email = (document.getElementById('modal-new-cust-email')?.value || '').trim();
                const custId = (document.getElementById('modal-new-cust-id')?.value || '').trim().toUpperCase();

                if (!name || !phone) {
                    if (alertBox && alertText) {
                        alertText.textContent = "Customer Name and Mobile Number are required.";
                        alertBox.style.display = 'block';
                    }
                    return;
                }

                try {
                    const regRes = await fetch('/api/customers', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, phone, email, customer_id: custId })
                    });
                    const regData = await regRes.json();
                    if (!regRes.ok || !regData.success) {
                        if (alertBox && alertText) {
                            alertText.textContent = regData.message || "Failed to register customer.";
                            alertBox.style.display = 'block';
                        }
                        return;
                    }
                    customerIdToAssign = regData.customer ? regData.customer.id : custId;
                } catch (err) {
                    if (alertBox && alertText) {
                        alertText.textContent = "Network error registering customer.";
                        alertBox.style.display = 'block';
                    }
                    return;
                }
            }

            try {
                const assignRes = await fetch(`/api/trolleys/${encodeURIComponent(trolleyId)}/assign`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ customer_id: customerIdToAssign })
                });
                const assignData = await assignRes.json();
                if (!assignRes.ok || !assignData.success) {
                    if (alertBox && alertText) {
                        alertText.textContent = assignData.message || "Failed to assign trolley.";
                        alertBox.style.display = 'block';
                    }
                    return;
                }

                closeCustAssignModal();
                if (window.showToast) window.showToast("Trolley Assigned", assignData.message, "success");
                await fetchTrolleys();
            } catch (err) {
                if (alertBox && alertText) {
                    alertText.textContent = "Network error assigning trolley.";
                    alertBox.style.display = 'block';
                }
            }
        });
    }

    // ── Filter buttons ──────────────────────────────────────────────────────
    els.filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            els.filterButtons.forEach(b => b.classList.remove('active-filter', 'active'));
            btn.classList.add('active');
            activeFilter = btn.getAttribute('data-filter');
            renderTrolleys();
        });
    });

    // ── Search bar ──────────────────────────────────────────────────────────
    if (els.searchBar) {
        els.searchBar.addEventListener('input', e => {
            searchQuery = e.target.value;
            renderTrolleys();
        });
    }

    // ── Init & polling ──────────────────────────────────────────────────────
    fetchTrolleys();
    setInterval(fetchTrolleys, 3000);
});
