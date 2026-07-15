/**
 * Customer Portal Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    const els = {
        loginContainer: document.getElementById('login-container'),
        dashboardContainer: document.getElementById('portal-dashboard-container'),
        loginForm: document.getElementById('portal-login-form'),
        usernameInput: document.getElementById('login-username'),
        passwordInput: document.getElementById('login-password'),
        logoutBtn: document.getElementById('portal-logout-btn'),
        userProfile: document.getElementById('portal-user-profile'),
        
        // Profile DOMs
        name: document.getElementById('portal-name'),
        tier: document.getElementById('portal-tier'),
        points: document.getElementById('portal-points'),
        email: document.getElementById('portal-email'),
        phone: document.getElementById('portal-phone'),
        wishlist: document.getElementById('portal-wishlist-container'),
        receiptsBody: document.getElementById('portal-receipts-body')
    };

    // Check session storage
    if (sessionStorage.getItem('shopper_logged_in') === 'true') {
        showDashboard();
    }

    async function handleLogin(e) {
        e.preventDefault();
        const username = els.usernameInput.value.trim();
        const password = els.passwordInput.value.trim();

        if (username === 'customer123' && password === 'password') {
            sessionStorage.setItem('shopper_logged_in', 'true');
            showDashboard();
            if (window.showToast) {
                window.showToast("Authentication Success", "Welcome back to your member dashboard!", "success");
            }
        } else {
            alert("Invalid username or password. Please use test credentials.");
        }
    }

    function handleLogout() {
        sessionStorage.removeItem('shopper_logged_in');
        els.loginContainer.style.display = 'block';
        els.dashboardContainer.style.display = 'none';
        els.logoutBtn.style.display = 'none';
        els.userProfile.style.display = 'none';
        if (window.showToast) {
            window.showToast("Signed Out", "You have successfully signed out of the portal.", "info");
        }
    }

    async function showDashboard() {
        els.loginContainer.style.display = 'none';
        els.dashboardContainer.style.display = 'grid';
        els.logoutBtn.style.display = 'block';
        els.userProfile.style.display = 'flex';

        await loadProfile();
        await loadReceipts();
    }

    async function loadProfile() {
        try {
            const res = await fetch('/api/customer/profile');
            if (res.ok) {
                const profile = await res.json();
                
                if (els.name) els.name.textContent = profile.name;
                if (els.tier) els.tier.textContent = profile.tier;
                if (els.points) els.points.innerHTML = `<i class="fa-solid fa-award"></i> ${profile.points} Points`;
                if (els.email) els.email.textContent = profile.email;
                if (els.phone) els.phone.textContent = profile.phone;

                // Render Wishlist
                if (els.wishlist) {
                    els.wishlist.innerHTML = '';
                    if (profile.wishlist.length === 0) {
                        els.wishlist.innerHTML = `<p style="color:var(--text-secondary); grid-column:1/-1;">Wishlist is empty.</p>`;
                    } else {
                        profile.wishlist.forEach(item => {
                            const wishEl = document.createElement('div');
                            wishEl.className = 'card glass-panel';
                            wishEl.style.padding = '12px 16px';
                            wishEl.style.justifyContent = 'space-between';
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

        if (transactions.length === 0) {
            els.receiptsBody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align:center; padding:24px; color:var(--text-secondary);">
                        No transaction invoices found.
                    </td>
                </tr>
            `;
            return;
        }

        transactions.forEach(tx => {
            const date = new Date(tx.timestamp * 1000).toLocaleString();
            const gst = tx.total * 0.18;
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${date}</td>
                <td style="color:var(--accent-green); font-weight:600;">Rs.${tx.total.toFixed(2)}</td>
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

    // Bind event listeners
    if (els.loginForm) els.loginForm.addEventListener('submit', handleLogin);
    if (els.logoutBtn) els.logoutBtn.addEventListener('click', handleLogout);
});
