/**
 * Customer Member Portal Logic - Integrated with MongoDB Customer Sessions,
 * Live Smart Trolley Sync, Inventory Catalog, and Invoices.
 */

let currentCustomerId = null;
let activePollingTimer = null;
let currentRating = 5;
let allCatalogProducts = [];

document.addEventListener('DOMContentLoaded', () => {
    const els = {
        customerSelect: document.getElementById('portal-customer-select'),
        regModalBtn: document.getElementById('portal-register-modal-btn'),
        regModal: document.getElementById('portal-register-modal'),
        closeRegModal: document.getElementById('portal-close-reg-modal'),
        cancelRegBtn: document.getElementById('portal-cancel-reg-btn'),
        regForm: document.getElementById('portal-reg-form'),

        feedbackModalBtn: document.getElementById('portal-open-feedback-btn'),
        feedbackModal: document.getElementById('portal-feedback-modal'),
        closeFeedbackModal: document.getElementById('portal-close-feedback-modal'),
        cancelFeedbackBtn: document.getElementById('portal-cancel-feedback-btn'),
        feedbackForm: document.getElementById('portal-feedback-form'),
        starRatingBox: document.getElementById('star-rating-box'),
        starRatingText: document.getElementById('star-rating-text'),

        logoutBtn: document.getElementById('portal-logout-btn'),
        loginNavBtn: document.getElementById('portal-login-nav-btn'),
        userProfile: document.getElementById('portal-user-profile'),
        avatarImg: document.getElementById('portal-avatar-img'),
        headerUsername: document.getElementById('portal-header-username'),

        // Profile DOMs
        profileAvatar: document.getElementById('portal-profile-avatar'),
        name: document.getElementById('portal-name'),
        custIdBadge: document.getElementById('portal-cust-id-badge'),
        tier: document.getElementById('portal-tier'),
        points: document.getElementById('portal-points'),
        totalSpent: document.getElementById('portal-total-spent'),
        totalVisits: document.getElementById('portal-total-visits'),
        email: document.getElementById('portal-email'),
        phone: document.getElementById('portal-phone'),
        sidebarTrolleyBadge: document.getElementById('portal-sidebar-trolley-badge'),

        // Active Trolley DOMs
        trolleyIdPill: document.getElementById('portal-trolley-id-pill'),
        trolleyConnBadge: document.getElementById('portal-trolley-conn-badge'),
        activeTrolleyContent: document.getElementById('portal-active-trolley-content'),

        // Wishlist & Catalog DOMs
        wishlistCount: document.getElementById('wishlist-count'),
        wishlistContainer: document.getElementById('portal-wishlist-container'),
        catalogGrid: document.getElementById('portal-catalog-grid'),
        catalogSearch: document.getElementById('portal-catalog-search'),
        catalogCategory: document.getElementById('portal-catalog-category'),

        // Receipts
        receiptsBody: document.getElementById('portal-receipts-body')
    };

    // Initialize the member portal
    initPortal();

    async function initPortal() {
        setupAuthHeader();
        await loadCustomerList();
        setupEventListeners();
        await loadCatalog();
        startRealtimePolling();
    }

    function isCurrentGuestSession() {
        const loggedIn = window.isAuthenticated ? window.isAuthenticated() : false;
        const authUser = window.getAuthUser ? window.getAuthUser() : null;
        return !loggedIn || !authUser || authUser.role === 'guest' || authUser.username === 'guest';
    }

    function setupAuthHeader() {
        const isGuest = isCurrentGuestSession();
        const authUser = window.getAuthUser ? window.getAuthUser() : null;

        if (!isGuest && authUser) {
            if (els.logoutBtn) els.logoutBtn.style.display = 'inline-flex';
            if (els.loginNavBtn) els.loginNavBtn.style.display = 'none';
            if (els.headerUsername) els.headerUsername.textContent = authUser.name || authUser.username;
            if (els.avatarImg) {
                els.avatarImg.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(authUser.name || authUser.username)}&background=06b6d4&color=fff`;
            }
        } else {
            if (els.logoutBtn) els.logoutBtn.style.display = 'none';
            if (els.loginNavBtn) els.loginNavBtn.style.display = 'inline-flex';
            if (els.headerUsername) els.headerUsername.textContent = 'Guest Shopper';
            if (els.avatarImg) {
                els.avatarImg.src = `https://ui-avatars.com/api/?name=Guest+Shopper&background=64748b&color=fff`;
            }
        }
    }

    async function loadCustomerList(preselectId = null) {
        const isGuest = isCurrentGuestSession();
        const authUser = window.getAuthUser ? window.getAuthUser() : null;

        try {
            const res = await fetch('/api/customers');
            let customers = [];
            if (res.ok) {
                customers = await res.json();
            }

            if (els.customerSelect) {
                els.customerSelect.innerHTML = '';

                // Guest Option (Always top)
                const guestOpt = document.createElement('option');
                guestOpt.value = 'guest';
                guestOpt.textContent = '🛒 Guest Shopper (Current Session)';
                els.customerSelect.appendChild(guestOpt);

                if (customers.length > 0) {
                    const group = document.createElement('optgroup');
                    group.label = '── Registered Members ──';
                    customers.forEach(c => {
                        const opt = document.createElement('option');
                        opt.value = c.id || c.customer_id;
                        const trolleyTag = c.assigned_trolley ? ` [${c.assigned_trolley}]` : '';
                        opt.textContent = `${c.name} (${c.id || c.customer_id})${trolleyTag}`;
                        group.appendChild(opt);
                    });
                    els.customerSelect.appendChild(group);
                }

                // Determine active customer ID
                if (preselectId) {
                    currentCustomerId = preselectId;
                    els.customerSelect.value = preselectId;
                } else if (isGuest) {
                    currentCustomerId = 'guest';
                    els.customerSelect.value = 'guest';
                } else if (authUser && authUser.role === 'customer') {
                    // Match logged in registered customer
                    const matched = customers.find(c => 
                        (authUser.email && c.email && c.email.toLowerCase() === authUser.email.toLowerCase()) ||
                        (authUser.name && c.name && c.name.toLowerCase() === authUser.name.toLowerCase()) ||
                        (authUser.phone && c.phone && c.phone === authUser.phone) ||
                        (authUser.username && c.id && c.id.toLowerCase() === authUser.username.toLowerCase())
                    );
                    if (matched) {
                        currentCustomerId = matched.id || matched.customer_id;
                    } else if (customers.length > 0) {
                        currentCustomerId = customers[0].id || customers[0].customer_id;
                    } else {
                        currentCustomerId = 'guest';
                    }
                    els.customerSelect.value = currentCustomerId;
                } else if (currentCustomerId) {
                    els.customerSelect.value = currentCustomerId;
                } else {
                    currentCustomerId = isGuest ? 'guest' : (customers.length > 0 ? (customers[0].id || customers[0].customer_id) : 'guest');
                    els.customerSelect.value = currentCustomerId;
                }

                await loadProfileData(currentCustomerId);
            }
        } catch (e) {
            console.error("Failed to load customer list:", e);
            if (isGuest) {
                currentCustomerId = 'guest';
                await loadProfileData('guest');
            }
        }
    }

    async function loadProfileData(customerId, isBackgroundPoll = false) {
        if (!customerId) customerId = 'guest';

        if (customerId === 'guest') {
            try {
                const res = await fetch('/api/customer/profile?customer_id=guest');
                if (res.ok) {
                    const data = await res.json();
                    renderProfile(data.customer);
                    renderActiveTrolley(data.active_trolley);
                    renderWishlist(getGuestWishlist());
                    renderReceipts(data.recent_transactions || []);
                    return;
                }
            } catch (e) {
                if (!isBackgroundPoll) console.error("Failed to load guest profile from server:", e);
            }
            renderProfile({
                id: 'GUEST',
                customer_id: 'GUEST',
                name: 'Guest Shopper',
                phone: '',
                email: '',
                tier: 'Guest Access',
                points: 0,
                total_spent: 0.0,
                total_visits: 1,
                status: 'Guest',
                assigned_trolley: null,
                is_guest: true
            });
            renderWishlist(getGuestWishlist());
            renderReceipts([]);
            return;
        }

        try {
            const res = await fetch(`/api/customer/profile?customer_id=${encodeURIComponent(customerId)}`);
            if (res.ok) {
                const data = await res.json();
                renderProfile(data.customer);
                renderActiveTrolley(data.active_trolley);
                renderWishlist(data.customer.wishlist || []);
                renderReceipts(data.recent_transactions || []);
            }
        } catch (e) {
            if (!isBackgroundPoll) {
                console.error("Failed to load customer profile:", e);
            }
        }
    }

    function renderProfile(cust) {
        if (!cust) return;

        const isGuest = cust.is_guest || cust.id === 'GUEST' || cust.id === 'guest' || cust.role === 'guest' || currentCustomerId === 'guest';

        if (els.name) els.name.textContent = isGuest ? 'Guest Shopper' : (cust.name || 'Valued Shopper');
        if (els.custIdBadge) els.custIdBadge.textContent = isGuest ? 'Guest Session' : `ID: ${cust.id || cust.customer_id || 'N/A'}`;
        if (els.email) els.email.textContent = isGuest ? 'Guest Session' : (cust.email || 'None');
        if (els.phone) els.phone.textContent = isGuest ? 'Not Registered' : (cust.phone ? `+91 ${cust.phone.replace(/^\+?91/, '')}` : 'Not registered');

        if (els.profileAvatar) {
            const avatarBg = isGuest ? '64748b' : '06b6d4';
            const avatarName = isGuest ? 'Guest Shopper' : (cust.name || 'User');
            els.profileAvatar.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(avatarName)}&background=${avatarBg}&color=fff&size=128`;
        }

        // Tier
        if (els.tier) {
            if (isGuest) {
                els.tier.className = 'tier-badge';
                els.tier.style.background = 'rgba(148, 163, 184, 0.2)';
                els.tier.style.color = '#94a3b8';
                els.tier.style.border = '1px solid rgba(148, 163, 184, 0.3)';
                els.tier.innerHTML = `<i class="fa-solid fa-user"></i> Guest Access`;
            } else {
                els.tier.style.background = '';
                els.tier.style.border = '';
                const tierStr = cust.tier || 'Bronze Member';
                let tierClass = 'tier-bronze';
                let icon = 'fa-medal';

                if (tierStr.includes('Silver')) {
                    tierClass = 'tier-silver';
                    icon = 'fa-shield-halved';
                } else if (tierStr.includes('Gold')) {
                    tierClass = 'tier-gold';
                    icon = 'fa-crown';
                } else if (tierStr.includes('Platinum')) {
                    tierClass = 'tier-platinum';
                    icon = 'fa-gem';
                }

                els.tier.className = `tier-badge ${tierClass}`;
                els.tier.innerHTML = `<i class="fa-solid ${icon}"></i> ${tierStr}`;
            }
        }

        // Points
        if (els.points) {
            if (isGuest) {
                els.points.innerHTML = `<i class="fa-solid fa-award"></i> 0 Points <span style="font-size:0.75rem; font-weight:normal; opacity:0.8;">(Sign in to earn)</span>`;
            } else {
                els.points.innerHTML = `<i class="fa-solid fa-award"></i> ${(cust.points || 0).toLocaleString()} Points`;
            }
        }

        // Lifetime stats
        if (els.totalSpent) {
            const spent = isGuest ? 0 : Number(cust.total_spent || 0);
            els.totalSpent.textContent = `₹${spent.toFixed(2)}`;
        }
        if (els.totalVisits) {
            els.totalVisits.textContent = isGuest ? 1 : (cust.total_visits || 0);
        }

        // Sidebar Trolley Badge
        if (els.sidebarTrolleyBadge) {
            if (cust.assigned_trolley) {
                els.sidebarTrolleyBadge.className = 'trolley-status-badge assigned';
                els.sidebarTrolleyBadge.textContent = cust.assigned_trolley;
            } else {
                els.sidebarTrolleyBadge.className = 'trolley-status-badge available';
                els.sidebarTrolleyBadge.textContent = 'None Assigned';
            }
        }

        // Guest CTA Banner
        const guestCta = document.getElementById('portal-guest-cta');
        if (guestCta) {
            guestCta.style.display = isGuest ? 'block' : 'none';
        }
    }

    async function renderActiveTrolley(activeTrolley) {
        if (!els.activeTrolleyContent) return;

        if (activeTrolley) {
            // Trolley is assigned to this customer
            if (els.trolleyIdPill) {
                els.trolleyIdPill.style.display = 'inline-block';
                els.trolleyIdPill.textContent = activeTrolley.trolley_id;
            }

            if (els.trolleyConnBadge) {
                if (activeTrolley.is_connected) {
                    els.trolleyConnBadge.className = 'trolley-status-badge active';
                    els.trolleyConnBadge.innerHTML = `<i class="fa-solid fa-wifi"></i> Hardware Online`;
                } else {
                    els.trolleyConnBadge.className = 'trolley-status-badge maintenance';
                    els.trolleyConnBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Disconnected (Session Preserved)`;
                }
            }

            const isAddMode = (activeTrolley.current_mode || 'ADD') === 'ADD';
            const modeBadgeHtml = isAddMode 
                ? `<span style="background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;"><i class="fa-solid fa-plus-circle"></i> ADD ITEM MODE</span>`
                : `<span style="background: rgba(239, 68, 68, 0.15); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.8rem;"><i class="fa-solid fa-minus-circle"></i> REMOVE ITEM MODE</span>`;

            const disconnectWarningHtml = !activeTrolley.is_connected ? `
                <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; font-size: 0.82rem; color: #fde68a; display: flex; align-items: center; gap: 10px;">
                    <i class="fa-solid fa-shield-halved" style="font-size: 1.1rem; color: #f59e0b;"></i>
                    <div>
                        <strong>Cart Protected:</strong> Trolley hardware is currently offline or rebooting. Disconnecting, Wi-Fi loss, or reboot does <em>not</em> reset your cart. Your items and session remain 100% saved in MongoDB.
                    </div>
                </div>
            ` : '';

            let itemsTableHtml = '';
            const items = activeTrolley.items || [];

            if (items.length === 0) {
                itemsTableHtml = `
                    <div style="text-align: center; padding: 32px 16px; color: var(--text-secondary); background: rgba(255, 255, 255, 0.02); border-radius: 8px; border: 1px dashed var(--panel-border);">
                        <i class="fa-solid fa-cart-arrow-down" style="font-size: 2.2rem; color: var(--accent-cyan); opacity: 0.5; margin-bottom: 12px; display: block;"></i>
                        <h4 style="margin: 0 0 6px 0; color: var(--text-primary); font-size: 1rem;">Cart is currently empty</h4>
                        <p style="margin: 0; font-size: 0.82rem;">Scan any item RFID card near <strong>${activeTrolley.trolley_id}</strong> scanner to add it to your live session.</p>
                    </div>
                `;
            } else {
                let rowsHtml = '';
                items.forEach((item, index) => {
                    const offerTag = item.offer && item.offer !== 'Standard Price' && item.offer !== 'No Active Offers'
                        ? `<span style="background: rgba(6, 182, 212, 0.15); color: var(--accent-cyan); padding: 2px 6px; border-radius: 4px; font-size: 0.72rem; margin-left: 6px;"><i class="fa-solid fa-tag"></i> ${item.offer}</span>`
                        : '';

                    rowsHtml += `
                        <tr>
                            <td style="font-weight: 500;">
                                ${index + 1}. ${item.name}
                                ${offerTag}
                            </td>
                            <td style="color: var(--text-secondary);">₹${Number(item.price || 0).toFixed(2)}</td>
                            <td style="text-align: center; font-weight: 700;">${item.quantity}</td>
                            <td style="text-align: right; color: var(--accent-green); font-weight: 700;">₹${Number(item.subtotal || 0).toFixed(2)}</td>
                        </tr>
                    `;
                });

                itemsTableHtml = `
                    <div class="table-responsive" style="margin-top: 10px;">
                        <table class="cart-table">
                            <thead>
                                <tr>
                                    <th>Item Description</th>
                                    <th>Unit Price</th>
                                    <th style="text-align: center;">Qty</th>
                                    <th style="text-align: right;">Line Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${rowsHtml}
                            </tbody>
                        </table>
                    </div>

                    <!-- Cart Running Bill Breakdown -->
                    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--panel-border); border-radius: 8px; padding: 14px 18px; margin-top: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
                        <div style="font-size: 0.82rem; color: var(--text-secondary);">
                            <div><strong>Items in Cart:</strong> ${activeTrolley.items_count} item(s)</div>
                            <div><strong>Cart Status:</strong> <span style="color: var(--accent-cyan); font-weight: 600;">${activeTrolley.cart_status}</span></div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.85rem; color: var(--text-secondary);">Subtotal: ₹${Number(activeTrolley.subtotal || 0).toFixed(2)}</div>
                            <div style="font-size: 0.85rem; color: var(--text-secondary);">GST (18%): ₹${Number(activeTrolley.gst || 0).toFixed(2)}</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: var(--accent-green); margin-top: 4px;">
                                Total: ₹${Number(activeTrolley.grand_total || 0).toFixed(2)}
                            </div>
                        </div>
                    </div>
                `;
            }

            els.activeTrolleyContent.innerHTML = `
                <div class="active-cart-panel ${activeTrolley.is_connected ? 'connected' : 'disconnected'}" style="padding: 18px;">
                    <!-- Trolley Metadata Bar -->
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid var(--panel-border);">
                        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                            <span style="font-weight: 700; font-size: 1rem; color: var(--accent-cyan); font-family: monospace;">
                                <i class="fa-solid fa-microchip"></i> ${activeTrolley.trolley_name}
                            </span>
                            ${modeBadgeHtml}
                            <span style="font-size: 0.8rem; color: var(--text-secondary);">
                                <i class="fa-solid fa-battery-three-quarters" style="color: var(--accent-green);"></i> ${activeTrolley.battery_level}% Battery
                            </span>
                            <span style="font-size: 0.78rem; color: var(--text-secondary);">
                                <i class="fa-regular fa-clock"></i> Last seen: ${activeTrolley.last_seen_str}
                            </span>
                        </div>
                        <div>
                            <button id="portal-unassign-btn" class="btn btn-outline" style="padding: 6px 12px; font-size: 0.8rem; color: var(--accent-red); border-color: rgba(239, 68, 68, 0.4);">
                                <i class="fa-solid fa-link-slash"></i> Release Trolley
                            </button>
                        </div>
                    </div>

                    ${disconnectWarningHtml}
                    ${itemsTableHtml}
                </div>
            `;

            // Bind unassign button
            const unassignBtn = document.getElementById('portal-unassign-btn');
            if (unassignBtn) {
                unassignBtn.addEventListener('click', async () => {
                    if (confirm(`Release and unpair ${activeTrolley.trolley_id} from your account?`)) {
                        await unassignTrolley(activeTrolley.trolley_id);
                    }
                });
            }

        } else {
            // NO Trolley currently assigned
            if (els.trolleyIdPill) els.trolleyIdPill.style.display = 'none';
            if (els.trolleyConnBadge) {
                els.trolleyConnBadge.className = 'trolley-status-badge available';
                els.trolleyConnBadge.innerHTML = `<i class="fa-solid fa-circle-check"></i> Available for Pairing`;
            }

            // Fetch available trolleys to render pairing options
            let availableTrolleys = [];
            try {
                const tRes = await fetch('/api/trolleys');
                if (tRes.ok) {
                    const allT = await tRes.json();
                    availableTrolleys = allT.filter(t => t.assignment_status === 'AVAILABLE');
                }
            } catch (e) {
                console.error("Failed to load available trolleys:", e);
            }

            let pairOptionsHtml = '';
            if (availableTrolleys.length > 0) {
                availableTrolleys.forEach(t => {
                    const connTag = t.status === 'online' ? '🟢 Online' : '⚪ Standby';
                    pairOptionsHtml += `<option value="${t.id}">${t.name} (${t.id}) - ${connTag}</option>`;
                });
            } else {
                pairOptionsHtml = `<option value="">No trolleys currently available</option>`;
            }

            els.activeTrolleyContent.innerHTML = `
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--panel-border); border-radius: 12px; padding: 28px; text-align: center;">
                    <div style="width: 56px; height: 56px; border-radius: 50%; background: rgba(6, 182, 212, 0.1); color: var(--accent-cyan); display: flex; align-items: center; justify-content: center; margin: 0 auto 16px auto; font-size: 1.5rem;">
                        <i class="fa-solid fa-cart-shopping"></i>
                    </div>
                    <h4 style="margin: 0 0 6px 0; font-size: 1.1rem; font-weight: 600;">No Smart Trolley Paired Yet</h4>
                    <p style="margin: 0 auto 20px auto; max-width: 480px; font-size: 0.85rem; color: var(--text-secondary);">
                        Pair an available smart trolley at the supermarket entrance to automatically track your live cart, discounts, and real-time total.
                    </p>

                    <div style="display: inline-flex; align-items: center; gap: 10px; background: rgba(0, 0, 0, 0.3); padding: 8px 12px; border-radius: 10px; border: 1px solid var(--panel-border); flex-wrap: wrap; justify-content: center;">
                        <span style="font-size: 0.82rem; color: var(--text-secondary);"><i class="fa-solid fa-qrcode"></i> Select Trolley:</span>
                        <select id="portal-pair-trolley-select" class="customer-select-pill" style="min-width: 220px;" ${availableTrolleys.length === 0 ? 'disabled' : ''}>
                            ${pairOptionsHtml}
                        </select>
                        <button id="portal-pair-trolley-btn" class="btn btn-primary" style="padding: 6px 14px; font-size: 0.85rem;" ${availableTrolleys.length === 0 ? 'disabled' : ''}>
                            <i class="fa-solid fa-link"></i> Pair Trolley
                        </button>
                    </div>
                </div>
            `;

            // Bind Pair button
            const pairBtn = document.getElementById('portal-pair-trolley-btn');
            const pairSelect = document.getElementById('portal-pair-trolley-select');
            if (pairBtn && pairSelect) {
                pairBtn.addEventListener('click', async () => {
                    const tid = pairSelect.value;
                    if (!tid) return;
                    await assignTrolleyToCurrentCustomer(tid);
                });
            }
        }
    }

    async function assignTrolleyToCurrentCustomer(trolleyId) {
        if (!currentCustomerId) {
            currentCustomerId = 'guest';
        }

        try {
            const res = await fetch(`/api/trolleys/${encodeURIComponent(trolleyId)}/assign`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ customer_id: currentCustomerId })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                if (window.showToast) {
                    window.showToast("Trolley Paired!", `Successfully paired ${trolleyId} to your ${currentCustomerId === 'guest' ? 'guest session' : 'account'}.`, "success");
                }
                await loadCustomerList(currentCustomerId);
            } else {
                alert(data.message || "Failed to pair trolley.");
            }
        } catch (e) {
            console.error("Assignment error:", e);
            alert("Network error pairing trolley.");
        }
    }

    async function unassignTrolley(trolleyId) {
        try {
            const res = await fetch(`/api/trolleys/${encodeURIComponent(trolleyId)}/unassign`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (res.ok && data.success) {
                if (window.showToast) {
                    window.showToast("Trolley Released", `${trolleyId} unlinked from account.`, "info");
                }
                await loadCustomerList(currentCustomerId);
            } else {
                alert(data.message || "Failed to release trolley.");
            }
        } catch (e) {
            console.error("Unassign error:", e);
            alert("Network error releasing trolley.");
        }
    }

    function renderWishlist(wishlist) {
        if (els.wishlistCount) els.wishlistCount.textContent = wishlist.length;
        if (!els.wishlistContainer) return;

        els.wishlistContainer.innerHTML = '';
        if (!wishlist || wishlist.length === 0) {
            els.wishlistContainer.innerHTML = `
                <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-secondary); background: rgba(255,255,255,0.02); border-radius: 8px;">
                    <i class="fa-regular fa-heart" style="font-size: 1.8rem; margin-bottom: 8px; opacity: 0.4; display: block;"></i>
                    Your wishlist is empty. Browse the store catalog below to add items for quick retrieval!
                </div>
            `;
            return;
        }

        wishlist.forEach(item => {
            const wishEl = document.createElement('div');
            wishEl.className = 'catalog-card';
            const price = Number(item.price || 0);

            wishEl.innerHTML = `
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                        <span style="font-weight: 600; font-size: 0.95rem; color: var(--text-primary);">${item.name}</span>
                        <span style="color: var(--accent-green); font-weight: 700; font-size: 0.95rem; white-space: nowrap;">₹${price.toFixed(2)}</span>
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">
                        <i class="fa-solid fa-map-pin" style="color: var(--accent-cyan); margin-right: 4px;"></i>${item.shelf || 'Main Aisle'}
                    </div>
                    ${item.offer && item.offer !== 'Standard Price' ? `
                        <div style="margin-top: 6px;">
                            <span style="font-size: 0.72rem; background: rgba(6, 182, 212, 0.15); color: var(--accent-cyan); padding: 2px 6px; border-radius: 4px;">
                                <i class="fa-solid fa-tag"></i> ${item.offer}
                            </span>
                        </div>
                    ` : ''}
                </div>
                <div style="margin-top: 14px; display: flex; justify-content: flex-end;">
                    <button class="btn btn-outline" style="font-size: 0.75rem; padding: 4px 8px; color: var(--accent-red); border-color: rgba(239, 68, 68, 0.3);" onclick="removeWishlistItem('${item.name.replace(/'/g, "\\'")}')">
                        <i class="fa-solid fa-trash-can"></i> Remove
                    </button>
                </div>
            `;
            els.wishlistContainer.appendChild(wishEl);
        });
    }

    async function loadCatalog() {
        try {
            const res = await fetch('/api/products');
            if (res.ok) {
                allCatalogProducts = await res.json();
                renderCatalog(allCatalogProducts);
            }
        } catch (e) {
            console.error("Failed to load catalog products:", e);
        }
    }

    function renderCatalog(products) {
        if (!els.catalogGrid) return;
        els.catalogGrid.innerHTML = '';

        if (!products || products.length === 0) {
            els.catalogGrid.innerHTML = `
                <div style="grid-column: 1 / -1; padding: 20px; text-align: center; color: var(--text-secondary);">
                    No products matched your search.
                </div>
            `;
            return;
        }

        products.forEach(p => {
            const card = document.createElement('div');
            card.className = 'catalog-card';
            const price = Number(p.price || 0);

            card.innerHTML = `
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                        <span style="font-weight: 600; font-size: 0.95rem; color: var(--text-primary);">${p.name}</span>
                        <span style="color: var(--accent-green); font-weight: 700; font-size: 0.95rem;">₹${price.toFixed(2)}</span>
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">
                        <span style="background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px;">${p.category || 'General'}</span>
                        <span style="margin-left: 6px;"><i class="fa-solid fa-boxes-stacked"></i> Stock: ${p.stock || 0}</span>
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">
                        <i class="fa-solid fa-map-pin" style="color: var(--accent-cyan); margin-right: 4px;"></i>${p.shelf || 'Aisle Shelf'}
                    </div>
                    ${p.offer && p.offer !== 'No Active Offers' && p.offer !== 'Standard Price' ? `
                        <div style="margin-top: 6px;">
                            <span style="font-size: 0.72rem; background: rgba(245, 158, 11, 0.15); color: #f59e0b; padding: 2px 6px; border-radius: 4px;">
                                <i class="fa-solid fa-gift"></i> ${p.offer}
                            </span>
                        </div>
                    ` : ''}
                </div>
                <div style="margin-top: 14px;">
                    <button class="btn btn-outline" style="width: 100%; font-size: 0.8rem; padding: 6px;" onclick="addCatalogItemToWishlist('${p.name.replace(/'/g, "\\'")}', ${price}, '${(p.category || 'General').replace(/'/g, "\\'")}', '${(p.shelf || 'Main Aisle').replace(/'/g, "\\'")}', '${(p.offer || 'Standard Price').replace(/'/g, "\\'")}')">
                        <i class="fa-solid fa-plus"></i> Add to Wishlist
                    </button>
                </div>
            `;
            els.catalogGrid.appendChild(card);
        });
    }

    function getGuestWishlist() {
        try {
            return JSON.parse(localStorage.getItem('smart_trolley_guest_wishlist')) || [];
        } catch (e) {
            return [];
        }
    }

    function saveGuestWishlist(items) {
        try {
            localStorage.setItem('smart_trolley_guest_wishlist', JSON.stringify(items));
        } catch (e) {
            console.error("Failed to save guest wishlist:", e);
        }
    }

    window.addCatalogItemToWishlist = async function(name, price, category, shelf, offer) {
        if (!currentCustomerId || currentCustomerId === 'guest') {
            const current = getGuestWishlist();
            if (current.some(it => it.name.toLowerCase() === name.toLowerCase())) {
                if (window.showToast) window.showToast("Wishlist", `${name} is already in your wishlist.`, "info");
                return;
            }
            current.push({ name, price, category, shelf, offer });
            saveGuestWishlist(current);
            if (window.showToast) window.showToast("Wishlist Updated", `Added ${name} to your session wishlist.`, "success");
            renderWishlist(current);
            return;
        }

        try {
            const res = await fetch(`/api/customer/wishlist?customer_id=${encodeURIComponent(currentCustomerId)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, price, category, shelf, offer })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                if (window.showToast) {
                    window.showToast("Wishlist Updated", `Added ${name} to your wishlist.`, "success");
                }
                renderWishlist(data.wishlist);
            }
        } catch (e) {
            console.error("Failed to add to wishlist:", e);
        }
    };

    window.removeWishlistItem = async function(name) {
        if (!currentCustomerId || currentCustomerId === 'guest') {
            const current = getGuestWishlist().filter(it => it.name.toLowerCase() !== name.toLowerCase());
            saveGuestWishlist(current);
            if (window.showToast) window.showToast("Removed", `Removed ${name} from wishlist.`, "info");
            renderWishlist(current);
            return;
        }

        try {
            const res = await fetch(`/api/customer/wishlist?customer_id=${encodeURIComponent(currentCustomerId)}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                if (window.showToast) {
                    window.showToast("Removed", `Removed ${name} from wishlist.`, "info");
                }
                renderWishlist(data.wishlist);
            }
        } catch (e) {
            console.error("Failed to remove from wishlist:", e);
        }
    };

    function renderReceipts(transactions) {
        if (!els.receiptsBody) return;
        els.receiptsBody.innerHTML = '';

        if (!transactions || transactions.length === 0) {
            const isGuest = currentCustomerId === 'guest';
            els.receiptsBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 28px; color: var(--text-secondary);">
                        <i class="fa-solid fa-receipt" style="font-size: 1.8rem; opacity: 0.3; margin-bottom: 8px; display: block;"></i>
                        ${isGuest ? 'No purchase invoices for this guest session.<br><span style="font-size:0.8rem; opacity:0.8; margin-top:4px; display:inline-block;">Sign in or register to have your verified thermal receipts saved automatically to your member locker.</span>' : 'No shopping invoices recorded yet for this member.'}
                    </td>
                </tr>
            `;
            return;
        }

        transactions.forEach(tx => {
            const dateStr = tx.date || (tx.timestamp ? new Date(tx.timestamp * 1000).toLocaleString() : 'N/A');
            const totalVal = Number(tx.finalTotal || tx.total || 0);
            const gst = totalVal * 0.18;
            const trolleyName = tx.trolley_id || 'TROLLEY-001';
            const payMethod = tx.paymentMethod || 'UPI';

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight: 500;">
                    ${dateStr}
                    ${tx.invoiceId ? `<div style="font-size: 0.72rem; color: var(--text-secondary); font-family: monospace;">${tx.invoiceId}</div>` : ''}
                </td>
                <td><span style="background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; font-family: monospace;">${trolleyName}</span></td>
                <td><span class="trolley-status-badge active" style="font-size: 0.75rem; text-transform: uppercase;">${payMethod}</span></td>
                <td style="color: var(--accent-green); font-weight: 700;">₹${totalVal.toFixed(2)}</td>
                <td style="color: var(--text-secondary);">₹${gst.toFixed(2)}</td>
                <td>
                    <a href="receipt.html?timestamp=${tx.timestamp || ''}&trolley_id=${encodeURIComponent(trolleyName)}" target="_blank" class="btn btn-outline" style="font-size: 0.75rem; padding: 4px 10px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
                        <i class="fa-solid fa-receipt"></i> View Receipt
                    </a>
                </td>
            `;
            els.receiptsBody.appendChild(tr);
        });
    }

    function setupEventListeners() {
        // Customer Select change
        if (els.customerSelect) {
            els.customerSelect.addEventListener('change', async (e) => {
                currentCustomerId = e.target.value;
                await loadProfileData(currentCustomerId);
            });
        }

        // Register Modal
        if (els.regModalBtn && els.regModal) {
            els.regModalBtn.addEventListener('click', () => {
                els.regModal.classList.add('active');
            });
        }
        if (els.closeRegModal && els.regModal) {
            els.closeRegModal.addEventListener('click', () => {
                els.regModal.classList.remove('active');
            });
        }
        if (els.cancelRegBtn && els.regModal) {
            els.cancelRegBtn.addEventListener('click', () => {
                els.regModal.classList.remove('active');
            });
        }

        // Register Form Submit
        if (els.regForm) {
            els.regForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('reg-cust-name').value.trim();
                const phone = document.getElementById('reg-cust-phone').value.trim();
                const email = document.getElementById('reg-cust-email').value.trim();
                const custId = document.getElementById('reg-cust-id').value.trim();

                try {
                    const res = await fetch('/api/customers', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, phone, email, id: custId })
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                        if (window.showToast) {
                            window.showToast("Registered!", `Customer ${name} successfully registered.`, "success");
                        }
                        els.regModal.classList.remove('active');
                        els.regForm.reset();
                        const newId = data.customer ? (data.customer.id || data.customer.customer_id) : custId;
                        await loadCustomerList(newId);
                    } else {
                        alert(data.message || "Registration failed.");
                    }
                } catch (err) {
                    console.error("Registration error:", err);
                    alert("Network error creating customer.");
                }
            });
        }

        // Feedback Modal
        if (els.feedbackModalBtn && els.feedbackModal) {
            els.feedbackModalBtn.addEventListener('click', () => {
                els.feedbackModal.classList.add('active');
            });
        }
        if (els.closeFeedbackModal && els.feedbackModal) {
            els.closeFeedbackModal.addEventListener('click', () => {
                els.feedbackModal.classList.remove('active');
            });
        }
        if (els.cancelFeedbackBtn && els.feedbackModal) {
            els.cancelFeedbackBtn.addEventListener('click', () => {
                els.feedbackModal.classList.remove('active');
            });
        }

        // Star Rating selector
        if (els.starRatingBox) {
            const stars = els.starRatingBox.querySelectorAll('.star-item');
            stars.forEach(star => {
                star.addEventListener('click', () => {
                    currentRating = parseInt(star.getAttribute('data-val'), 10);
                    updateStars(currentRating);
                });
            });
        }

        function updateStars(val) {
            const stars = els.starRatingBox.querySelectorAll('.star-item');
            stars.forEach(s => {
                const sVal = parseInt(s.getAttribute('data-val'), 10);
                if (sVal <= val) {
                    s.style.color = '#f59e0b';
                } else {
                    s.style.color = 'rgba(255,255,255,0.2)';
                }
            });
            const labels = ["1 Star - Needs Improvement", "2 Stars - Fair", "3 Stars - Good", "4 Stars - Very Good", "5 Stars - Excellent!"];
            if (els.starRatingText) {
                els.starRatingText.textContent = labels[val - 1] || `${val} Stars`;
            }
        }

        // Feedback Form Submit
        if (els.feedbackForm) {
            els.feedbackForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const comments = document.getElementById('portal-feedback-comments').value.trim();

                try {
                    const res = await fetch('/api/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ rating: currentRating, comments })
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                        if (window.showToast) {
                            window.showToast("Thank you!", "Your shopping feedback was recorded.", "success");
                        }
                        els.feedbackModal.classList.remove('active');
                        els.feedbackForm.reset();
                    } else {
                        alert(data.message || "Failed to submit feedback.");
                    }
                } catch (err) {
                    console.error("Feedback error:", err);
                    alert("Network error submitting feedback.");
                }
            });
        }

        // Catalog live search & category filter
        if (els.catalogSearch) {
            els.catalogSearch.addEventListener('input', filterCatalog);
        }
        if (els.catalogCategory) {
            els.catalogCategory.addEventListener('change', filterCatalog);
        }

        function filterCatalog() {
            const q = (els.catalogSearch ? els.catalogSearch.value : '').toLowerCase().trim();
            const cat = els.catalogCategory ? els.catalogCategory.value : 'ALL';

            const filtered = allCatalogProducts.filter(p => {
                const matchName = (p.name || '').toLowerCase().includes(q) || (p.shelf || '').toLowerCase().includes(q);
                const matchCat = cat === 'ALL' || (p.category || '').toLowerCase() === cat.toLowerCase();
                return matchName && matchCat;
            });
            renderCatalog(filtered);
        }

        // Logout
        if (els.logoutBtn) {
            els.logoutBtn.addEventListener('click', () => {
                if (window.logoutUser) {
                    window.logoutUser();
                } else {
                    localStorage.clear();
                    window.location.href = 'login.html';
                }
            });
        }
    }

    function startRealtimePolling() {
        if (activePollingTimer) clearInterval(activePollingTimer);
        activePollingTimer = setInterval(async () => {
            if (currentCustomerId) {
                await loadProfileData(currentCustomerId, true);
            }
        }, 2500);
    }
});

// Global tab switch function
window.switchHubTab = function(tabName) {
    const wishlistPane = document.getElementById('portal-wishlist-tab-pane');
    const catalogPane = document.getElementById('portal-catalog-tab-pane');
    const wishlistBtn = document.getElementById('tab-wishlist-btn');
    const catalogBtn = document.getElementById('tab-catalog-btn');

    if (tabName === 'wishlist') {
        if (wishlistPane) wishlistPane.style.display = 'block';
        if (catalogPane) catalogPane.style.display = 'none';
        if (wishlistBtn) wishlistBtn.classList.add('active');
        if (catalogBtn) catalogBtn.classList.remove('active');
    } else {
        if (wishlistPane) wishlistPane.style.display = 'none';
        if (catalogPane) catalogPane.style.display = 'block';
        if (wishlistBtn) wishlistBtn.classList.remove('active');
        if (catalogBtn) catalogBtn.classList.add('active');
    }
};
