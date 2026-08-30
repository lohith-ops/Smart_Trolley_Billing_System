/**
 * Employee Roster Management Logic with Password Management
 */

document.addEventListener('DOMContentLoaded', () => {
    let employees = [];

    const els = {
        container: document.getElementById('employees-container'),
        addBtn: document.getElementById('add-employee-btn'),
        modal: document.getElementById('employee-modal'),
        form: document.getElementById('employee-form'),
        modalTitle: document.getElementById('emp-modal-title'),
        empId: document.getElementById('emp-id'),
        empName: document.getElementById('emp-name'),
        empUsername: document.getElementById('emp-username'),
        empRole: document.getElementById('emp-role'),
        empPassword: document.getElementById('emp-password'),
        empPassGroup: document.getElementById('emp-password-group'),
        empShift: document.getElementById('emp-shift'),
        empStatus: document.getElementById('emp-status'),
        cancelBtn: document.getElementById('emp-cancel-btn'),
        submitBtn: document.getElementById('emp-submit-btn'),

        // Reset Password Modal Elements
        resetModal: document.getElementById('reset-password-modal'),
        resetForm: document.getElementById('reset-password-form'),
        resetEmpId: document.getElementById('reset-emp-id'),
        resetEmpName: document.getElementById('reset-emp-name'),
        resetNewPass: document.getElementById('reset-new-password'),
        resetCancelBtn: document.getElementById('reset-cancel-btn'),
        resetSubmitBtn: document.getElementById('reset-submit-btn'),
        toggleResetPass: document.getElementById('toggle-reset-pass'),
        toggleResetIcon: document.getElementById('toggle-reset-icon')
    };

    // Auto-populate username suggestion as Name is typed
    if (els.empName && els.empUsername) {
        els.empName.addEventListener('input', () => {
            if (!els.empId.readOnly) {
                const suggested = els.empName.value.trim().toLowerCase().replace(/\s+/g, '');
                els.empUsername.value = suggested;
            }
        });
    }

    async function fetchEmployees() {
        try {
            const res = await fetch('/api/employees');
            if (res.ok) {
                employees = await res.json();
                renderEmployees();
            }
        } catch (e) {
            console.error("Failed to load employee list:", e);
        }
    }

    function renderEmployees() {
        if (!els.container) return;
        els.container.innerHTML = '';

        if (employees.length === 0) {
            els.container.innerHTML = `
                <div class="glass-panel" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-users" style="font-size: 2rem; margin-bottom: 12px; opacity:0.3;"></i>
                    <p>No employees registered. Click "Add Employee" to create one.</p>
                </div>
            `;
            return;
        }

        employees.forEach(emp => {
            const card = document.createElement('div');
            card.className = 'card glass-panel gradient-border employee-card';
            card.style.flexDirection = 'column';
            card.style.alignItems = 'stretch';
            card.style.gap = '12px';

            const statusClass = emp.status === 'Active' ? 'active' : (emp.status === 'On Leave' ? 'idle' : 'offline');
            const initials = emp.name.split(' ').map(n => n[0]).join('').toUpperCase();
            const loginUsername = emp.username || emp.name.toLowerCase().replace(/\s+/g, '') || emp.id.toLowerCase();

            card.innerHTML = `
                <div class="employee-avatar-row">
                    <div class="employee-avatar">${initials}</div>
                    <div>
                        <div class="employee-name">${emp.name}</div>
                        <div class="employee-role">${emp.role}</div>
                    </div>
                    <span class="trolley-status-badge ${statusClass}" style="margin-left: auto;">${emp.status}</span>
                </div>
                <div class="trolley-stat-row">
                    <span>Employee ID</span>
                    <span class="trolley-stat-value">${emp.id}</span>
                </div>
                <div class="trolley-stat-row">
                    <span>Login ID / User</span>
                    <span class="trolley-stat-value" style="color: var(--accent-cyan); font-weight: 600;">${loginUsername}</span>
                </div>
                <div class="trolley-stat-row">
                    <span>Roster Shift</span>
                    <span class="trolley-stat-value" style="font-size: 0.8rem;">${emp.shift}</span>
                </div>
                <div style="margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px;">
                    <button class="btn btn-outline edit-emp-btn" data-id="${emp.id}" style="padding: 6px 0; font-size: 0.75rem;">
                        <i class="fa-solid fa-pen"></i> Edit
                    </button>
                    <button class="btn btn-outline reset-pass-btn" data-id="${emp.id}" style="padding: 6px 0; font-size: 0.75rem; border-color: rgba(6, 182, 212, 0.4); color: var(--accent-cyan);">
                        <i class="fa-solid fa-key"></i> Key
                    </button>
                    <button class="btn btn-danger delete-emp-btn" data-id="${emp.id}" style="padding: 6px 0; font-size: 0.75rem;">
                        <i class="fa-solid fa-trash"></i> Del
                    </button>
                </div>
            `;
            els.container.appendChild(card);
        });

        // Event listeners
        document.querySelectorAll('.edit-emp-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                openEditModal(id);
            });
        });

        document.querySelectorAll('.reset-pass-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                openResetPasswordModal(id);
            });
        });

        document.querySelectorAll('.delete-emp-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                deleteEmployee(id);
            });
        });
    }

    function openAddModal() {
        if (!els.modal) return;
        els.modalTitle.textContent = "Register New Employee";
        els.empId.value = "";
        els.empId.readOnly = false;
        els.empId.classList.remove('readonly-input');
        els.empName.value = "";
        if (els.empUsername) els.empUsername.value = "";
        els.empRole.value = "Cashier";
        if (els.empPassword) els.empPassword.value = "";
        if (els.empPassGroup) els.empPassGroup.style.display = "block";
        els.empShift.value = "Morning (08:00 AM - 04:00 PM)";
        els.empStatus.value = "Active";
        els.submitBtn.textContent = "Add Employee";
        els.modal.classList.add('active');
    }

    function openEditModal(id) {
        if (!els.modal) return;
        const emp = employees.find(e => e.id === id);
        if (!emp) return;

        els.modalTitle.textContent = "Modify Employee Roster";
        els.empId.value = emp.id;
        els.empId.readOnly = true;
        els.empId.classList.add('readonly-input');
        els.empName.value = emp.name;
        if (els.empUsername) els.empUsername.value = emp.username || emp.name.toLowerCase().replace(/\s+/g, '') || emp.id.toLowerCase();
        els.empRole.value = emp.role;
        if (els.empPassword) els.empPassword.value = "";
        if (els.empPassGroup) els.empPassGroup.style.display = "none";
        els.empShift.value = emp.shift;
        els.empStatus.value = emp.status;
        els.submitBtn.textContent = "Save Changes";
        els.modal.classList.add('active');
    }

    function closeRosterModal() {
        if (els.modal) els.modal.classList.remove('active');
    }

    // Reset Password Modal
    function openResetPasswordModal(id) {
        if (!els.resetModal) return;
        const emp = employees.find(e => e.id === id);
        if (!emp) return;

        const loginUser = emp.username || emp.name.toLowerCase().replace(/\s+/g, '') || emp.id.toLowerCase();
        els.resetEmpId.value = emp.id;
        els.resetEmpName.value = `${emp.name} (Login: ${loginUser})`;
        els.resetNewPass.value = '';
        els.resetModal.classList.add('active');
        setTimeout(() => els.resetNewPass.focus(), 100);
    }

    function closeResetPasswordModal() {
        if (els.resetModal) els.resetModal.classList.remove('active');
    }

    // Toggle Password Visibility in Reset Modal
    if (els.toggleResetPass && els.resetNewPass && els.toggleResetIcon) {
        els.toggleResetPass.addEventListener('click', () => {
            const isPass = els.resetNewPass.type === 'password';
            els.resetNewPass.type = isPass ? 'text' : 'password';
            els.toggleResetIcon.className = isPass ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
        });
    }

    // Form Submit Handler for Add / Edit Employee
    async function handleFormSubmit(e) {
        e.preventDefault();
        
        const rawUsername = els.empUsername ? els.empUsername.value.trim().toLowerCase() : '';
        const suggestedUser = rawUsername || els.empName.value.trim().toLowerCase().replace(/\s+/g, '') || els.empId.value.trim().toLowerCase();

        const payload = {
            id: els.empId.value.trim(),
            name: els.empName.value.trim(),
            username: suggestedUser,
            role: els.empRole.value,
            shift: els.empShift.value,
            status: els.empStatus.value,
            password: els.empPassword ? els.empPassword.value.trim() : ''
        };

        try {
            const res = await fetch('/api/employees', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                closeRosterModal();
                await fetchEmployees();
                if (window.showToast) {
                    window.showToast("Roster Updated", `Saved record & login credentials for ${payload.name} (Login: ${payload.username}).`, "success");
                }
            } else {
                const data = await res.json();
                alert(data.message || "Failed to save employee.");
            }
        } catch (err) {
            console.error("Failed to save employee details:", err);
            alert("Error communicating with server. Please ensure the backend is running.");
        }
    }

    // Form Submit Handler for Password Reset
    if (els.resetForm) {
        els.resetForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const empId = els.resetEmpId.value;
            const newPassword = els.resetNewPass.value;

            if (!newPassword || newPassword.length < 6) {
                alert("Password must be at least 6 characters long.");
                return;
            }

            try {
                const res = await fetch(`/api/employees/${encodeURIComponent(empId)}/password`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: newPassword })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    closeResetPasswordModal();
                    if (window.showToast) {
                        window.showToast("Password Reset", data.message || "Employee password has been updated.", "success");
                    } else {
                        alert(data.message || "Password updated successfully!");
                    }
                } else {
                    alert(data.message || "Failed to reset password. Please verify your admin privileges.");
                }
            } catch (err) {
                console.error("Password reset error:", err);
                alert("Unable to reach server to update password. Please check your backend connection.");
            }
        });
    }

    async function deleteEmployee(id) {
        const emp = employees.find(e => e.id === id);
        if (!emp) return;

        if (!confirm(`Are you sure you want to remove employee "${emp.name}"?`)) {
            return;
        }

        try {
            const res = await fetch(`/api/employees/${encodeURIComponent(id)}`, {
                method: 'DELETE'
            });

            if (res.ok) {
                await fetchEmployees();
                if (window.showToast) {
                    window.showToast("Roster Updated", `Removed employee record.`, "info");
                }
            }
        } catch (err) {
            console.error("Failed to delete employee:", err);
        }
    }

    // Bind events
    if (els.addBtn) els.addBtn.addEventListener('click', openAddModal);
    if (els.cancelBtn) els.cancelBtn.addEventListener('click', closeRosterModal);
    if (els.resetCancelBtn) els.resetCancelBtn.addEventListener('click', closeResetPasswordModal);
    if (els.form) els.form.addEventListener('submit', handleFormSubmit);

    if (els.modal) {
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeRosterModal();
        });
    }

    if (els.resetModal) {
        els.resetModal.addEventListener('click', (e) => {
            if (e.target === els.resetModal) closeResetPasswordModal();
        });
    }

    fetchEmployees();
});
