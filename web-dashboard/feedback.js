/**
 * Customer Feedback Board Logic
 * Features:
 * - Real-time customer review display
 * - Interactive rating filter and text search
 * - Single review deletion with confirmation modal
 * - Bulk "Clear All Feedback" with confirmation modal
 * - Dynamic average rating and response count calculation
 */

document.addEventListener('DOMContentLoaded', () => {
    let feedbackData = { feedbacks: [], averageRating: 5.0, totalResponses: 0 };
    let activeFilter = 'all';
    let searchQuery = '';
    let pendingDeleteId = null;
    let pendingDeleteText = '';

    const els = {
        container: document.getElementById('feedback-list-container'),
        avgText: document.getElementById('stat-avg-rating'),
        totalText: document.getElementById('stat-total-feedbacks'),
        openModalBtn: document.getElementById('submit-feedback-btn'),
        clearAllBtn: document.getElementById('clear-all-feedback-btn'),

        // Submit Review Modal
        modal: document.getElementById('feedback-modal'),
        form: document.getElementById('feedback-form'),
        cancelBtn: document.getElementById('feedback-cancel-btn'),
        stars: document.querySelectorAll('#feedback-stars-input i'),
        ratingVal: document.getElementById('feedback-rating-val'),
        comments: document.getElementById('feedback-comments'),

        // Delete Single Feedback Modal
        deleteModal: document.getElementById('delete-feedback-modal'),
        deletePreview: document.getElementById('delete-feedback-preview'),
        deleteCancelBtn: document.getElementById('delete-feedback-cancel-btn'),
        deleteConfirmBtn: document.getElementById('delete-feedback-confirm-btn'),

        // Clear All Feedback Modal
        clearAllModal: document.getElementById('clear-all-feedback-modal'),
        clearAllCountLabel: document.getElementById('clear-all-count-label'),
        clearAllCancelBtn: document.getElementById('clear-all-cancel-btn'),
        clearAllConfirmBtn: document.getElementById('clear-all-confirm-btn'),

        // Search & Filters
        searchInput: document.getElementById('feedback-search-input'),
        filterTabs: document.querySelectorAll('.feedback-filter-btn')
    };

    async function fetchFeedback() {
        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/feedback');
            if (res.ok) {
                feedbackData = await res.json();
                renderFeedback();
            }
        } catch (e) {
            console.error("Failed to load feedback logs:", e);
        }
    }

    function renderFeedback() {
        const total = feedbackData.feedbacks ? feedbackData.feedbacks.length : 0;
        const avg = typeof feedbackData.averageRating === 'number' ? feedbackData.averageRating : 5.0;

        if (els.avgText) els.avgText.textContent = `${avg.toFixed(1)} / 5.0`;
        if (els.totalText) els.totalText.textContent = total;

        if (els.clearAllBtn) {
            els.clearAllBtn.style.display = total > 0 ? 'inline-flex' : 'none';
        }

        if (!els.container) return;
        els.container.innerHTML = '';

        if (!feedbackData.feedbacks || feedbackData.feedbacks.length === 0) {
            els.container.innerHTML = `
                <div class="glass-panel" style="padding: 40px; text-align: center; color: var(--text-secondary); border-radius: 12px;">
                    <i class="fa-solid fa-comments" style="font-size: 2.2rem; margin-bottom: 12px; opacity: 0.35;"></i>
                    <p style="font-size: 1rem; margin: 0;">No customer reviews logged yet.</p>
                    <p style="font-size: 0.8rem; opacity: 0.6; margin-top: 4px;">Click "Submit New Feedback" to add one.</p>
                </div>
            `;
            return;
        }

        // Apply rating filter and text search
        let filtered = [...feedbackData.feedbacks].reverse();

        if (activeFilter !== 'all') {
            const starNum = parseInt(activeFilter, 10);
            filtered = filtered.filter(f => f.rating === starNum);
        }

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(f =>
                (f.comments && f.comments.toLowerCase().includes(q)) ||
                (f.date && f.date.toLowerCase().includes(q))
            );
        }

        if (filtered.length === 0) {
            els.container.innerHTML = `
                <div class="glass-panel" style="padding: 30px; text-align: center; color: var(--text-secondary); border-radius: 12px;">
                    <i class="fa-solid fa-filter" style="font-size: 1.8rem; margin-bottom: 10px; opacity: 0.35;"></i>
                    <p style="font-size: 0.95rem; margin: 0;">No reviews match the selected filter or search term.</p>
                </div>
            `;
            return;
        }

        filtered.forEach(f => {
            const reviewCard = document.createElement('div');
            reviewCard.className = 'inventory-item review-card';
            reviewCard.style.padding = '18px 22px';
            reviewCard.style.display = 'flex';
            reviewCard.style.flexDirection = 'column';
            reviewCard.style.gap = '10px';
            reviewCard.style.borderRadius = '12px';
            reviewCard.style.background = 'rgba(255, 255, 255, 0.03)';
            reviewCard.style.border = '1px solid var(--panel-border)';
            reviewCard.style.transition = 'all 0.2s ease';

            let starsHtml = '';
            for (let i = 1; i <= 5; i++) {
                if (i <= f.rating) {
                    starsHtml += `<i class="fa-solid fa-star" style="color: #f59e0b; margin-right: 3px;"></i>`;
                } else {
                    starsHtml += `<i class="fa-regular fa-star" style="color: rgba(255,255,255,0.2); margin-right: 3px;"></i>`;
                }
            }

            const cleanComments = f.comments || '';
            const fid = f.id || f._id || '';

            reviewCard.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div>${starsHtml}</div>
                        <span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); font-size: 0.75rem; padding: 2px 8px; border-radius: 6px; font-weight: 600;">
                            ${f.rating}.0 / 5.0
                        </span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 0.8rem; color: var(--text-secondary);">
                            <i class="fa-regular fa-clock" style="margin-right: 4px;"></i>${f.date || 'Today'}
                        </span>
                        <button class="btn btn-outline btn-delete-feedback" data-id="${fid}" style="border-color: rgba(239, 68, 68, 0.35); color: #fca5a5; font-size: 0.78rem; padding: 4px 10px; border-radius: 6px; cursor: pointer;" title="Delete this review">
                            <i class="fa-solid fa-trash-can" style="margin-right: 4px;"></i> Delete
                        </button>
                    </div>
                </div>
                <p style="font-size: 0.95rem; color: var(--text-primary); line-height: 1.5; margin: 0; word-break: break-word;">
                    "${cleanComments}"
                </p>
            `;

            // Bind single delete button
            const delBtn = reviewCard.querySelector('.btn-delete-feedback');
            if (delBtn) {
                delBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    openDeleteModal(fid, cleanComments);
                });
            }

            els.container.appendChild(reviewCard);
        });
    }

    // ── Delete Single Feedback Modal ───────────────────────────────────────
    function openDeleteModal(id, comments) {
        pendingDeleteId = id;
        pendingDeleteText = comments;
        if (els.deletePreview) {
            els.deletePreview.textContent = `"${comments}"`;
        }
        if (els.deleteModal) {
            els.deleteModal.classList.add('active');
            els.deleteModal.style.display = 'flex';
        }
    }

    function closeDeleteModal() {
        pendingDeleteId = null;
        pendingDeleteText = '';
        if (els.deleteModal) {
            els.deleteModal.classList.remove('active');
            els.deleteModal.style.display = 'none';
        }
    }

    async function confirmDeleteFeedback() {
        if (!pendingDeleteId) return;
        const idToDelete = pendingDeleteId;

        if (els.deleteConfirmBtn) {
            els.deleteConfirmBtn.disabled = true;
            els.deleteConfirmBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin" style="margin-right: 6px;"></i> Deleting...`;
        }

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn(`/api/feedback/${encodeURIComponent(idToDelete)}?id=${encodeURIComponent(idToDelete)}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: idToDelete })
            });

            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                closeDeleteModal();
                await fetchFeedback();
                if (window.showToast) {
                    window.showToast("Review Deleted", "The customer feedback was removed.", "info");
                }
            } else {
                alert(data.message || `Failed to delete feedback review (HTTP ${res.status}).`);
            }
        } catch (err) {
            console.error("Delete feedback error:", err);
            alert("Network error: Unable to delete review.");
        } finally {
            if (els.deleteConfirmBtn) {
                els.deleteConfirmBtn.disabled = false;
                els.deleteConfirmBtn.innerHTML = `<i class="fa-solid fa-trash-can" style="margin-right: 6px;"></i> Delete Review`;
            }
        }
    }

    // ── Clear All Feedback Modal ───────────────────────────────────────────
    function openClearAllModal() {
        const total = feedbackData.feedbacks ? feedbackData.feedbacks.length : 0;
        if (els.clearAllCountLabel) {
            els.clearAllCountLabel.textContent = `${total} review${total === 1 ? '' : 's'}`;
        }
        if (els.clearAllModal) {
            els.clearAllModal.classList.add('active');
            els.clearAllModal.style.display = 'flex';
        }
    }

    function closeClearAllModal() {
        if (els.clearAllModal) {
            els.clearAllModal.classList.remove('active');
            els.clearAllModal.style.display = 'none';
        }
    }

    async function confirmClearAllFeedback() {
        if (els.clearAllConfirmBtn) {
            els.clearAllConfirmBtn.disabled = true;
            els.clearAllConfirmBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin" style="margin-right: 6px;"></i> Clearing...`;
        }

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/feedback/all?all=true', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'clear_all' })
            });

            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                closeClearAllModal();
                await fetchFeedback();
                if (window.showToast) {
                    window.showToast("Feedback Cleared", "All customer feedback reviews have been cleared.", "success");
                }
            } else {
                alert(data.message || `Failed to clear all feedback (HTTP ${res.status}).`);
            }
        } catch (err) {
            console.error("Clear all feedback error:", err);
            alert("Network error: Unable to clear feedback.");
        } finally {
            if (els.clearAllConfirmBtn) {
                els.clearAllConfirmBtn.disabled = false;
                els.clearAllConfirmBtn.innerHTML = `<i class="fa-solid fa-trash-can" style="margin-right: 6px;"></i> Delete All`;
            }
        }
    }

    // ── Submit Feedback Modal ──────────────────────────────────────────────
    function openModal() {
        if (!els.modal) return;
        els.comments.value = '';
        els.ratingVal.value = 5;
        els.stars.forEach(s => {
            s.classList.remove('fa-regular');
            s.classList.add('fa-solid', 'active');
        });
        els.modal.classList.add('active');
        els.modal.style.display = 'flex';
        if (els.comments) setTimeout(() => els.comments.focus(), 100);
    }

    function closeModal() {
        if (els.modal) {
            els.modal.classList.remove('active');
            els.modal.style.display = 'none';
        }
    }

    async function handleFormSubmit(e) {
        e.preventDefault();
        const payload = {
            rating: parseInt(els.ratingVal.value, 10),
            comments: els.comments.value.trim()
        };

        try {
            const fetchFn = window.authFetch || fetch;
            const res = await fetchFn('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                closeModal();
                await fetchFeedback();
                if (window.showToast) {
                    window.showToast("Review Submitted", "Thank you! Feedback received successfully.", "success");
                }
            } else {
                const data = await res.json().catch(() => ({}));
                alert(data.message || "Failed to submit review.");
            }
        } catch (err) {
            console.error("Form submit error:", err);
            alert("Network error submitting feedback.");
        }
    }

    // Star clicking handler
    els.stars.forEach(star => {
        star.addEventListener('click', () => {
            const rating = parseInt(star.getAttribute('data-rating'), 10);
            els.ratingVal.value = rating;

            els.stars.forEach(s => {
                const r = parseInt(s.getAttribute('data-rating'), 10);
                if (r <= rating) {
                    s.classList.remove('fa-regular');
                    s.classList.add('fa-solid', 'active');
                } else {
                    s.classList.remove('fa-solid', 'active');
                    s.classList.add('fa-regular');
                }
            });
        });
    });

    // Filter tabs
    els.filterTabs.forEach(btn => {
        btn.addEventListener('click', () => {
            els.filterTabs.forEach(b => {
                b.className = 'btn btn-outline feedback-filter-btn';
            });
            btn.className = 'btn btn-primary feedback-filter-btn';
            activeFilter = btn.getAttribute('data-rating') || 'all';
            renderFeedback();
        });
    });

    // Search input
    if (els.searchInput) {
        els.searchInput.addEventListener('input', () => {
            searchQuery = els.searchInput.value.trim();
            renderFeedback();
        });
    }

    // Modal triggers & event bindings
    if (els.openModalBtn) els.openModalBtn.addEventListener('click', openModal);
    if (els.cancelBtn) els.cancelBtn.addEventListener('click', closeModal);
    if (els.form) els.form.addEventListener('submit', handleFormSubmit);
    if (els.modal) {
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeModal();
        });
    }

    if (els.clearAllBtn) els.clearAllBtn.addEventListener('click', openClearAllModal);
    if (els.clearAllCancelBtn) els.clearAllCancelBtn.addEventListener('click', closeClearAllModal);
    if (els.clearAllConfirmBtn) els.clearAllConfirmBtn.addEventListener('click', confirmClearAllFeedback);
    if (els.clearAllModal) {
        els.clearAllModal.addEventListener('click', (e) => {
            if (e.target === els.clearAllModal) closeClearAllModal();
        });
    }

    if (els.deleteCancelBtn) els.deleteCancelBtn.addEventListener('click', closeDeleteModal);
    if (els.deleteConfirmBtn) els.deleteConfirmBtn.addEventListener('click', confirmDeleteFeedback);
    if (els.deleteModal) {
        els.deleteModal.addEventListener('click', (e) => {
            if (e.target === els.deleteModal) closeDeleteModal();
        });
    }

    // Escape key listener to close active modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            closeDeleteModal();
            closeClearAllModal();
        }
    });

    fetchFeedback();
});
