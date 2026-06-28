/**
 * Configuration Settings Logic
 */

const els = {
    hwStatus: document.getElementById('hw-status'),
    serialPortInput: document.getElementById('serial-port-input'),
    hwForm: document.getElementById('settings-hw-form'),
    seedDbBtn: document.getElementById('seed-db-btn'),
    clearTxBtn: document.getElementById('clear-tx-btn')
};

// Initialize Settings
async function initSettings() {
    await fetchSettings();
    setInterval(fetchSettings, 3000); // Poll settings state

    if (els.hwForm) els.hwForm.addEventListener('submit', saveHardwareConfig);
    if (els.seedDbBtn) els.seedDbBtn.addEventListener('click', handleSeedDb);
    if (els.clearTxBtn) els.clearTxBtn.addEventListener('click', handleClearTx);
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
            alert(`Serial port updated to ${data.serialPort}. Attempting to connect...`);
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
            alert(data.message);
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
    if (!confirm("⚠️ CRITICAL WARNING!\nAre you sure you want to delete all transaction receipts and reset the live activity logs?\nThis action cannot be undone.")) {
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
            alert(data.message);
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

document.addEventListener('DOMContentLoaded', initSettings);
