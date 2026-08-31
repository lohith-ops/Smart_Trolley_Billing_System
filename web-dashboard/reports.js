/**
 * Reports Generation & Export Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    let transactions = [];
    let reportData = []; // compiled list for table
    let reportSummary = { gross: 0, items: 0, gst: 0 };
    let selectedType = 'daily';

    const els = {
        typeSelect: document.getElementById('report-type'),
        generateBtn: document.getElementById('generate-report-btn'),
        exportPdfBtn: document.getElementById('export-pdf-btn'),
        exportCsvBtn: document.getElementById('export-csv-btn'),
        exportExcelBtn: document.getElementById('export-excel-btn'),
        metricsContainer: document.getElementById('report-metrics-container'),
        tableCard: document.getElementById('report-table-card'),
        emptyState: document.getElementById('report-empty-state'),
        metricGross: document.getElementById('report-metric-gross'),
        metricItems: document.getElementById('report-metric-items'),
        metricGst: document.getElementById('report-metric-gst'),
        tableHeaders: document.getElementById('report-table-headers'),
        tableBody: document.getElementById('report-table-body'),
        tableTitle: document.getElementById('report-table-title')
    };

    // Compile reports
    async function compileReport() {
        try {
            const res = await fetch('/api/transactions');
            if (res.ok) {
                transactions = await res.json();
            }
        } catch (e) {
            console.error("Failed to load transactions for report:", e);
        }

        selectedType = els.typeSelect.value;
        aggregateData();
        renderReport();
        
        if (window.showToast) {
            window.showToast("Report Compiled", `Successfully generated ${selectedType} sales report summary.`, "success");
        }
    }

    // Aggregation logic
    function aggregateData() {
        reportSummary = { gross: 0, items: 0, gst: 0 };
        const groups = {};

        transactions.forEach(tx => {
            const date = new Date(tx.timestamp * 1000);
            let key = '';

            if (selectedType === 'daily') {
                key = date.toLocaleDateString();
            } else if (selectedType === 'weekly') {
                // Get week number
                const firstDayOfYear = new Date(date.getFullYear(), 0, 1);
                const pastDaysOfYear = (date - firstDayOfYear) / 86400000;
                const weekNum = Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
                key = `Week ${weekNum}, ${date.getFullYear()}`;
            } else if (selectedType === 'monthly') {
                key = date.toLocaleString('default', { month: 'long', year: 'numeric' });
            } else if (selectedType === 'yearly') {
                key = date.getFullYear().toString();
            }

            // Sum items in transaction
            let itemsCount = 0;
            if (tx.items) {
                itemsCount = Object.values(tx.items).reduce((acc, curr) => acc + curr.quantity, 0);
            }

            if (!groups[key]) {
                groups[key] = {
                    period: key,
                    transactionsCount: 0,
                    itemsCount: 0,
                    revenue: 0.0
                };
            }

            groups[key].transactionsCount += 1;
            groups[key].itemsCount += itemsCount;
            groups[key].revenue += tx.total;

            // Global stats
            reportSummary.gross += tx.total;
            reportSummary.items += itemsCount;
        });

        // 18% GST calculation
        reportSummary.gst = reportSummary.gross * 0.18;
        reportData = Object.values(groups).sort((a, b) => b.period.localeCompare(a.period));
    }

    // Render elements
    function renderReport() {
        if (transactions.length === 0) {
            alert("No transaction logs available. Check out carts first.");
            return;
        }

        els.emptyState.style.display = 'none';
        els.metricsContainer.style.display = 'grid';
        els.tableCard.style.display = 'block';

        // Render metrics cards
        els.metricGross.textContent = `Rs.${reportSummary.gross.toFixed(2)}`;
        els.metricItems.textContent = reportSummary.items;
        els.metricGst.textContent = `Rs.${reportSummary.gst.toFixed(2)}`;

        // Render headers
        let timeLabel = "Billing Period";
        if (selectedType === 'daily') timeLabel = "Date";
        else if (selectedType === 'weekly') timeLabel = "Week Number";
        else if (selectedType === 'monthly') timeLabel = "Month";
        else if (selectedType === 'yearly') timeLabel = "Year";

        els.tableTitle.textContent = `${selectedType.toUpperCase()} Financial Statement Summary`;
        els.tableHeaders.innerHTML = `
            <th>${timeLabel}</th>
            <th>Checkout Frequency</th>
            <th>Units Sold</th>
            <th>Gross Billings</th>
            <th>GST Collected (18%)</th>
            <th>Net Sales Revenue</th>
        `;

        els.tableBody.innerHTML = '';
        reportData.forEach(row => {
            const tax = row.revenue * 0.18;
            const net = row.revenue - tax;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight: 600;">${row.period}</td>
                <td>${row.transactionsCount} bills</td>
                <td>${row.itemsCount} units</td>
                <td style="color: var(--accent-green); font-weight:600;">Rs.${row.revenue.toFixed(2)}</td>
                <td>Rs.${tax.toFixed(2)}</td>
                <td style="color: var(--accent-cyan); font-weight:600;">Rs.${net.toFixed(2)}</td>
            `;
            els.tableBody.appendChild(tr);
        });
    }

    // EXPORT PDF
    function exportPDF() {
        if (reportData.length === 0) return;
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        doc.setFillColor(15, 17, 21);
        doc.rect(0, 0, 220, 297, "F");

        doc.setTextColor(6, 182, 212);
        doc.setFontSize(22);
        doc.text("SMART TROLLEY BILLING SYSTEM", 20, 24);
        
        doc.setTextColor(248, 250, 252);
        doc.setFontSize(14);
        doc.text(`${selectedType.toUpperCase()} SALES AUDIT REPORT`, 20, 36);
        
        doc.setFontSize(10);
        doc.setTextColor(148, 163, 184);
        doc.text(`Generated on: ${new Date().toLocaleString()}`, 20, 44);
        doc.line(20, 48, 190, 48);

        // Print summaries
        doc.setTextColor(248, 250, 252);
        doc.setFontSize(12);
        doc.text(`Total Gross Billing: Rs. ${reportSummary.gross.toFixed(2)}`, 20, 60);
        doc.text(`Total Units Transacted: ${reportSummary.items} units`, 20, 68);
        doc.text(`GST Accumulated (18%): Rs. ${reportSummary.gst.toFixed(2)}`, 20, 76);
        doc.text(`Total Net Store Income: Rs. ${(reportSummary.gross - reportSummary.gst).toFixed(2)}`, 20, 84);

        doc.line(20, 92, 190, 92);

        // Draw Table
        doc.text("PER-PERIOD DETAIL STATEMENT:", 20, 104);
        let y = 114;
        
        doc.setFontSize(10);
        doc.setTextColor(6, 182, 212);
        doc.text("Period", 20, y);
        doc.text("Bills", 65, y);
        doc.text("Units", 90, y);
        doc.text("Gross Revenue", 120, y);
        doc.text("Net Sales", 160, y);
        
        doc.setTextColor(248, 250, 252);
        reportData.forEach(row => {
            y += 10;
            if (y > 270) {
                doc.addPage();
                doc.setFillColor(15, 17, 21);
                doc.rect(0, 0, 220, 297, "F");
                y = 30;
            }
            doc.text(row.period, 20, y);
            doc.text(row.transactionsCount.toString(), 65, y);
            doc.text(row.itemsCount.toString(), 90, y);
            doc.text(`Rs. ${row.revenue.toFixed(2)}`, 120, y);
            doc.text(`Rs. ${(row.revenue * 0.82).toFixed(2)}`, 160, y);
        });

        doc.save(`SmartTrolley_Report_${selectedType}_${new Date().toISOString().split('T')[0]}.pdf`);
    }

    // EXPORT CSV
    function exportCSV() {
        if (reportData.length === 0) return;
        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Period,Billing Count,Units Sold,Gross Billings,GST (18%),Net Revenue\n";

        reportData.forEach(row => {
            const gst = row.revenue * 0.18;
            const net = row.revenue - gst;
            csvContent += `"${row.period}",${row.transactionsCount},${row.itemsCount},${row.revenue.toFixed(2)},${gst.toFixed(2)},${net.toFixed(2)}\n`;
        });

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `SmartTrolley_Report_${selectedType}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // EXPORT EXCEL
    function exportExcel() {
        // Excel readable format is CSV as well, we just trigger xls file format naming
        if (reportData.length === 0) return;
        let csvContent = "Period\tCheckout Frequency\tUnits Sold\tGross Revenue\tGST Accumulated\tNet Income\n";

        reportData.forEach(row => {
            const gst = row.revenue * 0.18;
            const net = row.revenue - gst;
            csvContent += `${row.period}\t${row.transactionsCount}\t${row.itemsCount}\t${row.revenue.toFixed(2)}\t${gst.toFixed(2)}\t${net.toFixed(2)}\n`;
        });

        const blob = new Blob([csvContent], { type: "application/vnd.ms-excel;charset=utf-8" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", `SmartTrolley_Report_${selectedType}.xls`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Listeners
    if (els.generateBtn) els.generateBtn.addEventListener('click', compileReport);
    if (els.exportPdfBtn) els.exportPdfBtn.addEventListener('click', exportPDF);
    if (els.exportCsvBtn) els.exportCsvBtn.addEventListener('click', exportCSV);
    if (els.exportExcelBtn) els.exportExcelBtn.addEventListener('click', exportExcel);
});
