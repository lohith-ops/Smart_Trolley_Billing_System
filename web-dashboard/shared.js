/**
 * Shared Utilities & Dynamic Navigation for Smart Trolley Web Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inject Unified Grouped Sidebar Navigation with User Role Filtering
    renderSidebar();

    // 2. Highlight Active Nav Item
    highlightActiveLink();

    // 3. Initialize Toast Container
    initToastContainer();

    // 4. Arduino Connection Status Polling & Event Toast Alerts
    const statusText = document.querySelector('.status-indicator span:last-child');
    const pulseDot = document.querySelector('.pulse-dot');
    let lastArduinoState = null;
    let processedFeedTimestamps = new Set();

    async function checkStatusAndEvents() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/dashboard');
            if (res.ok) {
                const data = await res.json();
                
                // Update UI Indicators
                if (pulseDot && statusText) {
                    if (data.arduinoConnected) {
                        pulseDot.style.backgroundColor = 'var(--accent-green)';
                        pulseDot.style.boxShadow = '0 0 8px var(--accent-green)';
                        statusText.textContent = `Hardware Online (${data.serialPort})`;
                    } else {
                        pulseDot.style.backgroundColor = 'var(--accent-red)';
                        pulseDot.style.boxShadow = '0 0 8px var(--accent-red)';
                        statusText.textContent = 'Hardware Offline';
                    }
                }

                // Trigger Toast on Connectivity Changes
                if (lastArduinoState !== null && lastArduinoState !== data.arduinoConnected) {
                    if (data.arduinoConnected) {
                        window.showToast("Hardware Online", `Microcontroller connected on port ${data.serialPort}`, "success");
                    } else {
                        window.showToast("Hardware Connection Lost", `Device on ${data.serialPort} disconnected. Please check cables.`, "error");
                    }
                }
                lastArduinoState = data.arduinoConnected;

                // Monitor Activity Feed for Toasts (Only trigger for events in the last 4 seconds)
                if (data.feed && data.feed.length > 0) {
                    const latestEvent = data.feed[0];
                    const eventKey = `${latestEvent.actionType}_${latestEvent.timestamp}`;
                    
                    if (!processedFeedTimestamps.has(eventKey)) {
                        processedFeedTimestamps.add(eventKey);
                        const elapsed = (Date.now() / 1000) - latestEvent.timestamp;
                        
                        if (elapsed < 5 && window.showToast) {
                            const trolleyLabel = latestEvent.trolley_id ? latestEvent.trolley_id.replace('TROLLEY-00', 'Trolley #').replace('TROLLEY-', 'Trolley #') : 'Trolley #1';
                            const priceStr = (typeof latestEvent.productPrice === 'number') ? latestEvent.productPrice.toFixed(2) : (latestEvent.productPrice ? Number(latestEvent.productPrice).toFixed(2) : '0.00');
                            const totalStr = (typeof latestEvent.total === 'number') ? latestEvent.total.toFixed(2) : (latestEvent.total ? Number(latestEvent.total).toFixed(2) : '0.00');
                            
                            if (latestEvent.actionType === "UNKNOWN_SCAN") {
                                window.showToast("New Card Scanned", `Unknown card UID ${latestEvent.uid} detected on ${trolleyLabel}. Register it now.`, "warning");
                            } else if (latestEvent.actionType === "ADD") {
                                window.showToast("Item Added", `${latestEvent.productName || 'Item'} (+Rs.${priceStr}) scanned into ${trolleyLabel}.`, "success");
                            } else if (latestEvent.actionType === "REMOVE") {
                                window.showToast("Item Removed", `${latestEvent.productName || 'Item'} (-Rs.${priceStr}) removed from ${trolleyLabel}.`, "info");
                            } else if (latestEvent.actionType === "CHECKOUT" || latestEvent.actionType === "BILL_PAID") {
                                window.showToast("Checkout Finalized", `${trolleyLabel} payment complete! Total: Rs.${totalStr}`, "success");
                            } else if (latestEvent.actionType === "BILL_GENERATED") {
                                window.showToast("Bill Generated", `Invoice ready for ${trolleyLabel}. Total: Rs.${totalStr}`, "info");
                            } else if (latestEvent.actionType === "RESET") {
                                window.showToast("Cart Reset", `${trolleyLabel} bill and items cleared.`, "info");
                            } else if (latestEvent.actionType === "PRODUCT_REGISTERED") {
                                window.showToast("Product Registered", `${latestEvent.productName} added to product catalog.`, "success");
                            }
                        }
                    }
                }
            }
        } catch (e) {
            if (pulseDot && statusText) {
                pulseDot.style.backgroundColor = 'var(--accent-red)';
                statusText.textContent = 'Server Offline';
            }
        }
    }

    checkStatusAndEvents();
    setInterval(checkStatusAndEvents, 3000);
});

/**
 * Renders the unified project sidebar with user profile badge and RBAC links
 */
function renderSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    
    const user = (window.getAuthUser && window.getAuthUser()) || { name: 'Guest User', role: 'guest', username: 'guest' };
    const role = (user.role || 'guest').toLowerCase();

    // Helper to calculate role tag style & avatar initials
    const roleColors = {
        'admin':   { bg: 'rgba(244, 63, 94, 0.15)', text: '#f43f5e', border: '#f43f5e' },
        'manager': { bg: 'rgba(192, 132, 252, 0.15)', text: '#c084fc', border: '#c084fc' },
        'cashier': { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: '#10b981' },
        'customer':{ bg: 'rgba(6, 182, 212, 0.15)', text: '#06b6d4', border: '#06b6d4' },
        'guest':   { bg: 'rgba(148, 163, 184, 0.15)', text: '#94a3b8', border: '#94a3b8' }
    };
    const roleStyle = roleColors[role] || roleColors['guest'];
    const initials = (user.name || user.username || 'U')
        .split(' ')
        .map(n => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase();

    // Navigation sections based on permissions
    let adminNavItems = '';
    let customerNavItems = '';

    // Admin Suite items
    if (role === 'admin' || role === 'manager' || role === 'cashier') {
        adminNavItems += `
            <div class="sidebar-group-label">Operations</div>
            <a href="index.html" class="nav-item" id="nav-index">
                <i class="fa-solid fa-house"></i>
                <span>Admin Dashboard</span>
            </a>
            <a href="trolleys.html" class="nav-item" id="nav-trolleys">
                <i class="fa-solid fa-network-wired"></i>
                <span>Live Trolleys</span>
            </a>
            <a href="trolley-monitor.html" class="nav-item" id="nav-trolley-monitor">
                <i class="fa-solid fa-desktop"></i>
                <span>Trolley Monitor</span>
            </a>
        `;

        if (role === 'admin' || role === 'manager') {
            adminNavItems += `
                <a href="inventory.html" class="nav-item" id="nav-inventory">
                    <i class="fa-solid fa-boxes-stacked"></i>
                    <span>Inventory Catalog</span>
                </a>
            `;
        }

        adminNavItems += `
            <a href="transactions.html" class="nav-item" id="nav-transactions">
                <i class="fa-solid fa-history"></i>
                <span>Transactions Log</span>
            </a>
        `;

        if (role === 'admin' || role === 'manager') {
            adminNavItems += `
                <a href="analytics.html" class="nav-item" id="nav-analytics">
                    <i class="fa-solid fa-chart-line"></i>
                    <span>Sales Analytics</span>
                </a>
                <a href="reports.html" class="nav-item" id="nav-reports">
                    <i class="fa-solid fa-file-invoice-dollar"></i>
                    <span>Reports Module</span>
                </a>
            `;
        }

        if (role === 'admin') {
            adminNavItems += `
                <a href="employees.html" class="nav-item" id="nav-employees">
                    <i class="fa-solid fa-users-gear"></i>
                    <span>Staff & Roles</span>
                </a>
            `;
        }

        adminNavItems += `
            <a href="feedback.html" class="nav-item" id="nav-feedback">
                <i class="fa-solid fa-comment-dots"></i>
                <span>Customer Feedback</span>
            </a>
        `;

        if (role === 'admin') {
            adminNavItems += `
                <a href="settings.html" class="nav-item" id="nav-settings">
                    <i class="fa-solid fa-gear"></i>
                    <span>System Settings</span>
                </a>
            `;
        }
    }

    // Customer Portal Items
    customerNavItems = `
        <div class="sidebar-group-label">Customer Portal</div>
        <a href="customer-portal.html" class="nav-item" id="nav-customer-portal">
            <i class="fa-solid fa-user-circle"></i>
            <span>Member Portal</span>
        </a>
        <a href="product-search.html" class="nav-item" id="nav-product-search">
            <i class="fa-solid fa-search"></i>
            <span>Product Finder</span>
        </a>
        <a href="navigation.html" class="nav-item" id="nav-navigation">
            <i class="fa-solid fa-map-location-dot"></i>
            <span>Store Directory</span>
        </a>
        <a href="feedback.html" class="nav-item" id="nav-feedback">
            <i class="fa-solid fa-comment-dots"></i>
            <span>Give Feedback</span>
        </a>
    `;

    sidebar.innerHTML = `
        <div class="sidebar-header">
            <div class="logo-icon">
                <i class="fa-solid fa-cart-shopping"></i>
            </div>
            <h2>Smart Trolley</h2>
        </div>

        <div class="sidebar-user-card glass-panel">
            <div class="sidebar-user-avatar" style="background: ${roleStyle.bg}; color: ${roleStyle.text}; border: 1px solid ${roleStyle.border};">
                ${initials}
            </div>
            <div class="sidebar-user-info">
                <div class="sidebar-user-name">${user.name || user.username || 'User'}</div>
                <div class="sidebar-user-role-badge" style="color: ${roleStyle.text}; border-color: ${roleStyle.border}; background: ${roleStyle.bg};">
                    ${role.toUpperCase()}
                </div>
            </div>
            <button type="button" class="sidebar-logout-btn" id="sidebar-logout-btn" title="Sign Out">
                <i class="fa-solid fa-arrow-right-from-bracket"></i>
            </button>
        </div>

        <nav class="sidebar-nav">
            ${adminNavItems}
            ${customerNavItems}
        </nav>

        <div class="sidebar-footer">
            <div class="status-indicator">
                <span class="pulse-dot"></span>
                <span>System Online</span>
            </div>
        </div>
    `;

    // Bind logout button
    const logoutBtn = document.getElementById('sidebar-logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            if (confirm("Are you sure you want to sign out?")) {
                if (window.logoutUser) {
                    window.logoutUser();
                } else {
                    localStorage.clear();
                    window.location.href = 'login.html';
                }
            }
        });
    }
}

/**
 * Highlights active link matching page filename
 */
function highlightActiveLink() {
    const currentPath = window.location.pathname.split('/').pop() || 'index.html';
    const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
    
    navItems.forEach(item => {
        const itemHref = item.getAttribute('href');
        if (itemHref === currentPath || (currentPath === '' && itemHref === 'index.html')) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

/**
 * Dynamic Toast Notifications Core
 */
function initToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
}

window.showToast = function(title, message, type = 'info') {
    initToastContainer();
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = 'toast glass-panel';
    
    let iconClass = 'fa-info-circle info';
    if (type === 'success') iconClass = 'fa-check-circle success';
    else if (type === 'warning') iconClass = 'fa-exclamation-triangle warning';
    else if (type === 'error') iconClass = 'fa-times-circle error';
    
    toast.innerHTML = `
        <div class="toast-icon">
            <i class="fa-solid ${iconClass}"></i>
        </div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${message}</div>
        </div>
        <button class="toast-close"><i class="fa-solid fa-xmark"></i></button>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 50);
    
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    });
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }
    }, 5000);
};
