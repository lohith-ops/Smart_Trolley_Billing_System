/**
 * Sign In Handling Script for Smart Trolley Web Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');
    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    const submitBtn = document.getElementById('login-submit-btn');
    const errorAlert = document.getElementById('login-error-alert');
    const errorMsg = document.getElementById('login-error-msg');
    const togglePassBtn = document.getElementById('toggle-password');
    const togglePassIcon = document.getElementById('toggle-password-icon');
    const presetBtns = document.querySelectorAll('.preset-btn');

    // 1. Password Visibility Toggle
    if (togglePassBtn && passwordInput && togglePassIcon) {
        togglePassBtn.addEventListener('click', () => {
            const isPassword = passwordInput.type === 'password';
            passwordInput.type = isPassword ? 'text' : 'password';
            togglePassIcon.className = isPassword ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
        });
    }

    // 2. Preset Buttons Quick Fill & Auto-Login
    presetBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const user = btn.getAttribute('data-user');
            const pass = btn.getAttribute('data-pass');
            if (user && pass) {
                usernameInput.value = user;
                passwordInput.value = pass;
                hideError();
                // Highlight button briefly
                btn.style.transform = 'scale(0.96)';
                setTimeout(() => {
                    btn.style.transform = '';
                    handleLogin(user, pass);
                }, 150);
            }
        });
    });

    // 3. Form Submit Handler
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const username = usernameInput.value.trim();
            const password = passwordInput.value;
            handleLogin(username, password);
        });
    }

    /**
     * Executes the login API request
     */
    async function handleLogin(username, password) {
        if (!username || !password) {
            showError("Please enter both username and password.");
            return;
        }

        hideError();
        setLoading(true);

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            const data = await res.json();

            if (res.ok && data.success && data.token) {
                // Save session in localStorage
                window.setAuthSession(data.token, data.user);

                // Show success state on button
                submitBtn.innerHTML = `<i class="fa-solid fa-check"></i> <span>Success! Redirecting...</span>`;
                submitBtn.style.background = 'var(--accent-green)';
                submitBtn.style.boxShadow = '0 0 20px rgba(16, 185, 129, 0.5)';

                // Check for redirect param
                const urlParams = new URLSearchParams(window.location.search);
                const redirectTarget = urlParams.get('redirect');

                setTimeout(() => {
                    if (redirectTarget && !redirectTarget.includes('login.html')) {
                        window.location.href = decodeURIComponent(redirectTarget);
                    } else if (data.user.role === 'customer') {
                        window.location.href = 'customer-portal.html';
                    } else {
                        window.location.href = 'index.html';
                    }
                }, 400);

            } else {
                showError(data.message || "Invalid credentials. Please try again.");
                setLoading(false);
            }
        } catch (err) {
            console.error("Login request error:", err);
            showError("Unable to reach server. Please ensure the backend is running.");
            setLoading(false);
        }
    }

    function showError(msg) {
        if (errorAlert && errorMsg) {
            errorMsg.textContent = msg;
            errorAlert.classList.remove('hidden');
        }
    }

    function hideError() {
        if (errorAlert) {
            errorAlert.classList.add('hidden');
        }
    }

    function setLoading(isLoading) {
        if (!submitBtn) return;
        if (isLoading) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Authenticating...</span>`;
        } else {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<span>Sign In</span> <i class="fa-solid fa-arrow-right"></i>`;
            submitBtn.style.background = '';
            submitBtn.style.boxShadow = '';
        }
    }
});
