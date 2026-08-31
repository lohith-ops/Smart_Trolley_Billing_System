/**
 * Customer Portal Logic - Unified with Global Authentication
 */

document.addEventListener('DOMContentLoaded', () => {
    const els = {
        dashboardContainer: document.getElementById('portal-dashboard-container'),
        logoutBtn: document.getElementById('portal-logout-btn'),
        loginNavBtn: document.getElementById('portal-login-nav-btn'),
        userProfile: document.getElementById('portal-user-profile'),
        avatarImg: document.getElementById('portal-avatar-img'),
        headerUsername: document.getElementById('portal-header-username'),
        
        // Profile DOMs
        profileImg: document.querySelector('.profile-sidebar img'),
        name: document.getElementById('portal-name'),
        tier: document.getElementById('portal-tier'),
        points: document.getElementById('portal-points'),
        email: document.getElementById('portal-email'),
        phone: document.getElementById('portal-phone'),
        wishlist: document.getElementById('portal-wishlist-container'),
        receiptsBody: document.getElementById('portal-receipts-body')
    };

    // Initialize portal state
    initPortal();

    async function initPortal() {
        const loggedIn = window.isAuthenticated ? window.isAuthenticated() : false;
        const authUser = window.getAuthUser ? window.getAuthUser() : null;

        if (loggedIn && authUser) {
            // Logged in user
            if (els.logoutBtn) els.logoutBtn.style.display = 'inline-flex';
            if (els.loginNavBtn) els.loginNavBtn.style.display = 'none';
            if (els.headerUsername) els.headerUsername.textContent = authUser.name || authUser.username;
            if (els.avatarImg) els.avatarImg.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(authUser.name || authUser.username)}&background=06b6d4&color=fff`;

            if (els.name) els.name.textContent = authUser.name || authUser.username;
            if (els.email) els.email.textContent = authUser.email || `${authUser.username}@smarttrolley.local`;
            if (els.profileImg) els.profileImg.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(authUser.name || authUser.username)}&background=06b6d4&color=fff`;
            if (els.tier) {
                const roleCapitalized = (authUser.role || 'Member').toUpperCase();
                els.tier.textContent = `${roleCapitalized} Account`;
            }
        } else {
            // Guest mode
            if (els.logoutBtn) els.logoutBtn.style.display = 'none';
            if (els.loginNavBtn) els.loginNavBtn.style.display = 'inline-flex';
            if (els.headerUsername) els.headerUsername.textContent = 'Guest Shopper';
            if (els.name) els.name.textContent = 'Guest Shopper';
            if (els.tier) els.tier.textContent = 'Guest Visitor';
        }

        await loadProfileData(authUser);
        await loadReceipts();
    }

    async function loadProfileData(authUser) {
        try {
            const res = await fetch('/api/customer/profile');
            if (res.ok) {
                const profile = await res.json();
                
                if (authUser) {
                    if (els.name) els.name.textContent = authUser.name || profile.name;
                    if (els.email) els.email.textContent = authUser.email || profile.email;
                    if (els.phone) els.phone.textContent = authUser.phone || profile.phone;
                } else {
                    if (els.name) els.name.textContent = profile.name;
                    if (els.email) els.email.textContent = profile.email;
                    if (els.phone) els.phone.textContent = profile.phone;
                }

                if (els.points) els.points.innerHTML = `<i class="fa-solid fa-award"></i> ${profile.points} Points`;

                // Render Wishlist
                if (els.wishlist) {
                    els.wishlist.innerHTML = '';
                    if (!profile.wishlist || profile.wishlist.length === 0) {
                        els.wishlist.innerHTML = `<p style="color:var(--text-secondary); grid-column:1/-1;">Wishlist is empty.</p>`;
                    } else {
                        profile.wishlist.forEach(item => {
                            const wishEl = document.createElement('div');
                            wishEl.className = 'card glass-panel';
                            wishEl.style.padding = '12px 16px';
                            wishEl.style.display = 'flex';
                            wishEl.style.justifyContent = 'space-between';
                            wishEl.style.alignItems = 'center';
                            wishEl.innerHTML = `
                                <div>
                                    <div style="font-weight:600; font-size:0.9rem;">${item.name}</div>
                                    <span style="font-size:0.75rem; color:var(--text-secondary);">${item.category}</span>
                                </div>
                                <div style="color:var(--accent-green); font-weight:700; font-size:0.9rem;">Rs.${item.price.toFixed(2)}</div>
                            `;
                            els.wishlist.appendChild(wishEl);
                        });
                    }
                }
            }
        } catch (e) {
            console.error("Failed to load customer profile details:", e);
        }
    }

    async function loadReceipts() {
        try {
            const res = await fetch('/api/transactions');
            if (res.ok) {
                const transactions = await res.json();
                renderReceipts(transactions);
            }
        } catch (e) {
            console.error("Failed to load transactions for customer portal:", e);
        }
    }

    function renderReceipts(transactions) {
        if (!els.receiptsBody) return;
        els.receiptsBody.innerHTML = '';

        if (!transactions || transactions.length === 0) {
            els.receiptsBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align:center; padding:24px; color:var(--text-secondary);">
                        No transaction invoices found yet.
                    </td>
                </tr>
            `;
            return;
        }

        transactions.forEach(tx => {
            const date = new Date(tx.timestamp * 1000).toLocaleString();
            const totalVal = Number(tx.total || 0);
            const gst = totalVal * 0.18;
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${date}</td>
                <td style="color:var(--accent-green); font-weight:600;">Rs.${totalVal.toFixed(2)}</td>
                <td>Rs.${gst.toFixed(2)}</td>
                <td>
                    <a href="receipt.html?timestamp=${tx.timestamp}" target="_blank" class="btn btn-outline" style="font-size:0.75rem; padding:4px 8px; text-decoration:none;">
                        <i class="fa-solid fa-cloud-arrow-down"></i> View Receipt
                    </a>
                </td>
            `;
            els.receiptsBody.appendChild(tr);
        });
    }

    // Bind logout button to global auth logout
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
});
