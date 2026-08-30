/**
 * Customer Self-Registration Handling Script
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('register-form');
    const nameInput = document.getElementById('reg-name');
    const usernameInput = document.getElementById('reg-username');
    const emailInput = document.getElementById('reg-email');
    const passwordInput = document.getElementById('reg-password');
    const confirmPassInput = document.getElementById('reg-confirm-password');
    const submitBtn = document.getElementById('reg-submit-btn');
    const errorAlert = document.getElementById('register-error-alert');
    const errorMsg = document.getElementById('register-error-msg');
    const successAlert = document.getElementById('register-success-alert');
    const successMsg = document.getElementById('register-success-msg');

    // Toggle Password Visibility
    const togglePass = document.getElementById('toggle-reg-pass');
    const togglePassIcon = document.getElementById('toggle-reg-pass-icon');
    if (togglePass && passwordInput && togglePassIcon) {
        togglePass.addEventListener('click', () => {
            const isPass = passwordInput.type === 'password';
            passwordInput.type = isPass ? 'text' : 'password';
            togglePassIcon.className = isPass ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
        });
    }

    // Toggle Confirm Password Visibility
    const toggleConfirm = document.getElementById('toggle-reg-confirm');
    const toggleConfirmIcon = document.getElementById('toggle-reg-confirm-icon');
    if (toggleConfirm && confirmPassInput && toggleConfirmIcon) {
        toggleConfirm.addEventListener('click', () => {
            const isPass = confirmPassInput.type === 'password';
            confirmPassInput.type = isPass ? 'text' : 'password';
            toggleConfirmIcon.className = isPass ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
        });
    }

    // Form Submit Handler
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const name = nameInput.value.trim();
            const username = usernameInput.value.trim().toLowerCase();
            const email = emailInput ? emailInput.value.trim() : '';
            const password = passwordInput.value;
            const confirmPassword = confirmPassInput.value;

            // Client-side validations
            if (!name || !username || !password) {
                showError("Please fill in all required fields.");
                return;
            }

            if (username.length < 3) {
                showError("Username must be at least 3 characters long.");
                usernameInput.focus();
                return;
            }

            const emailPattern = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
            if (email && !emailPattern.test(email)) {
                showError("Please enter a valid email address (e.g. admin@gmail.com).");
                emailInput.focus();
                return;
            }

            if (password.length < 6) {
                showError("Password must be at least 6 characters long.");
                passwordInput.focus();
                return;
            }

            if (password !== confirmPassword) {
                showError("Passwords do not match. Please re-enter.");
                confirmPassInput.focus();
                return;
            }

            hideAlerts();
            setLoading(true);

            try {
                const res = await fetch('/api/auth/signup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: name,
                        username: username,
                        email: email,
                        password: password
                    })
                });

                const data = await res.json();

                if (res.ok && data.success && data.token) {
                    // Set auth session
                    window.setAuthSession(data.token, data.user);

                    showSuccess("Account created successfully! Redirecting to customer portal...");

                    submitBtn.innerHTML = `<i class="fa-solid fa-check"></i> <span>Success!</span>`;
                    submitBtn.style.background = 'var(--accent-green)';
                    submitBtn.style.boxShadow = '0 0 20px rgba(16, 185, 129, 0.5)';

                    setTimeout(() => {
                        window.location.href = 'customer-portal.html';
                    }, 800);
                } else {
                    showError(data.message || "Failed to create account. Please try again.");
                    setLoading(false);
                }
            } catch (err) {
                console.error("Signup error:", err);
                showError("Unable to connect to server. Please ensure the backend is running.");
                setLoading(false);
            }
        });
    }

    function showError(msg) {
        if (errorAlert && errorMsg) {
            errorMsg.textContent = msg;
            errorAlert.classList.remove('hidden');
        }
        if (successAlert) successAlert.classList.add('hidden');
    }

    function showSuccess(msg) {
        if (successAlert && successMsg) {
            successMsg.textContent = msg;
            successAlert.classList.remove('hidden');
        }
        if (errorAlert) errorAlert.classList.add('hidden');
    }

    function hideAlerts() {
        if (errorAlert) errorAlert.classList.add('hidden');
        if (successAlert) successAlert.classList.add('hidden');
    }

    function setLoading(isLoading) {
        if (!submitBtn) return;
        if (isLoading) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Creating Account...</span>`;
        } else {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<span>Register & Get Started</span> <i class="fa-solid fa-arrow-right"></i>`;
            submitBtn.style.background = '';
            submitBtn.style.boxShadow = '';
        }
    }
});
