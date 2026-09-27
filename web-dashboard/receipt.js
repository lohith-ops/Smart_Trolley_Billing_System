/**
 * Digital Receipt Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let transaction = null;

    let currentStoreName = "GECM Supermarket";
    let currentStoreAddress = "GECM CAMPUS, HASSAN";

    const els = {
        storeName: document.getElementById('receipt-store-name'),
        storeAddress: document.getElementById('receipt-store-address'),
        invoiceNo: document.getElementById('invoice-no'),
        invoiceDate: document.getElementById('invoice-date'),
        invoiceCustomer: document.getElementById('invoice-customer'),
        invoiceTrolley: document.getElementById('invoice-trolley'),
        paymentMode: document.getElementById('invoice-payment-mode'),
        itemsBody: document.getElementById('invoice-items-body'),
        qtyTotal: document.getElementById('invoice-qty-total'),
        subtotal: document.getElementById('invoice-subtotal'),
        cgst: document.getElementById('invoice-cgst'),
        sgst: document.getElementById('invoice-sgst'),
        grandTotal: document.getElementById('invoice-grand-total'),
        pointsEarned: document.getElementById('invoice-points-earned'),
        qrImage: document.getElementById('invoice-qr'),
        btnPrint: document.getElementById('btn-print-receipt'),
        btnPdf: document.getElementById('btn-pdf-receipt')
    };

    // Load invoice and store settings
    async function loadInvoice() {
        const urlParams = new URLSearchParams(window.location.search);
        const timestamp = parseFloat(urlParams.get('timestamp'));
        const txId = urlParams.get('id');

        // Fetch store settings for store name
        try {
            const setRes = await fetch('/api/settings/payment');
            if (setRes.ok) {
                const setData = await setRes.json();
                if (setData.storeName) {
                    currentStoreName = setData.storeName;
                }
            }
        } catch (e) {
            console.warn("Could not fetch store settings:", e);
        }

        if (els.storeName) els.storeName.textContent = currentStoreName;
        if (els.storeAddress) els.storeAddress.textContent = currentStoreAddress;
        document.title = `${currentStoreName} - Digital Invoice Receipt`;

        try {
            const res = await fetch('/api/transactions');
            if (res.ok) {
                const txs = await res.json();
                if (txs && txs.length > 0) {
                    if (txId) {
                        transaction = txs.find(t => t.transaction_id === txId || t._id === txId);
                    }
                    if (!transaction && !isNaN(timestamp)) {
                        transaction = txs.find(t => Math.abs(t.timestamp - timestamp) < 3.0);
                    }
                    // If no timestamp or not matched, default to the most recent transaction
                    if (!transaction && (isNaN(timestamp) || !urlParams.has('timestamp'))) {
                        transaction = txs[0];
                    }
                }
            }
        } catch (e) {
            console.error("Failed to load matching transaction for receipt:", e);
        }

        // Fallback to mock invoice if not found and no transactions exist in DB
        if (!transaction) {
            transaction = {
                timestamp: Date.now() / 1000,
                total: 60.00,
                paymentMethod: "UPI",
                trolley_id: "TROLLEY-001",
                items: {
                    "5C1E7E05": { name: "Rice 1kg", price: 60.00, quantity: 1, subtotal: 60.00 }
                }
            };
        }

        renderReceipt();
    }

    function renderReceipt() {
        const date = new Date(transaction.timestamp * 1000);
        const dateString = date.toLocaleString();
        
        // Construct transaction/invoice hash ID based on timestamp
        const txHash = `TXN-${Math.floor(transaction.timestamp)}`;
        
        if (els.storeName) els.storeName.textContent = currentStoreName;
        if (els.invoiceNo) els.invoiceNo.textContent = txHash;
        if (els.invoiceDate) els.invoiceDate.textContent = dateString;
        if (els.invoiceCustomer) {
            els.invoiceCustomer.textContent = transaction.customerPhone ? `+91 ${transaction.customerPhone}` : 'Walk-in Customer';
        }
        if (els.invoiceTrolley) {
            els.invoiceTrolley.textContent = transaction.trolley_id ? transaction.trolley_id.replace('TROLLEY-00', 'Trolley #').replace('TROLLEY-', 'Trolley #') : 'Trolley #001';
        }
        if (els.paymentMode) {
            els.paymentMode.textContent = (transaction.paymentMethod || 'UPI').toUpperCase();
        }
        
        // Calculate mathematics
        const total = transaction.total;
        const subAmount = total / 1.18; // 18% GST inclusive
        const cgstAmount = subAmount * 0.09;
        const sgstAmount = subAmount * 0.09;
        
        const itemsList = Object.values(transaction.items);
        const qtySum = itemsList.reduce((acc, curr) => acc + curr.quantity, 0);
        const points = Math.floor(total / 10);

        if (els.qtyTotal) els.qtyTotal.textContent = `${qtySum} units`;
        if (els.subtotal) els.subtotal.textContent = `Rs.${subAmount.toFixed(2)}`;
        if (els.cgst) els.cgst.textContent = `Rs.${cgstAmount.toFixed(2)}`;
        if (els.sgst) els.sgst.textContent = `Rs.${sgstAmount.toFixed(2)}`;
        if (els.grandTotal) els.grandTotal.textContent = `Rs.${total.toFixed(2)}`;
        if (els.pointsEarned) els.pointsEarned.textContent = `+${points} Points`;

        // Update QR server dynamic URL
        if (els.qrImage) {
            els.qrImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${txHash}`;
        }

        // Render rows
        if (els.itemsBody) {
            els.itemsBody.innerHTML = '';
            itemsList.forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${item.name}</td>
                    <td style="text-align: right;">Rs.${item.price.toFixed(2)}</td>
                    <td style="text-align: center;">${item.quantity}</td>
                    <td style="text-align: right; font-weight: bold;">Rs.${item.subtotal.toFixed(2)}</td>
                `;
                els.itemsBody.appendChild(tr);
            });
        }
    }

    // Print Receipt
    if (els.btnPrint) {
        els.btnPrint.addEventListener('click', () => {
            window.print();
        });
    }

    // PDF compilation
    if (els.btnPdf) {
        els.btnPdf.addEventListener('click', () => {
            if (!transaction) return;
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF({
                unit: 'mm',
                format: [80, 220] // thermal receipt paper aspect
            });

            const txHash = `TXN-${Math.floor(transaction.timestamp)}`;

            doc.setFont("courier", "bold");
            doc.setFontSize(13);
            doc.text(currentStoreName.toUpperCase(), 40, 14, { align: 'center' });
            
            doc.setFont("courier", "normal");
            doc.setFontSize(8);
            doc.text(currentStoreAddress, 40, 19, { align: 'center' });
            doc.text("SMART TROLLEY BILLING SYSTEM", 40, 23, { align: 'center' });
            
            doc.text("-------------------------------------", 40, 27, { align: 'center' });
            doc.text(`INVOICE: ${txHash}`, 10, 32);
            doc.text(`DATE   : ${new Date(transaction.timestamp * 1000).toLocaleString()}`, 10, 36);
            const custInfo = transaction.customerPhone ? `+91 ${transaction.customerPhone}` : "Walk-in Customer";
            doc.text(`CUSTOMER: ${custInfo}`, 10, 40);
            const trolleyInfo = transaction.trolley_id ? transaction.trolley_id.replace('TROLLEY-00', 'Trolley #').replace('TROLLEY-', 'Trolley #') : 'Trolley #001';
            doc.text(`TROLLEY : ${trolleyInfo}`, 10, 44);
            doc.text(`PAYMENT : ${(transaction.paymentMethod || 'UPI').toUpperCase()}`, 10, 48);
            doc.text("-------------------------------------", 40, 52, { align: 'center' });

            // Table headers
            doc.text("ITEM         PRICE   QTY   TOTAL", 10, 57);
            let y = 62;

            const itemsList = Object.values(transaction.items);
            itemsList.forEach(item => {
                const name = item.name.substring(0, 10).padEnd(12, ' ');
                const price = item.price.toFixed(0).padStart(5, ' ');
                const qty = item.quantity.toString().padStart(3, ' ');
                const sub = item.subtotal.toFixed(0).padStart(7, ' ');
                doc.text(`${name}${price}${qty}${sub}`, 10, y);
                y += 6;
            });

            doc.text("-------------------------------------", 40, y, { align: 'center' });
            y += 5;

            const total = transaction.total;
            doc.text(`Subtotal Amount: Rs. ${(total / 1.18).toFixed(2)}`, 10, y);
            y += 5;
            doc.text(`CGST (9.0%)    : Rs. ${(total / 1.18 * 0.09).toFixed(2)}`, 10, y);
            y += 5;
            doc.text(`SGST (9.0%)    : Rs. ${(total / 1.18 * 0.09).toFixed(2)}`, 10, y);
            y += 5;
            doc.text("-------------------------------------", 40, y, { align: 'center' });
            y += 6;

            doc.setFont("courier", "bold");
            doc.setFontSize(10);
            doc.text(`GRAND TOTAL    : Rs. ${total.toFixed(2)}`, 10, y);
            y += 8;

            doc.setFont("courier", "normal");
            doc.setFontSize(8);
            doc.text(`Points Earned  : +${Math.floor(total/10)} Points`, 10, y);
            y += 12;

            doc.text("* THANK YOU FOR SHOPPING *", 40, y, { align: 'center' });

            doc.save(`Invoice_${txHash}.pdf`);
        });
    }

    // ── Post-Checkout Feedback Interaction ───────────────────────────────────
    let currentRating = 5;
    const starEls = document.querySelectorAll('#receipt-stars i');
    const commentInput = document.getElementById('receipt-feedback-comment');
    const submitFeedbackBtn = document.getElementById('btn-submit-receipt-feedback');
    const formRow = document.getElementById('receipt-feedback-form-row');
    const thankYouMsg = document.getElementById('receipt-feedback-thankyou');

    starEls.forEach(star => {
        star.addEventListener('click', () => {
            currentRating = parseInt(star.getAttribute('data-rating'));
            starEls.forEach(s => {
                const r = parseInt(s.getAttribute('data-rating'));
                if (r <= currentRating) {
                    s.classList.remove('fa-regular');
                    s.classList.add('fa-solid');
                    s.style.color = '#f59e0b';
                } else {
                    s.classList.remove('fa-solid');
                    s.classList.add('fa-regular');
                    s.style.color = 'var(--text-secondary)';
                }
            });
        });
    });

    if (submitFeedbackBtn) {
        submitFeedbackBtn.addEventListener('click', async () => {
            const comment = commentInput ? commentInput.value.trim() : '';
            submitFeedbackBtn.disabled = true;
            submitFeedbackBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

            try {
                const res = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        rating: currentRating,
                        comments: comment || "Great smart checkout experience!"
                    })
                });

                if (res.ok) {
                    if (formRow) formRow.style.display = 'none';
                    if (thankYouMsg) thankYouMsg.style.display = 'block';
                } else {
                    alert("Could not submit feedback. Please try again.");
                    submitFeedbackBtn.disabled = false;
                    submitFeedbackBtn.textContent = 'Send Review';
                }
            } catch (err) {
                console.error("Feedback submit error:", err);
                submitFeedbackBtn.disabled = false;
                submitFeedbackBtn.textContent = 'Send Review';
            }
        });
    }

    loadInvoice();
});
