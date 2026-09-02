/**
 * Sign In Handling Script for Smart Trolley Web Dashboard
 */

function initLoginPage() {
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

    // 1.1 Demo Mode Collapsible Toggle
    const toggleDemoBtn = document.getElementById('toggle-demo-btn');
    const demoPresetsContainer = document.getElementById('demo-presets-container');
    const demoChevron = document.getElementById('demo-chevron');
    if (toggleDemoBtn && demoPresetsContainer) {
        toggleDemoBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const isHidden = demoPresetsContainer.style.display === 'none' || !demoPresetsContainer.style.display;
            demoPresetsContainer.style.display = isHidden ? 'grid' : 'none';
            if (demoChevron) {
                demoChevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
            }
        });
    }

    // 2. Preset Buttons Quick Fill & Auto-Login
    presetBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const user = btn.getAttribute('data-user');
            const pass = btn.getAttribute('data-pass');
            if (user && pass) {
                if (usernameInput) usernameInput.value = user;
                if (passwordInput) passwordInput.value = pass;
                hideError();
                // Highlight button briefly
                btn.style.transform = 'scale(0.96)';
                setTimeout(() => {
                    btn.style.transform = '';
                    handleLogin(user, pass);
                }, 100);
            }
        });
    });

    // 3. Form Submit Handler
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const username = usernameInput ? usernameInput.value.trim() : '';
            const password = passwordInput ? passwordInput.value : '';
            handleLogin(username, password);
        });
    }

    // Auto-login & clean if query params exist from previous form reload
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const queryUser = urlParams.get('username');
        const queryPass = urlParams.get('password');
        if (queryUser && queryPass) {
            if (usernameInput) usernameInput.value = queryUser;
            if (passwordInput) passwordInput.value = queryPass;
            window.history.replaceState({}, document.title, window.location.pathname);
            setTimeout(() => handleLogin(queryUser, queryPass), 50);
        }
    } catch (e) {
        console.warn("URL query check error:", e);
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
                // Save session in localStorage with fallbacks
                try {
                    localStorage.setItem('smart_trolley_jwt_token', data.token);
                    localStorage.setItem('smart_trolley_user_profile', JSON.stringify(data.user));
                    if (typeof window.setAuthSession === 'function') {
                        window.setAuthSession(data.token, data.user);
                    }
                } catch (storeErr) {
                    console.warn("Storage write notice:", storeErr);
                }

                // Show success state on button
                if (submitBtn) {
                    submitBtn.innerHTML = `<i class="fa-solid fa-check"></i> <span>Success! Redirecting...</span>`;
                    submitBtn.style.background = 'var(--accent-green)';
                    submitBtn.style.boxShadow = '0 0 20px rgba(16, 185, 129, 0.5)';
                }

                // Check for redirect param
                const urlParams = new URLSearchParams(window.location.search);
                const redirectTarget = urlParams.get('redirect');

                setTimeout(() => {
                    if (redirectTarget && !redirectTarget.includes('login.html')) {
                        window.location.href = decodeURIComponent(redirectTarget);
                    } else if (data.user && data.user.role === 'customer') {
                        window.location.href = 'customer-portal.html';
                    } else if (data.user && data.user.role === 'cashier') {
                        window.location.href = 'trolleys.html';
                    } else if (data.user && data.user.role === 'manager') {
                        window.location.href = 'index.html';
                    } else {
                        window.location.href = 'index.html';
                    }
                }, 300);

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

    // ── 4. Forgot Password Modal Logic ──────────────────────────────────────────
    const forgotTrigger     = document.getElementById('forgot-password-trigger');
    const forgotModal       = document.getElementById('forgot-modal');
    const modalBackdrop     = document.getElementById('modal-backdrop');
    const modalCloseBtn     = document.getElementById('forgot-modal-close');
    const forgotAlert       = document.getElementById('forgot-alert');
    const forgotAlertMsg    = document.getElementById('forgot-alert-msg');
    const forgotAlertIcon   = document.getElementById('forgot-alert-icon');
    
    // Step Elements
    const step1Form         = document.getElementById('forgot-step1-form');
    const step2Form         = document.getElementById('forgot-step2-form');
    const successState      = document.getElementById('forgot-success-state');
    const identifierInput   = document.getElementById('forgot-identifier');
    const sendBtn           = document.getElementById('forgot-send-btn');
    const step2TargetInfo   = document.getElementById('step2-target-info');
    const otpInput          = document.getElementById('forgot-otp');
    const newPassInput      = document.getElementById('forgot-new-pass');
    const confirmPassInput  = document.getElementById('forgot-confirm-pass');
    const verifyBtn         = document.getElementById('forgot-verify-btn');
    const backToStep1Btn    = document.getElementById('forgot-back-step1');
    const resendOtpBtn      = document.getElementById('forgot-resend-btn');
    const doneBtn           = document.getElementById('forgot-done-btn');
    const toggleForgotPass  = document.getElementById('toggle-forgot-pass');
    const toggleForgotPassIcon = document.getElementById('toggle-forgot-pass-icon');

    // Elements for Demo OTP
    const demoOtpBanner     = document.getElementById('demo-otp-banner');
    const demoOtpVal        = document.getElementById('demo-otp-val');
    const demoOtpFillBtn    = document.getElementById('demo-otp-fill-btn');

    let activeResetUsername = '';
    let currentOtpCode      = '';

    function openForgotModal() {
        if (!forgotModal) return;
        // Pre-fill identifier if username was typed in main form
        if (usernameInput && usernameInput.value.trim()) {
            identifierInput.value = usernameInput.value.trim();
        }
        resetForgotModalState();
        forgotModal.classList.remove('hidden');
        forgotModal.classList.add('active');
        forgotModal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        setTimeout(() => identifierInput && identifierInput.focus(), 100);
    }

    function closeForgotModal() {
        if (!forgotModal) return;
        forgotModal.classList.remove('active');
        forgotModal.classList.add('hidden');
        forgotModal.style.display = 'none';
        document.body.style.overflow = '';
    }

    function resetForgotModalState() {
        hideForgotAlert();
        if (step1Form) {
            step1Form.classList.remove('hidden');
            step1Form.style.display = 'block';
        }
        if (step2Form) {
            step2Form.classList.add('hidden');
            step2Form.style.display = 'none';
        }
        if (successState) {
            successState.classList.add('hidden');
            successState.style.display = 'none';
        }
        if (demoOtpBanner) {
            demoOtpBanner.style.display = 'none';
        }
        if (otpInput) otpInput.value = '';
        if (newPassInput) newPassInput.value = '';
        if (confirmPassInput) confirmPassInput.value = '';
    }

    function showForgotAlert(msg, type = 'error') {
        if (!forgotAlert || !forgotAlertMsg) return;
        forgotAlertMsg.textContent = msg;
        forgotAlert.className = 'login-alert';
        forgotAlert.classList.remove('hidden');
        forgotAlert.style.display = 'flex';

        if (type === 'success') {
            forgotAlert.style.background = 'rgba(16, 185, 129, 0.15)';
            forgotAlert.style.borderColor = 'rgba(16, 185, 129, 0.4)';
            forgotAlert.style.color = '#34d399';
            if (forgotAlertIcon) forgotAlertIcon.className = 'fa-solid fa-circle-check';
        } else if (type === 'info') {
            forgotAlert.style.background = 'rgba(6, 182, 212, 0.15)';
            forgotAlert.style.borderColor = 'rgba(6, 182, 212, 0.4)';
            forgotAlert.style.color = 'var(--accent-cyan)';
            if (forgotAlertIcon) forgotAlertIcon.className = 'fa-solid fa-circle-info';
        } else {
            forgotAlert.style.background = '';
            forgotAlert.style.borderColor = '';
            forgotAlert.style.color = '';
            if (forgotAlertIcon) forgotAlertIcon.className = 'fa-solid fa-triangle-exclamation';
        }
    }

    function hideForgotAlert() {
        if (forgotAlert) {
            forgotAlert.classList.add('hidden');
            forgotAlert.style.display = 'none';
        }
    }

    if (forgotTrigger) forgotTrigger.addEventListener('click', openForgotModal);
    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeForgotModal);
    if (modalBackdrop) modalBackdrop.addEventListener('click', closeForgotModal);

    // Escape key closes modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && forgotModal && forgotModal.classList.contains('active')) {
            closeForgotModal();
        }
    });

    // Toggle password in reset modal
    if (toggleForgotPass && newPassInput && toggleForgotPassIcon) {
        toggleForgotPass.addEventListener('click', () => {
            const isPass = newPassInput.type === 'password';
            newPassInput.type = isPass ? 'text' : 'password';
            toggleForgotPassIcon.className = isPass ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
        });
    }

    // Step 1: Request OTP
    if (step1Form) {
        step1Form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const identifier = identifierInput.value.trim();
            if (!identifier) {
                showForgotAlert('Please enter your username, email, or phone.');
                return;
            }

            hideForgotAlert();
            sendBtn.disabled = true;
            sendBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Sending Code...</span>`;

            try {
                const res = await fetch('/api/auth/forgot-password/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ identifier })
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    activeResetUsername = data.username || identifier;
                    currentOtpCode = data.otp || '';

                    step1Form.classList.add('hidden');
                    step1Form.style.display = 'none';
                    step2Form.classList.remove('hidden');
                    step2Form.style.display = 'block';
                    
                    if (step2TargetInfo) {
                        step2TargetInfo.textContent = `Verification code sent to ${data.masked_target || identifier}`;
                    }

                    // Show helper OTP banner if code is returned
                    if (data.otp && demoOtpBanner && demoOtpVal) {
                        demoOtpVal.textContent = data.otp;
                        demoOtpBanner.style.display = 'flex';
                    }

                    showForgotAlert(`A 6-digit code has been generated & sent. Please enter it below.`, 'info');
                    setTimeout(() => otpInput && otpInput.focus(), 150);
                } else {
                    showForgotAlert(data.message || 'Unable to request password reset code.');
                }
            } catch (err) {
                console.error('OTP request error:', err);
                showForgotAlert('Network error. Please make sure the server is active.');
            } finally {
                sendBtn.disabled = false;
                sendBtn.innerHTML = `<span>Send Verification Code (OTP)</span> <i class="fa-solid fa-paper-plane"></i>`;
            }
        });
    }

    // Autofill OTP helper button
    if (demoOtpFillBtn && otpInput) {
        demoOtpFillBtn.addEventListener('click', () => {
            if (currentOtpCode) {
                otpInput.value = currentOtpCode;
                if (newPassInput) newPassInput.focus();
            }
        });
    }

    // Step 2: Verify OTP & Reset Password
    if (step2Form) {
        step2Form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const otp = otpInput.value.trim();
            const newPassword = newPassInput.value;
            const confirmPassword = confirmPassInput.value;

            if (!otp || otp.length !== 6) {
                showForgotAlert('Please enter the 6-digit verification code received.');
                return;
            }

            if (newPassword.length < 6) {
                showForgotAlert('Password must be at least 6 characters long.');
                return;
            }

            if (newPassword !== confirmPassword) {
                showForgotAlert('Passwords do not match. Please re-enter.');
                return;
            }

            hideForgotAlert();
            verifyBtn.disabled = true;
            verifyBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Updating Password...</span>`;

            try {
                const res = await fetch('/api/auth/forgot-password/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        identifier: activeResetUsername,
                        otp: otp,
                        new_password: newPassword
                    })
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    step2Form.classList.add('hidden');
                    step2Form.style.display = 'none';
                    hideForgotAlert();
                    successState.classList.remove('hidden');
                    successState.style.display = 'block';

                    // Pre-fill reset username into login input
                    if (usernameInput && activeResetUsername) {
                        usernameInput.value = activeResetUsername;
                        if (passwordInput) passwordInput.value = '';
                    }
                } else {
                    showForgotAlert(data.message || 'Invalid or expired code. Please check your SMS/Email.');
                }
            } catch (err) {
                console.error('Verify error:', err);
                showForgotAlert('Network error. Failed to reset password.');
            } finally {
                verifyBtn.disabled = false;
                verifyBtn.innerHTML = `<span>Confirm & Reset Password</span> <i class="fa-solid fa-check"></i>`;
            }
        });
    }

    // Back to Step 1
    if (backToStep1Btn) {
        backToStep1Btn.addEventListener('click', () => {
            hideForgotAlert();
            step2Form.classList.add('hidden');
            step2Form.style.display = 'none';
            step1Form.classList.remove('hidden');
            step1Form.style.display = 'block';
            identifierInput.focus();
        });
    }

    // Resend OTP
    if (resendOtpBtn) {
        resendOtpBtn.addEventListener('click', async () => {
            if (!activeResetUsername) return;
            resendOtpBtn.disabled = true;
            resendOtpBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Resending...`;

            try {
                const res = await fetch('/api/auth/forgot-password/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ identifier: activeResetUsername })
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    currentOtpCode = data.otp || '';
                    if (data.otp && demoOtpVal) {
                        demoOtpVal.textContent = data.otp;
                    }
                    showForgotAlert(`New verification code sent!`, 'success');
                } else {
                    showForgotAlert(data.message || 'Failed to resend code.');
                }
            } catch (err) {
                showForgotAlert('Network error. Could not resend code.');
            } finally {
                resendOtpBtn.disabled = false;
                resendOtpBtn.innerHTML = `<i class="fa-solid fa-rotate-right"></i> Resend Code`;
            }
        });
    }

    // Done / Go to Sign In
    if (doneBtn) {
        doneBtn.addEventListener('click', () => {
            closeForgotModal();
            passwordInput && passwordInput.focus();
        });
    }
}

// Initialize immediately if document is ready or wait for DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLoginPage);
} else {
    initLoginPage();
}

