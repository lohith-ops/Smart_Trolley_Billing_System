/**
 * Shared Utilities & Dynamic Navigation for Smart Trolley Web Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inject Unified Grouped Sidebar Navigation
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
            const res = await fetch('/api/dashboard');
            if (res.ok) {
                const data = await res.json();
                
                // Update UI Indicators
                if (pulseDot && statusText) {
                    if (data.arduinoConnected) {
                        pulseDot.style.backgroundColor = 'var(--accent-green)';
                        pulseDot.style.boxShadow = '0 0 8px var(--accent-green)';
                        statusText.textContent = `Arduino Online (${data.serialPort})`;
                    } else {
                        pulseDot.style.backgroundColor = 'var(--accent-red)';
                        pulseDot.style.boxShadow = '0 0 8px var(--accent-red)';
                        statusText.textContent = 'Arduino Offline';
                    }
                }

                // Trigger Toast on Arduino Connectivity Changes
                if (lastArduinoState !== null && lastArduinoState !== data.arduinoConnected) {
                    if (data.arduinoConnected) {
                        window.showToast("Hardware Online", `Arduino has successfully connected to port ${data.serialPort}`, "success");
                    } else {
                        window.showToast("Hardware Connection Lost", `Arduino on ${data.serialPort} disconnected. Please check cables.`, "error");
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
                        
                        if (elapsed < 5) {
                            if (latestEvent.actionType === "UNKNOWN_SCAN") {
                                window.showToast("New Card Scanned", `Unknown card UID ${latestEvent.uid} detected. Register it now.`, "warning");
                            } else if (latestEvent.actionType === "ADD") {
                                window.showToast("Item Added", `${latestEvent.productName} (Rs. ${latestEvent.productPrice.toFixed(2)}) scanned into cart.`, "success");
                            } else if (latestEvent.actionType === "REMOVE") {
                                window.showToast("Item Removed", `${latestEvent.productName} removed from cart.`, "info");
                            } else if (latestEvent.actionType === "CHECKOUT") {
                                window.showToast("Checkout Finalized", `Transaction approved! Billed total: Rs. ${latestEvent.total.toFixed(2)}`, "success");
                            } else if (latestEvent.actionType === "RESET") {
                                window.showToast("Cart Reset", "Active trolley bill has been cleared.", "info");
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
 * Renders the unified project sidebar across all dashboard views
 */
function renderSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    
    sidebar.innerHTML = `
        <div class="sidebar-header">
            <div class="logo-icon">
                <i class="fa-solid fa-cart-shopping"></i>
            </div>
            <h2>Smart Trolley</h2>
        </div>
        <nav class="sidebar-nav">
            <div class="sidebar-group-label">Admin Suite</div>
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
            <a href="inventory.html" class="nav-item" id="nav-inventory">
                <i class="fa-solid fa-boxes-stacked"></i>
                <span>Inventory Catalog</span>
            </a>
            <a href="transactions.html" class="nav-item" id="nav-transactions">
                <i class="fa-solid fa-history"></i>
                <span>Transactions Log</span>
            </a>
            <a href="analytics.html" class="nav-item" id="nav-analytics">
                <i class="fa-solid fa-chart-line"></i>
                <span>Sales Analytics</span>
            </a>
            <a href="reports.html" class="nav-item" id="nav-reports">
                <i class="fa-solid fa-file-invoice-dollar"></i>
                <span>Reports Module</span>
            </a>
            <a href="employees.html" class="nav-item" id="nav-employees">
                <i class="fa-solid fa-users-gear"></i>
                <span>Employee Management</span>
            </a>
            <a href="feedback.html" class="nav-item" id="nav-feedback">
                <i class="fa-solid fa-comment-dots"></i>
                <span>Customer Feedback</span>
            </a>
            <a href="settings.html" class="nav-item" id="nav-settings">
                <i class="fa-solid fa-gear"></i>
                <span>Settings Panel</span>
            </a>
            
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
        </nav>
        <div class="sidebar-footer">
            <div class="status-indicator">
                <span class="pulse-dot"></span>
                <span>System Online</span>
            </div>
        </div>
    `;
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
