/**
 * Customer Feedback Board Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let feedbackData = { feedbacks: [], averageRating: 5.0, totalResponses: 0 };

    const els = {
        container: document.getElementById('feedback-list-container'),
        avgText: document.getElementById('stat-avg-rating'),
        totalText: document.getElementById('stat-total-feedbacks'),
        openModalBtn: document.getElementById('submit-feedback-btn'),
        modal: document.getElementById('feedback-modal'),
        form: document.getElementById('feedback-form'),
        cancelBtn: document.getElementById('feedback-cancel-btn'),
        stars: document.querySelectorAll('#feedback-stars-input i'),
        ratingVal: document.getElementById('feedback-rating-val'),
        comments: document.getElementById('feedback-comments')
    };

    async function fetchFeedback() {
        try {
            const res = await fetch('/api/feedback');
            if (res.ok) {
                feedbackData = await res.json();
                renderFeedback();
            }
        } catch (e) {
            console.error("Failed to load feedback logs:", e);
        }
    }

    function renderFeedback() {
        if (els.avgText) els.avgText.textContent = `${feedbackData.averageRating.toFixed(1)} / 5.0`;
        if (els.totalText) els.totalText.textContent = feedbackData.totalResponses;

        if (!els.container) return;
        els.container.innerHTML = '';

        if (feedbackData.feedbacks.length === 0) {
            els.container.innerHTML = `
                <div class="empty-state">
                    <p>No customer reviews logged yet.</p>
                </div>
            `;
            return;
        }

        // Display recent feedback first
        const sorted = [...feedbackData.feedbacks].reverse();

        sorted.forEach(f => {
            const reviewCard = document.createElement('div');
            reviewCard.className = 'inventory-item';
            reviewCard.style.padding = '18px 24px';
            reviewCard.style.flexDirection = 'column';
            reviewCard.style.alignItems = 'stretch';
            reviewCard.style.gap = '8px';

            let starsHtml = '';
            for (let i = 1; i <= 5; i++) {
                if (i <= f.rating) {
                    starsHtml += `<i class="fa-solid fa-star" style="color: #f59e0b; margin-right: 4px;"></i>`;
                } else {
                    starsHtml += `<i class="fa-regular fa-star" style="color: var(--text-secondary); margin-right: 4px;"></i>`;
                }
            }

            reviewCard.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>${starsHtml}</div>
                    <span style="font-size: 0.8rem; color: var(--text-secondary);">${f.date || 'Today'}</span>
                </div>
                <p style="font-size: 0.95rem; color: var(--text-primary); line-height: 1.4;">
                    "${f.comments}"
                </p>
            `;
            els.container.appendChild(reviewCard);
        });
    }

    // Star clicking handler
    els.stars.forEach(star => {
        star.addEventListener('click', () => {
            const rating = parseInt(star.getAttribute('data-rating'));
            els.ratingVal.value = rating;
            
            els.stars.forEach(s => {
                const r = parseInt(s.getAttribute('data-rating'));
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

    function openModal() {
        if (!els.modal) return;
        els.comments.value = '';
        els.ratingVal.value = 5;
        els.stars.forEach(s => {
            s.classList.remove('fa-regular');
            s.classList.add('fa-solid', 'active');
        });
        els.modal.classList.add('active');
    }

    function closeModal() {
        if (els.modal) els.modal.classList.remove('active');
    }

    async function handleFormSubmit(e) {
        e.preventDefault();
        const payload = {
            rating: parseInt(els.ratingVal.value),
            comments: els.comments.value.trim()
        };

        try {
            const res = await fetch('/api/feedback', {
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
            }
        } catch (err) {
            console.error("Form submit error:", err);
        }
    }

    if (els.openModalBtn) els.openModalBtn.addEventListener('click', openModal);
    if (els.cancelBtn) els.cancelBtn.addEventListener('click', closeModal);
    if (els.form) els.form.addEventListener('submit', handleFormSubmit);

    if (els.modal) {
        els.modal.addEventListener('click', (e) => {
            if (e.target === els.modal) closeModal();
        });
    }

    fetchFeedback();
});
