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
        restoreDbBtn: document.getElementById('restore-db-btn')
    };

    // Initialize Settings
    async function initSettings() {
        await fetchSettings();
        await fetchAvailablePorts();
        setInterval(fetchSettings, 3000); // Poll settings state

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

    initSettings();
});
