/**
 * Configuration Settings Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    const els = {
        hwStatus: document.getElementById('hw-status'),
        serialPortInput: document.getElementById('serial-port-input'),
        portsSelect: document.getElementById('available-ports-select'),
        refreshPortsBtn: document.getElementById('refresh-ports-btn'),
        hwForm: document.getElementById('settings-hw-form'),
        seedDbBtn: document.getElementById('seed-db-btn'),
        clearTxBtn: document.getElementById('clear-tx-btn'),
        backupDbBtn: document.getElementById('backup-db-btn'),
        restoreDbBtn: document.getElementById('restore-db-btn'),

        // Payment Configuration Elements
        paymentForm: document.getElementById('settings-payment-form'),
        storeNameInput: document.getElementById('store-name-input'),
        upiIdInput: document.getElementById('upi-id-input'),
        qrModeDynamic: document.getElementById('qr-mode-dynamic'),
        qrModeCustom: document.getElementById('qr-mode-custom'),
        qrFileInput: document.getElementById('qr-file-input'),
        chooseQrBtn: document.getElementById('choose-qr-btn'),
        removeQrBtn: document.getElementById('remove-qr-btn'),
        qrPreviewContainer: document.getElementById('qr-preview-container'),
        qrPreviewImg: document.getElementById('qr-preview-img'),
        qrPreviewFilename: document.getElementById('qr-preview-filename')
    };

    let currentQrBase64 = "";

    // Initialize Settings
    async function initSettings() {
        await fetchSettings();
        await fetchPaymentSettings();
        await fetchAvailablePorts();
        setupQrUploadEvents();
        setInterval(fetchSettings, 3000); // Poll settings state

        if (els.paymentForm) els.paymentForm.addEventListener('submit', handlePaymentSubmit);
        if (els.hwForm) els.hwForm.addEventListener('submit', saveHardwareConfig);
        if (els.refreshPortsBtn) els.refreshPortsBtn.addEventListener('click', fetchAvailablePorts);
        if (els.portsSelect) {
            els.portsSelect.addEventListener('change', (e) => {
                if (e.target.value && els.serialPortInput) {
                    els.serialPortInput.value = e.target.value;
                }
            });
        }
        if (els.seedDbBtn) els.seedDbBtn.addEventListener('click', handleSeedDb);
        if (els.clearTxBtn) els.clearTxBtn.addEventListener('click', handleClearTx);
        if (els.backupDbBtn) els.backupDbBtn.addEventListener('click', handleBackup);
        if (els.restoreDbBtn) els.restoreDbBtn.addEventListener('click', handleRestore);
    }

    // Fetch active available serial ports from system
    async function fetchAvailablePorts() {
        if (!els.portsSelect) return;
        try {
            const res = await fetch('/api/settings/ports');
            if (res.ok) {
                const data = await res.json();
                els.portsSelect.innerHTML = '';
                
                if (data.ports && data.ports.length > 0) {
                    const defaultOpt = document.createElement('option');
                    defaultOpt.value = '';
                    defaultOpt.textContent = `-- Select Connected Device (${data.ports.length} found) --`;
                    els.portsSelect.appendChild(defaultOpt);

                    data.ports.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p.port;
                        opt.textContent = `${p.port} - ${p.description}`;
                        if (p.port === data.currentPort || p.port === els.serialPortInput.value) {
                            opt.selected = true;
                        }
                        els.portsSelect.appendChild(opt);
                    });
                } else {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = 'No active COM ports detected (Plug in device & refresh)';
                    els.portsSelect.appendChild(opt);
                }
            }
        } catch (e) {
            console.error("Failed to fetch available COM ports:", e);
        }
    }

    // Fetch active config settings from server
    async function fetchSettings() {
        try {
            const res = await fetch('/api/dashboard');
            if (res.ok) {
                const data = await res.json();
                
                // Set input field default if not currently focused (avoid cursor jumping)
                if (els.serialPortInput && document.activeElement !== els.serialPortInput) {
                    els.serialPortInput.value = data.serialPort || '';
                }

                // Update Connection indicators
                if (els.hwStatus) {
                    const dot = els.hwStatus.querySelector('.pulse-dot');
                    const text = els.hwStatus.querySelector('span:last-child');
                    
                    if (data.arduinoConnected) {
                        els.hwStatus.className = "status-text online";
                        dot.style.backgroundColor = "var(--accent-green)";
                        dot.style.boxShadow = "0 0 10px var(--accent-green)";
                        text.textContent = `Connected (${data.serialPort})`;
                    } else {
                        els.hwStatus.className = "status-text offline";
                        dot.style.backgroundColor = "var(--accent-red)";
                        dot.style.boxShadow = "none";
                        text.textContent = "Disconnected";
                    }
                }
            }
        } catch(e) {
            console.error("Failed to query settings status:", e);
        }
    }

    // Save dynamic COM port configuration
    async function saveHardwareConfig(e) {
        e.preventDefault();

        const submitBtn = els.hwForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        const payload = {
            serialPort: els.serialPortInput.value.trim()
        };

        try {
            const res = await fetch('/api/settings/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (data.success) {
                if (window.showToast) {
                    window.showToast('Settings Saved', `Serial port updated to ${data.serialPort}. Attempting to connect...`, 'success');
                } else {
                    alert(`Serial port updated to ${data.serialPort}. Attempting to connect...`);
                }
                await fetchSettings();
            } else {
                alert(data.message || "Failed to update configuration.");
            }
        } catch (err) {
            console.error("Hardware save error:", err);
            alert("Network error while updating configurations.");
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-save"></i> Save Port Configuration';
        }
    }

    // Handle database catalog seeding
    async function handleSeedDb() {
        if (!confirm("Are you sure you want to reset the catalog?\nThis will clear all current products and import default items.")) {
            return;
        }

        els.seedDbBtn.disabled = true;
        const origHtml = els.seedDbBtn.innerHTML;
        els.seedDbBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Seeding database...';

        try {
            const res = await fetch('/api/settings/database', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'seed' })
            });
            const data = await res.json();
            if (data.success) {
                if (window.showToast) window.showToast('Database Seeded', data.message, 'success');
                else alert(data.message);
            } else {
                alert(data.message || "Seeding failed.");
            }
        } catch (e) {
            console.error("Database seed error:", e);
            alert("Network error during database operation.");
        } finally {
            els.seedDbBtn.disabled = false;
            els.seedDbBtn.innerHTML = origHtml;
        }
    }

    // Handle database logs clearing
    async function handleClearTx() {
        if (!confirm("\u26a0\ufe0f CRITICAL WARNING!\nAre you sure you want to delete all transaction receipts and reset the live activity logs?\nThis action cannot be undone.")) {
            return;
        }

        els.clearTxBtn.disabled = true;
        const origHtml = els.clearTxBtn.innerHTML;
        els.clearTxBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Clearing logs...';

        try {
            const res = await fetch('/api/settings/database', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'clear_transactions' })
            });
            const data = await res.json();
            if (data.success) {
                if (window.showToast) window.showToast('Logs Cleared', data.message, 'info');
                else alert(data.message);
            } else {
                alert(data.message || "Operation failed.");
            }
        } catch (e) {
            console.error("Database clear error:", e);
            alert("Network error during database operation.");
        } finally {
            els.clearTxBtn.disabled = false;
            els.clearTxBtn.innerHTML = origHtml;
        }
    }

    // Handle database backup
    async function handleBackup() {
        els.backupDbBtn.disabled = true;
        const origHtml = els.backupDbBtn.innerHTML;
        els.backupDbBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Creating backup...';

        try {
            const res = await fetch('/api/settings/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (data.success) {
                if (window.showToast) window.showToast('Backup Created', data.message, 'success');
                else alert(data.message);
            } else {
                alert(data.message || "Backup failed.");
            }
        } catch (e) {
            console.error("Backup error:", e);
            alert("Network error during backup.");
        } finally {
            els.backupDbBtn.disabled = false;
            els.backupDbBtn.innerHTML = origHtml;
        }
    }

    // Handle database restore
    async function handleRestore() {
        if (!confirm("⚠️ WARNING!\nThis will overwrite current products and transactions with the backup file.\nAre you sure you want to continue?")) {
            return;
        }

        els.restoreDbBtn.disabled = true;
        const origHtml = els.restoreDbBtn.innerHTML;
        els.restoreDbBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Restoring...';

        try {
            const res = await fetch('/api/settings/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (data.success) {
                if (window.showToast) window.showToast('Restore Complete', data.message, 'success');
                else alert(data.message);
            } else {
                alert(data.message || "Restore failed.");
            }
        } catch (e) {
            console.error("Restore error:", e);
            alert("Network error during restore.");
        } finally {
            els.restoreDbBtn.disabled = false;
            els.restoreDbBtn.innerHTML = origHtml;
        }
    }

    // ── Payment & UPI Configuration ───────────────────────────────────────────
    async function fetchPaymentSettings() {
        try {
            const res = await fetch('/api/settings/payment');
            if (res.ok) {
                const data = await res.json();
                if (els.storeNameInput) els.storeNameInput.value = data.storeName || 'Smart Supermarket';
                if (els.upiIdInput) els.upiIdInput.value = data.upiId || 'smartsupermarket@okaxis';
                
                if (data.useCustomQr) {
                    if (els.qrModeCustom) els.qrModeCustom.checked = true;
                } else {
                    if (els.qrModeDynamic) els.qrModeDynamic.checked = true;
                }

                if (data.customQrImage) {
                    currentQrBase64 = data.customQrImage;
                    if (els.qrPreviewImg) els.qrPreviewImg.src = data.customQrImage;
                    if (els.qrPreviewContainer) els.qrPreviewContainer.style.display = 'flex';
                    if (els.removeQrBtn) els.removeQrBtn.style.display = 'inline-flex';
                    if (els.qrPreviewFilename) els.qrPreviewFilename.textContent = "Uploaded Standee QR Image";
                }
            }
        } catch (e) {
            console.error("Failed to load payment settings:", e);
        }
    }

    function setupQrUploadEvents() {
        if (els.chooseQrBtn && els.qrFileInput) {
            els.chooseQrBtn.addEventListener('click', () => {
                els.qrFileInput.click();
            });
        }

        if (els.qrFileInput) {
            els.qrFileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (!file) return;

                if (!file.type.startsWith('image/')) {
                    if (window.showToast) window.showToast('Invalid File', 'Please select a valid PNG or JPG image file.', 'warning');
                    else alert('Please select a valid image file.');
                    return;
                }

                // Check file size (< 3MB)
                if (file.size > 3 * 1024 * 1024) {
                    if (window.showToast) window.showToast('File Too Large', 'Please select an image smaller than 3MB.', 'warning');
                    else alert('Please select an image smaller than 3MB.');
                    return;
                }

                const reader = new FileReader();
                reader.onload = (loadEvt) => {
                    currentQrBase64 = loadEvt.target.result;
                    if (els.qrPreviewImg) els.qrPreviewImg.src = currentQrBase64;
                    if (els.qrPreviewContainer) els.qrPreviewContainer.style.display = 'flex';
                    if (els.removeQrBtn) els.removeQrBtn.style.display = 'inline-flex';
                    if (els.qrPreviewFilename) els.qrPreviewFilename.textContent = file.name;
                    if (els.qrModeCustom) els.qrModeCustom.checked = true;
                    if (window.showToast) window.showToast('QR Loaded', `Loaded ${file.name}. Click Save Configuration to apply.`, 'info');
                };
                reader.readAsDataURL(file);
            });
        }

        if (els.removeQrBtn) {
            els.removeQrBtn.addEventListener('click', () => {
                currentQrBase64 = "";
                if (els.qrFileInput) els.qrFileInput.value = "";
                if (els.qrPreviewImg) els.qrPreviewImg.src = "";
                if (els.qrPreviewContainer) els.qrPreviewContainer.style.display = 'none';
                els.removeQrBtn.style.display = 'none';
                if (els.qrModeDynamic) els.qrModeDynamic.checked = true;
                if (window.showToast) window.showToast('QR Removed', 'Custom QR image cleared. Switched to Dynamic Amount QR.', 'info');
            });
        }
    }

    async function handlePaymentSubmit(e) {
        e.preventDefault();
        const submitBtn = document.getElementById('save-payment-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        }

        const useCustomQr = els.qrModeCustom ? els.qrModeCustom.checked : false;

        if (useCustomQr && !currentQrBase64) {
            if (window.showToast) window.showToast('Upload Required', 'Please choose a QR image file or select Dynamic Amount QR mode.', 'warning');
            else alert('Please choose a QR image file or select Dynamic Amount QR mode.');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-save"></i> Save Payment Configuration';
            }
            return;
        }

        const payload = {
            storeName: els.storeNameInput ? els.storeNameInput.value.trim() : 'Smart Supermarket',
            upiId: els.upiIdInput ? els.upiIdInput.value.trim() : 'smartsupermarket@okaxis',
            useCustomQr: useCustomQr,
            customQrImage: currentQrBase64
        };

        try {
            const token = (typeof getAuthToken === 'function') ? getAuthToken() : localStorage.getItem('smart_trolley_jwt_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch('/api/settings/payment', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok && data.success) {
                if (window.showToast) window.showToast('Payment Config Saved', data.message || 'Payment settings updated successfully!', 'success');
                else alert(data.message || 'Payment settings updated successfully!');
            } else {
                alert(data.message || 'Failed to save payment settings.');
            }
        } catch (err) {
            console.error('Payment save error:', err);
            alert('Network error while saving payment settings.');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-save"></i> Save Payment Configuration';
            }
        }
    }

    // ── Email & SMS Notification Gateways ────────────────────────────────────
    const notifForm       = document.getElementById('settings-notifications-form');
    const smtpUserInput   = document.getElementById('smtp-user-input');
    const smtpPassInput   = document.getElementById('smtp-pass-input');
    const smtpServerInput = document.getElementById('smtp-server-input');
    const smtpPortInput   = document.getElementById('smtp-port-input');
    const fast2smsKeyInput= document.getElementById('fast2sms-key-input');
    const twilioSidInput  = document.getElementById('twilio-sid-input');
    const testNotifBtn    = document.getElementById('test-notification-btn');

    async function fetchNotificationSettings() {
        try {
            const token = (typeof getAuthToken === 'function') ? getAuthToken() : localStorage.getItem('smart_trolley_jwt_token');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch('/api/settings/notifications', { headers });
            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    if (smtpUserInput)   smtpUserInput.value = data.smtpUser || '';
                    if (smtpPassInput && data.smtpPasswordSet) smtpPassInput.placeholder = '•••••••• (Configured)';
                    if (smtpServerInput) smtpServerInput.value = data.smtpServer || 'smtp.gmail.com';
                    if (smtpPortInput)   smtpPortInput.value = data.smtpPort || 587;
                    if (fast2smsKeyInput && data.fast2smsApiKeySet) fast2smsKeyInput.placeholder = '•••••••• (Configured)';
                    if (twilioSidInput)  twilioSidInput.value = data.twilioSid || '';
                }
            }
        } catch (err) {
            console.error('Failed to fetch notification settings:', err);
        }
    }

    async function saveNotificationSettings(e) {
        e.preventDefault();
        const submitBtn = document.getElementById('save-notifications-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
        }

        const payload = {
            smtpUser:        smtpUserInput ? smtpUserInput.value.trim() : '',
            smtpPassword:    smtpPassInput ? smtpPassInput.value : '',
            smtpServer:      smtpServerInput ? smtpServerInput.value.trim() : 'smtp.gmail.com',
            smtpPort:        smtpPortInput ? parseInt(smtpPortInput.value) || 587 : 587,
            fast2smsApiKey:  fast2smsKeyInput ? fast2smsKeyInput.value.trim() : '',
            twilioSid:       twilioSidInput ? twilioSidInput.value.trim() : ''
        };

        try {
            const token = (typeof getAuthToken === 'function') ? getAuthToken() : localStorage.getItem('smart_trolley_jwt_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch('/api/settings/notifications', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (res.ok && data.success) {
                if (window.showToast) window.showToast('Gateways Saved', data.message || 'Notification gateways saved!', 'success');
                else alert(data.message || 'Notification gateways saved!');
                fetchNotificationSettings();
            } else {
                alert(data.message || 'Failed to save notification settings.');
            }
        } catch (err) {
            console.error('Notification save error:', err);
            alert('Network error while saving notification gateways.');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fa-solid fa-save"></i> Save Notification Gateways';
            }
        }
    }

    async function handleTestNotification() {
        const testChoice = prompt("What would you like to test?\nEnter 'email' or 'sms':", "email");
        if (!testChoice) return;

        const choiceClean = testChoice.trim().toLowerCase();
        if (choiceClean !== 'email' && choiceClean !== 'sms') {
            alert("Invalid choice. Please enter 'email' or 'sms'.");
            return;
        }

        const promptText = (choiceClean === 'email') ? "Enter destination email (e.g. yourname@gmail.com):" : "Enter 10-digit mobile number (e.g. 9876543210):";
        const target = prompt(promptText);
        if (!target) return;

        if (testNotifBtn) {
            testNotifBtn.disabled = true;
            testNotifBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';
        }

        try {
            const token = (typeof getAuthToken === 'function') ? getAuthToken() : localStorage.getItem('smart_trolley_jwt_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const res = await fetch('/api/settings/notifications/test', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ type: choiceClean, target: target.trim() })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                if (window.showToast) window.showToast('Test Sent', data.message, 'success');
                else alert(data.message);
            } else {
                alert(`Test Failed: ${data.message}`);
            }
        } catch (err) {
            console.error('Test notification error:', err);
            alert('Failed to send test dispatch. Check server logs.');
        } finally {
            if (testNotifBtn) {
                testNotifBtn.disabled = false;
                testNotifBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Test Delivery';
            }
        }
    }

    if (notifForm) notifForm.addEventListener('submit', saveNotificationSettings);
    if (testNotifBtn) testNotifBtn.addEventListener('click', handleTestNotification);

    // Add to initial loaders
    fetchNotificationSettings();
    initSettings();
});
