/**
 * Digital Receipt Page Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let transaction = null;

    const els = {
        invoiceNo: document.getElementById('invoice-no'),
        invoiceDate: document.getElementById('invoice-date'),
        invoiceCustomer: document.getElementById('invoice-customer'),
        invoiceTrolley: document.getElementById('invoice-trolley'),
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

    // Load invoice
    async function loadInvoice() {
        const urlParams = new URLSearchParams(window.location.search);
        const timestamp = parseFloat(urlParams.get('timestamp'));

        if (!isNaN(timestamp)) {
            try {
                const res = await fetch('/api/transactions');
                if (res.ok) {
                    const txs = await res.json();
                    transaction = txs.find(t => Math.abs(t.timestamp - timestamp) < 1.0);
                }
            } catch (e) {
                console.error("Failed to load matching transaction for receipt:", e);
            }
        }

        // Fallback to mock invoice if not found
        if (!transaction) {
            transaction = {
                timestamp: Date.now() / 1000,
                total: 170.00,
                items: {
                    "5C1E7E05": { name: "Rice 1kg", price: 60.00, quantity: 2, subtotal: 120.00 },
                    "11223344": { name: "Milk (1 Gallon)", price: 50.00, quantity: 1, subtotal: 50.00 }
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
        
        els.invoiceNo.textContent = txHash;
        els.invoiceDate.textContent = dateString;
        
        // Calculate mathematics
        const total = transaction.total;
        const subAmount = total / 1.18; // 18% GST inclusive
        const cgstAmount = subAmount * 0.09;
        const sgstAmount = subAmount * 0.09;
        
        const itemsList = Object.values(transaction.items);
        const qtySum = itemsList.reduce((acc, curr) => acc + curr.quantity, 0);
        const points = Math.floor(total / 10);

        els.qtyTotal.textContent = `${qtySum} units`;
        els.subtotal.textContent = `Rs.${subAmount.toFixed(2)}`;
        els.cgst.textContent = `Rs.${cgstAmount.toFixed(2)}`;
        els.sgst.textContent = `Rs.${sgstAmount.toFixed(2)}`;
        els.grandTotal.textContent = `Rs.${total.toFixed(2)}`;
        els.pointsEarned.textContent = `+${points} Points`;

        // Update QR server dynamic URL
        els.qrImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${txHash}`;

        // Render rows
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
            doc.setFontSize(14);
            doc.text("SUPERMARKET POS", 40, 15, { align: 'center' });
            
            doc.setFont("courier", "normal");
            doc.setFontSize(8);
            doc.text("OUTER RING ROAD, BANGALORE", 40, 20, { align: 'center' });
            
            doc.text("-------------------------------------", 40, 25, { align: 'center' });
            doc.text(`INVOICE: ${txHash}`, 10, 30);
            doc.text(`DATE   : ${new Date(transaction.timestamp * 1000).toLocaleString()}`, 10, 35);
            doc.text("MEMBER : MEM-872910 (Gold)", 10, 40);
            doc.text("-------------------------------------", 40, 45, { align: 'center' });

            // Table headers
            doc.text("ITEM         PRICE   QTY   TOTAL", 10, 50);
            let y = 55;

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

    loadInvoice();
});
