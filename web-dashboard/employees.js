/**
 * Employee Roster Management Logic
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
        empRole: document.getElementById('emp-role'),
        empShift: document.getElementById('emp-shift'),
        empStatus: document.getElementById('emp-status'),
        cancelBtn: document.getElementById('emp-cancel-btn'),
        submitBtn: document.getElementById('emp-submit-btn')
    };

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
            const initials = emp.name.split(' ').map(n => n[0]).join('');

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
                    <span>Roster Shift</span>
                    <span class="trolley-stat-value" style="font-size: 0.8rem;">${emp.shift}</span>
                </div>
                <div style="margin-top: 10px; display: flex; gap: 8px;">
                    <button class="btn btn-outline edit-emp-btn" data-id="${emp.id}" style="flex: 1; padding: 6px 0; font-size: 0.8rem;">
                        <i class="fa-solid fa-pen"></i> Edit
                    </button>
                    <button class="btn btn-danger delete-emp-btn" data-id="${emp.id}" style="flex: 1; padding: 6px 0; font-size: 0.8rem;">
                        <i class="fa-solid fa-trash"></i> Remove
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
        els.empRole.value = "Cashier";
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
        els.empRole.value = emp.role;
        els.empShift.value = emp.shift;
        els.empStatus.value = emp.status;
        els.submitBtn.textContent = "Save Changes";
        els.modal.classList.add('active');
    }

    function closeRosterModal() {
        if (els.modal) els.modal.classList.remove('active');
    }

    async function handleFormSubmit(e) {
        e.preventDefault();
        
        const payload = {
            id: els.empId.value.trim(),
            name: els.empName.value.trim(),
            role: els.empRole.value,
            shift: els.empShift.value,
            status: els.empStatus.value
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
                    window.showToast("Roster Updated", `Saved records for ${payload.name}.`, "success");
                }
            }
        } catch (err) {
            console.error("Failed to save employee details:", err);
        }
    }

    async function deleteEmployee(id) {
        const emp = employees.find(e => e.id === id);
        if (!emp) return;

        if (!confirm(`Are you sure you want to remove employee "${emp.name}"?`)) {
            return;
        }

        try {
            const res = await fetch(`/api/employees/${id}`, {
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
    if (els.form) els.form.addEventListener('submit', handleFormSubmit);

    if (els.modal) {
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeRosterModal();
        });
    }

    fetchEmployees();
});
