/**
 * Global Authentication & Session Guard for Smart Trolley Web Dashboard
 */

const AUTH_CONFIG = {
    TOKEN_KEY: 'smart_trolley_jwt_token',
    USER_KEY:  'smart_trolley_user_profile',
    PUBLIC_PAGES: ['login.html', 'product-search.html', 'customer-portal.html', 'navigation.html', 'receipt.html'],
    ROLE_PERMISSIONS: {
        'admin': ['*'],
        'manager': ['index.html', 'trolleys.html', 'trolley-monitor.html', 'inventory.html', 'transactions.html', 'analytics.html', 'reports.html', 'feedback.html', 'customer-portal.html', 'product-search.html', 'navigation.html', 'receipt.html'],
        'cashier': ['index.html', 'trolleys.html', 'trolley-monitor.html', 'transactions.html', 'feedback.html', 'customer-portal.html', 'product-search.html', 'navigation.html', 'receipt.html'],
        'customer': ['customer-portal.html', 'product-search.html', 'navigation.html', 'feedback.html', 'receipt.html']
    }
};

/**
 * Retrieves the stored JWT token
 */
function getAuthToken() {
    return localStorage.getItem(AUTH_CONFIG.TOKEN_KEY);
}

/**
 * Retrieves the stored user profile object
 */
function getAuthUser() {
    try {
        const data = localStorage.getItem(AUTH_CONFIG.USER_KEY);
        return data ? JSON.parse(data) : null;
    } catch (e) {
        return null;
    }
}

/**
 * Decodes a JWT token safely on client-side
 */
function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
}

/**
 * Checks if current user is authenticated and token is not expired
 */
function isAuthenticated() {
    const token = getAuthToken();
    if (!token) return false;
    const payload = parseJwt(token);
    if (!payload || !payload.exp) return false;
    
    // Check if token expired
    const nowSecs = Math.floor(Date.now() / 1000);
    return payload.exp > nowSecs;
}

/**
 * Sets session token and user profile in storage
 */
function setAuthSession(token, user) {
    localStorage.setItem(AUTH_CONFIG.TOKEN_KEY, token);
    localStorage.setItem(AUTH_CONFIG.USER_KEY, JSON.stringify(user));
}

/**
 * Clears session and redirects to login page
 */
function logoutUser() {
    localStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
    localStorage.removeItem(AUTH_CONFIG.USER_KEY);
    
    if (window.showToast) {
        window.showToast("Signed Out", "You have been securely signed out.", "info");
    }
    
    setTimeout(() => {
        window.location.href = 'login.html';
    }, 200);
}

/**
 * Global Fetch Interceptor: Automatically attaches JWT header to all /api/ calls
 */
const originalNativeFetch = window.fetch;
window.fetch = async function(resource, init = {}) {
    let url = typeof resource === 'string' ? resource : (resource && resource.url ? resource.url : '');
    const token = getAuthToken();
    
    if (token && url && (url.startsWith('/api/') || url.includes('/api/')) && !url.includes('/api/auth/login')) {
        init = init || {};
        let headers = init.headers;
        
        if (headers instanceof Headers) {
            if (!headers.has('Authorization')) {
                headers.set('Authorization', `Bearer ${token}`);
            }
        } else if (Array.isArray(headers)) {
            const hasAuth = headers.some(([k]) => k.toLowerCase() === 'authorization');
            if (!hasAuth) {
                headers.push(['Authorization', `Bearer ${token}`]);
            }
        } else {
            headers = Object.assign({}, headers);
            if (!headers['Authorization'] && !headers['authorization']) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }
        init.headers = headers;
    }
    
    try {
        const response = await originalNativeFetch(resource, init);
        
        // Intercept 401 Unauthorized
        if (response.status === 401) {
            const currentPage = window.location.pathname.split('/').pop() || 'index.html';
            if (!AUTH_CONFIG.PUBLIC_PAGES.includes(currentPage)) {
                console.warn("[AUTH] Session expired or unauthorized (401). Redirecting to login...");
                logoutUser();
            }
        }
        
        return response;
    } catch (err) {
        throw err;
    }
};

/**
 * Explicit helper authFetch alias
 */
async function authFetch(url, options = {}) {
    return window.fetch(url, options);
}

/**
 * Route protection guard executed immediately on script load
 */
(function enforceAuthGuard() {
    const currentPath = window.location.pathname.split('/').pop() || 'index.html';
    const isPublic = AUTH_CONFIG.PUBLIC_PAGES.includes(currentPath);
    const loggedIn = isAuthenticated();
    const user = getAuthUser();

    // 1. If user is on login page and already logged in, send them to their dashboard
    if (currentPath === 'login.html' && loggedIn) {
        if (user && user.role === 'customer') {
            window.location.href = 'customer-portal.html';
        } else {
            window.location.href = 'index.html';
        }
        return;
    }

    // 2. If not public and not logged in, redirect to login
    if (!isPublic && !loggedIn) {
        const redirectParam = encodeURIComponent(currentPath);
        window.location.href = `login.html?redirect=${redirectParam}`;
        return;
    }

    // 3. If logged in, check role permissions for the specific page
    if (loggedIn && user && user.role) {
        const allowedPages = AUTH_CONFIG.ROLE_PERMISSIONS[user.role] || [];
        if (!allowedPages.includes('*') && !allowedPages.includes(currentPath)) {
            alert(`Access Denied: Your account role (${user.role.toUpperCase()}) does not have permission to view ${currentPath}.`);
            window.location.href = (user.role === 'customer') ? 'customer-portal.html' : 'index.html';
        }
    }
})();

// Export helpers to global window
window.getAuthToken = getAuthToken;
window.getAuthUser = getAuthUser;
window.isAuthenticated = isAuthenticated;
window.setAuthSession = setAuthSession;
window.logoutUser = logoutUser;
window.authFetch = authFetch;
