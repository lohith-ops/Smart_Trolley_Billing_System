/**
 * Employee Roster Management Logic with Password Management
 */

document.addEventListener('DOMContentLoaded', () => {
    let employees = [];
    let customers = [];
    let currentTab = 'staff';
    let pendingDeleteCustomerId = null;
    let pendingDeleteCustomerName = null;

    const els = {
        container: document.getElementById('employees-container'),
        addBtn: document.getElementById('add-employee-btn'),
        modal: document.getElementById('employee-modal'),
        form: document.getElementById('employee-form'),
        modalTitle: document.getElementById('emp-modal-title'),
        empId: document.getElementById('emp-id'),
        empName: document.getElementById('emp-name'),
        empUsername: document.getElementById('emp-username'),
        empEmail: document.getElementById('emp-email'),
        empRole: document.getElementById('emp-role'),
        empPassword: document.getElementById('emp-password'),
        empPassGroup: document.getElementById('emp-password-group'),
        empShift: document.getElementById('emp-shift'),
        empStatus: document.getElementById('emp-status'),
        cancelBtn: document.getElementById('emp-cancel-btn'),
        submitBtn: document.getElementById('emp-submit-btn'),

        // Tab Navigation & Views
        tabStaffBtn: document.getElementById('tab-staff-btn'),
        tabCustBtn: document.getElementById('tab-cust-btn'),
        staffSection: document.getElementById('staff-view-section'),
        custSection: document.getElementById('customers-view-section'),
        staffBadgeCount: document.getElementById('staff-badge-count'),
        custBadgeCount: document.getElementById('cust-badge-count'),
        addCustBtn: document.getElementById('add-customer-btn'),
        custSearchWrapper: document.getElementById('customer-search-wrapper'),
        custSearchInput: document.getElementById('customer-search-input'),
        custMainSearch: document.getElementById('customer-main-search-input'),
        custSearchClearBtn: document.getElementById('customer-search-clear-btn'),
        custSearchCountLabel: document.getElementById('cust-search-count-label'),
        customersContainer: document.getElementById('customers-container'),

        // Customer Stats
        statCustTotal: document.getElementById('stat-cust-total'),
        statCustActive: document.getElementById('stat-cust-active'),
        statCustAssigned: document.getElementById('stat-cust-assigned'),

        // Delete Customer Modal Elements
        deleteCustModal: document.getElementById('delete-customer-modal'),
        deleteCustNameLabel: document.getElementById('delete-cust-name-label'),
        deleteCustIdLabel: document.getElementById('delete-cust-id-label'),
        deleteCustCancelBtn: document.getElementById('delete-cust-cancel-btn'),
        deleteCustConfirmBtn: document.getElementById('delete-cust-confirm-btn'),

        // Add Customer Modal Elements
        addCustModal: document.getElementById('add-customer-modal'),
        addCustForm: document.getElementById('add-customer-form'),
        addCustName: document.getElementById('add-cust-name'),
        addCustPhone: document.getElementById('add-cust-phone'),
        addCustEmail: document.getElementById('add-cust-email'),
        addCustId: document.getElementById('add-cust-id'),
        addCustCancelBtn: document.getElementById('add-cust-cancel-btn'),

        // Change Email Modal Elements
        changeEmailModal: document.getElementById('change-email-modal'),
        changeEmailForm: document.getElementById('change-email-form'),
        changeEmailEmpId: document.getElementById('change-email-emp-id'),
        changeEmailEmpName: document.getElementById('change-email-emp-name'),
        changeEmailNewEmail: document.getElementById('change-email-new-email'),
        changeEmailCancelBtn: document.getElementById('change-email-cancel-btn'),
        changeEmailSubmitBtn: document.getElementById('change-email-submit-btn'),

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
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/employees');
            if (res.ok) {
                employees = await res.json();
                if (els.staffBadgeCount) els.staffBadgeCount.textContent = employees.length;
                renderEmployees();
            }
        } catch (e) {
            console.error("Failed to load employee list:", e);
        }
    }

    function renderEmployees() {
        if (!els.container) return;
        els.container.innerHTML = '';
        if (els.staffBadgeCount) els.staffBadgeCount.textContent = employees.length;

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
                <div class="trolley-stat-row" style="align-items: center;">
                    <span>Registered Email</span>
                    <span class="trolley-stat-value" style="display: inline-flex; align-items: center; gap: 6px; color: ${emp.email ? 'var(--accent-cyan)' : 'var(--text-muted)'}; font-size: 0.82rem; word-break: break-all;">
                        <i class="${emp.email ? 'fa-solid' : 'fa-regular'} fa-envelope" style="opacity: 0.7;"></i>
                        <span class="emp-email-text">${emp.email || '<span style="font-style: italic; opacity: 0.7;">Not registered</span>'}</span>
                        <button type="button" class="quick-email-btn" data-id="${emp.id}" title="Change Email" style="background: rgba(6, 182, 212, 0.1); border: 1px solid rgba(6, 182, 212, 0.3); color: var(--accent-cyan); cursor: pointer; padding: 2px 6px; font-size: 0.7rem; border-radius: 4px; margin-left: 4px; transition: all 0.2s;">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                    </span>
                </div>
                <div class="trolley-stat-row">
                    <span>Roster Shift</span>
                    <span class="trolley-stat-value" style="font-size: 0.8rem;">${emp.shift}</span>
                </div>
                <div style="margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px;">
                    <button class="btn btn-outline edit-emp-btn" data-id="${emp.id}" style="padding: 6px 0; font-size: 0.75rem;" title="Edit employee details & email">
                        <i class="fa-solid fa-pen"></i> Edit
                    </button>
                    <button class="btn btn-outline reset-pass-btn" data-id="${emp.id}" style="padding: 6px 0; font-size: 0.75rem; border-color: rgba(6, 182, 212, 0.4); color: var(--accent-cyan);" title="Reset password">
                        <i class="fa-solid fa-key"></i> Key
                    </button>
                    <button class="btn btn-danger delete-emp-btn" data-id="${emp.id}" style="padding: 6px 0; font-size: 0.75rem;" title="Delete employee">
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

        document.querySelectorAll('.quick-email-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                openChangeEmailModal(id);
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
        if (els.empEmail) {
            els.empEmail.value = "";
            els.empEmail.readOnly = false;
        }
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
        if (els.empEmail) {
            els.empEmail.value = emp.email || "";
            els.empEmail.readOnly = false; // Always available to change email
        }
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

    // Change Email Modal
    function openChangeEmailModal(id) {
        if (!els.changeEmailModal) return;
        const emp = employees.find(e => e.id === id);
        if (!emp) return;

        els.changeEmailEmpId.value = emp.id;
        els.changeEmailEmpName.value = `${emp.name} (${emp.id})`;
        els.changeEmailNewEmail.value = emp.email || '';
        els.changeEmailModal.classList.add('active');
        setTimeout(() => els.changeEmailNewEmail.focus(), 100);
    }

    function closeChangeEmailModal() {
        if (els.changeEmailModal) els.changeEmailModal.classList.remove('active');
    }

    if (els.changeEmailForm) {
        els.changeEmailForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const empId = els.changeEmailEmpId.value;
            const newEmail = els.changeEmailNewEmail.value.trim();

            const emailPattern = /^[a-zA-Z0-9_.+-]+@gmail\.com$/i;
            if (newEmail && !emailPattern.test(newEmail)) {
                alert("Please enter a valid email address in the form of example@gmail.com.");
                if (els.changeEmailNewEmail) els.changeEmailNewEmail.focus();
                return;
            }

            try {
                const fetchFn = window.authFetch || fetch;
                const res = await fetchFn(`/api/employees/${encodeURIComponent(empId)}/email`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: newEmail })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    closeChangeEmailModal();
                    await fetchEmployees();
                    if (window.showToast) {
                        window.showToast("Email Updated", data.message || `Updated registered email for ${empId}.`, "success");
                    } else {
                        alert(data.message || "Email updated successfully!");
                    }
                } else {
                    alert(data.message || "Failed to update email.");
                }
            } catch (err) {
                console.error("Email update error:", err);
                alert("Unable to reach server to update email.");
            }
        });
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
            email: els.empEmail ? els.empEmail.value.trim() : '',
            role: els.empRole.value,
            shift: els.empShift.value,
            status: els.empStatus.value,
            password: els.empPassword ? els.empPassword.value.trim() : ''
        };

        const emailPattern = /^[a-zA-Z0-9_.+-]+@gmail\.com$/i;
        if (payload.email && !emailPattern.test(payload.email)) {
            alert("Please enter a valid email address in the form of example@gmail.com.");
            if (els.empEmail) els.empEmail.focus();
            return;
        }

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/employees', {
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
                const fetchFn = window.authFetch || fetch;
                const res = await fetchFn(`/api/employees/${encodeURIComponent(empId)}/password`, {
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
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn(`/api/employees/${encodeURIComponent(id)}`, {
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

    // ── Customer Management Logic ──────────────────────────────────────────

    async function fetchCustomers() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/customers');
            if (res.ok) {
                customers = await res.json();
                updateCustomerStats();
                renderCustomers(els.custSearchInput ? els.custSearchInput.value.trim() : '');
            }
        } catch (e) {
            console.error("Failed to load customer list:", e);
        }
    }

    function updateCustomerStats() {
        const total = customers.length;
        const active = customers.filter(c => (c.status || 'Active') === 'Active').length;
        const assigned = customers.filter(c => Boolean(c.assigned_trolley)).length;

        if (els.custBadgeCount) els.custBadgeCount.textContent = total;
        if (els.statCustTotal) els.statCustTotal.textContent = total;
        if (els.statCustActive) els.statCustActive.textContent = active;
        if (els.statCustAssigned) els.statCustAssigned.textContent = assigned;
    }

    let activeCustFilter = 'all';

    function renderCustomers(query = '') {
        if (!els.customersContainer) return;
        els.customersContainer.innerHTML = '';

        const q = query.toLowerCase().trim();
        let filtered = customers;

        // 1. Text Search Filter (name, id, phone, email, trolley)
        if (q) {
            filtered = filtered.filter(c => 
                (c.name && c.name.toLowerCase().includes(q)) ||
                (c.id && c.id.toLowerCase().includes(q)) ||
                (c.customer_id && c.customer_id.toLowerCase().includes(q)) ||
                (c.phone && c.phone.includes(q)) ||
                (c.email && c.email.toLowerCase().includes(q)) ||
                (c.assigned_trolley && c.assigned_trolley.toLowerCase().includes(q))
            );
        }

        // 2. Status / Assignment Filter
        if (activeCustFilter === 'assigned') {
            filtered = filtered.filter(c => Boolean(c.assigned_trolley));
        } else if (activeCustFilter === 'unassigned') {
            filtered = filtered.filter(c => !c.assigned_trolley);
        }

        // Update count indicator and clear button
        if (els.custSearchCountLabel) {
            const filterLabel = activeCustFilter !== 'all' ? ` (${activeCustFilter})` : '';
            if (q) {
                els.custSearchCountLabel.innerHTML = `Found <strong>${filtered.length}</strong> matching customer${filtered.length === 1 ? '' : 's'} for "<em>${query}</em>"${filterLabel}`;
            } else {
                els.custSearchCountLabel.textContent = `Showing ${filtered.length} of ${customers.length} registered customers${filterLabel}`;
            }
        }
        if (els.custSearchClearBtn) {
            els.custSearchClearBtn.style.display = q ? 'block' : 'none';
        }

        if (filtered.length === 0) {
            els.customersContainer.innerHTML = `
                <div class="glass-panel" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-magnifying-glass" style="font-size: 2.2rem; margin-bottom: 12px; color: var(--accent-cyan); opacity: 0.6;"></i>
                    <p style="font-size: 1.05rem; font-weight: 600; color: #fff; margin-bottom: 6px;">No customers found</p>
                    <p>${q ? `No registered customers match search term "${query}".` : 'No customers meet the selected filter criteria.'}</p>
                    ${q ? `<button type="button" class="btn btn-outline" id="cust-reset-search-btn" style="margin-top: 14px; font-size: 0.82rem; padding: 6px 14px;"><i class="fa-solid fa-rotate-left" style="margin-right: 6px;"></i> Clear Search</button>` : ''}
                </div>
            `;
            const resetBtn = document.getElementById('cust-reset-search-btn');
            if (resetBtn) {
                resetBtn.addEventListener('click', () => {
                    if (els.custMainSearch) els.custMainSearch.value = '';
                    if (els.custSearchInput) els.custSearchInput.value = '';
                    renderCustomers('');
                });
            }
            return;
        }

        filtered.forEach(cust => {
            const card = document.createElement('div');
            card.className = 'card glass-panel gradient-border employee-card';
            card.style.flexDirection = 'column';
            card.style.alignItems = 'stretch';
            card.style.gap = '14px';

            const cId = cust.id || cust.customer_id || cust.username || (cust._id ? String(cust._id) : '') || 'CUST';
            const initials = (cust.name || 'Customer').split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
            const trolleyLabel = cust.assigned_trolley ? 
                `<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 0.75rem; padding: 2px 8px; border-radius: 6px;"><i class="fa-solid fa-cart-shopping"></i> ${cust.assigned_trolley}</span>` : 
                `<span class="badge" style="background: rgba(148, 163, 184, 0.12); color: #94a3b8; font-size: 0.75rem; padding: 2px 8px; border-radius: 6px;">Unassigned</span>`;
            
            const spentFormatted = (typeof cust.total_spent === 'number') ? cust.total_spent.toFixed(2) : (cust.total_spent || '0.00');

            card.innerHTML = `
                <div class="employee-avatar-row" style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div class="employee-avatar" style="background: linear-gradient(135deg, #06b6d4, #3b82f6); color: #fff;">${initials}</div>
                        <div>
                            <div class="employee-name" style="font-weight: 700; font-size: 1.05rem;">${cust.name}</div>
                            <div style="font-size: 0.78rem; color: var(--accent-cyan); font-family: monospace; margin-top: 2px;">
                                <i class="fa-solid fa-id-card"></i> ${cId}
                            </div>
                        </div>
                    </div>
                    ${trolleyLabel}
                </div>

                <div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 10px 12px; font-size: 0.82rem; display: flex; flex-direction: column; gap: 6px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: var(--text-secondary);"><i class="fa-solid fa-phone" style="width: 14px;"></i> Phone</span>
                        <span style="color: var(--text-primary); font-weight: 500;">${cust.phone || '—'}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: var(--text-secondary);"><i class="fa-solid fa-envelope" style="width: 14px;"></i> Email</span>
                        <span style="color: var(--text-primary); font-weight: 500; word-break: break-all;">${cust.email || '—'}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 6px; margin-top: 2px;">
                        <span style="color: var(--text-secondary);"><i class="fa-solid fa-bag-shopping" style="width: 14px;"></i> Visits / Spent</span>
                        <span style="color: var(--accent-green); font-weight: 600;">${cust.total_visits || 0} visits • ₹${spentFormatted}</span>
                    </div>
                </div>

                <div class="employee-actions" style="display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid var(--panel-border); padding-top: 10px;">
                    <button class="btn btn-outline btn-cust-delete" data-id="${cId}" data-name="${cust.name}" style="border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; font-size: 0.8rem; padding: 6px 14px;">
                        <i class="fa-solid fa-trash-can" style="margin-right: 6px;"></i> Delete Customer
                    </button>
                </div>
            `;

            // Bind Delete button
            const deleteBtn = card.querySelector('.btn-cust-delete');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    openDeleteCustomerModal(cId, cust.name || cId);
                });
            }

            els.customersContainer.appendChild(card);
        });
    }

    function openDeleteCustomerModal(id, name) {
        pendingDeleteCustomerId = id;
        pendingDeleteCustomerName = name;

        if (els.deleteCustNameLabel) els.deleteCustNameLabel.textContent = name;
        if (els.deleteCustIdLabel) els.deleteCustIdLabel.textContent = id;
        if (els.deleteCustModal) {
            els.deleteCustModal.classList.add('active');
            els.deleteCustModal.style.display = 'flex';
        }
    }

    function closeDeleteCustomerModal() {
        pendingDeleteCustomerId = null;
        pendingDeleteCustomerName = null;
        if (els.deleteCustModal) {
            els.deleteCustModal.classList.remove('active');
            els.deleteCustModal.style.display = 'none';
        }
    }

    async function confirmDeleteCustomer() {
        if (!pendingDeleteCustomerId) return;
        const idToDelete = pendingDeleteCustomerId;
        const nameToDelete = pendingDeleteCustomerName || idToDelete;

        if (els.deleteCustConfirmBtn) {
            els.deleteCustConfirmBtn.disabled = true;
            els.deleteCustConfirmBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin" style="margin-right: 6px;"></i> Deleting...`;
        }

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn(`/api/customers/${encodeURIComponent(idToDelete)}?id=${encodeURIComponent(idToDelete)}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: idToDelete, customer_id: idToDelete })
            });
            
            let data = null;
            try {
                data = await res.json();
            } catch (jsonErr) {
                const text = await res.text().catch(() => '');
                data = { 
                    success: false, 
                    message: `Server returned HTTP ${res.status}: ${text ? text.slice(0, 100) : res.statusText || 'Unexpected server response'}` 
                };
            }

            if (res.ok && data && data.success) {
                closeDeleteCustomerModal();
                await fetchCustomers();
                if (window.showToast) {
                    window.showToast("Customer Deleted", `Removed customer "${nameToDelete}" and purged account records.`, "success");
                }
            } else {
                alert((data && data.message) || `Failed to delete customer (HTTP ${res.status}).`);
            }
        } catch (err) {
            console.error("Delete customer error:", err);
            alert(`Unable to delete customer: ${err.message || 'Network error. Please make sure Flask backend is running on port 5000.'}`);
        } finally {
            if (els.deleteCustConfirmBtn) {
                els.deleteCustConfirmBtn.disabled = false;
                els.deleteCustConfirmBtn.innerHTML = `<i class="fa-solid fa-trash-can" style="margin-right: 6px;"></i> Delete Customer`;
            }
        }
    }

    function openAddCustomerModal() {
        if (els.addCustForm) els.addCustForm.reset();
        if (els.addCustModal) {
            els.addCustModal.classList.add('active');
            els.addCustModal.style.display = 'flex';
        }
        if (els.addCustName) els.addCustName.focus();
    }

    function closeAddCustomerModal() {
        if (els.addCustModal) {
            els.addCustModal.classList.remove('active');
            els.addCustModal.style.display = 'none';
        }
    }

    async function handleAddCustomerSubmit(e) {
        e.preventDefault();
        const name = els.addCustName ? els.addCustName.value.trim() : '';
        const phone = els.addCustPhone ? els.addCustPhone.value.trim() : '';
        const email = els.addCustEmail ? els.addCustEmail.value.trim() : '';
        const custId = els.addCustId ? els.addCustId.value.trim() : '';

        if (!name || !phone) {
            alert("Name and 10-digit mobile number are required.");
            return;
        }

        const emailPattern = /^[a-zA-Z0-9_.+-]+@gmail\.com$/i;
        if (email && !emailPattern.test(email)) {
            alert("Please enter a valid email address in the form of example@gmail.com.");
            if (els.addCustEmail) els.addCustEmail.focus();
            return;
        }

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/customers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    phone: phone,
                    email: email,
                    id: custId
                })
            });
            const data = await res.json();

            if (res.ok && data.success) {
                closeAddCustomerModal();
                await fetchCustomers();
                if (window.showToast) {
                    window.showToast("Customer Registered", `Added customer "${name}" successfully.`, "success");
                }
            } else {
                alert(data.message || "Failed to register customer.");
            }
        } catch (err) {
            console.error("Registration error:", err);
            alert("Network error creating customer.");
        }
    }

    function switchTab(tab) {
        currentTab = tab;
        if (tab === 'staff') {
            if (els.tabStaffBtn) {
                els.tabStaffBtn.className = 'btn btn-primary';
            }
            if (els.tabCustBtn) {
                els.tabCustBtn.className = 'btn btn-outline';
            }
            if (els.staffSection) els.staffSection.style.display = 'block';
            if (els.custSection) els.custSection.style.display = 'none';
            if (els.addBtn) els.addBtn.style.display = 'inline-flex';
            if (els.addCustBtn) els.addCustBtn.style.display = 'none';
            if (els.custSearchWrapper) els.custSearchWrapper.style.display = 'none';
        } else {
            if (els.tabStaffBtn) {
                els.tabStaffBtn.className = 'btn btn-outline';
            }
            if (els.tabCustBtn) {
                els.tabCustBtn.className = 'btn btn-primary';
            }
            if (els.staffSection) els.staffSection.style.display = 'none';
            if (els.custSection) els.custSection.style.display = 'block';
            if (els.addBtn) els.addBtn.style.display = 'none';
            if (els.addCustBtn) els.addCustBtn.style.display = 'inline-flex';
            if (els.custSearchWrapper) els.custSearchWrapper.style.display = 'flex';
            fetchCustomers();
        }
    }

    // Bind tab events
    if (els.tabStaffBtn) els.tabStaffBtn.addEventListener('click', () => switchTab('staff'));
    if (els.tabCustBtn) els.tabCustBtn.addEventListener('click', () => switchTab('customers'));

    // Bind customer delete events
    if (els.deleteCustCancelBtn) els.deleteCustCancelBtn.addEventListener('click', closeDeleteCustomerModal);
    if (els.deleteCustConfirmBtn) els.deleteCustConfirmBtn.addEventListener('click', confirmDeleteCustomer);
    if (els.deleteCustModal) {
        els.deleteCustModal.addEventListener('click', (e) => {
            if (e.target === els.deleteCustModal) closeDeleteCustomerModal();
        });
    }

    // Bind customer add events
    if (els.addCustBtn) els.addCustBtn.addEventListener('click', openAddCustomerModal);
    if (els.addCustCancelBtn) els.addCustCancelBtn.addEventListener('click', closeAddCustomerModal);
    if (els.addCustForm) els.addCustForm.addEventListener('submit', handleAddCustomerSubmit);
    if (els.addCustModal) {
        els.addCustModal.addEventListener('click', (e) => {
            if (e.target === els.addCustModal) closeAddCustomerModal();
        });
    }

    // Bind customer search filter & toolbar
    function syncCustomerSearch(val) {
        if (els.custMainSearch && els.custMainSearch.value !== val) els.custMainSearch.value = val;
        if (els.custSearchInput && els.custSearchInput.value !== val) els.custSearchInput.value = val;
        renderCustomers(val);
    }

    if (els.custMainSearch) {
        els.custMainSearch.addEventListener('input', () => {
            syncCustomerSearch(els.custMainSearch.value);
        });
        els.custMainSearch.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                syncCustomerSearch('');
            }
        });
    }

    if (els.custSearchInput) {
        els.custSearchInput.addEventListener('input', () => {
            syncCustomerSearch(els.custSearchInput.value);
        });
    }

    if (els.custSearchClearBtn) {
        els.custSearchClearBtn.addEventListener('click', () => {
            syncCustomerSearch('');
            if (els.custMainSearch) els.custMainSearch.focus();
        });
    }

    document.querySelectorAll('.cust-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.cust-filter-btn').forEach(b => {
                b.className = 'btn btn-outline cust-filter-btn';
            });
            btn.className = 'btn btn-primary cust-filter-btn';
            activeCustFilter = btn.getAttribute('data-filter') || 'all';
            const curQ = (els.custMainSearch && els.custMainSearch.value) || (els.custSearchInput && els.custSearchInput.value) || '';
            renderCustomers(curQ);
        });
    });

    // Bind employee events
    if (els.addBtn) els.addBtn.addEventListener('click', openAddModal);
    if (els.cancelBtn) els.cancelBtn.addEventListener('click', closeRosterModal);
    if (els.changeEmailCancelBtn) els.changeEmailCancelBtn.addEventListener('click', closeChangeEmailModal);
    if (els.resetCancelBtn) els.resetCancelBtn.addEventListener('click', closeResetPasswordModal);
    if (els.form) els.form.addEventListener('submit', handleFormSubmit);

    if (els.modal) {
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeRosterModal();
        });
    }

    if (els.changeEmailModal) {
        els.changeEmailModal.addEventListener('click', (e) => {
            if (e.target === els.changeEmailModal) closeChangeEmailModal();
        });
    }

    if (els.resetModal) {
        els.resetModal.addEventListener('click', (e) => {
            if (e.target === els.resetModal) closeResetPasswordModal();
        });
    }

    fetchEmployees();
    fetchCustomers();
});
