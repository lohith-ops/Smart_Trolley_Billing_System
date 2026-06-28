/**
 * Sales Analytics Logic
 */

const els = {
    metricRevenue: document.getElementById('metric-revenue'),
    metricCheckouts: document.getElementById('metric-checkouts'),
    metricAvgBasket: document.getElementById('metric-avg-basket'),
    topProductsBody: document.getElementById('top-products-body'),
    revenueChartCanvas: document.getElementById('revenue-chart'),
    productChartCanvas: document.getElementById('product-chart')
};

let revenueChart = null;
let productChart = null;

// Initialize Page
async function initAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();
        
        renderMetrics(data);
        renderTopProductsTable(data.topProducts);
        renderCharts(data);
    } catch (e) {
        console.error("Failed to render analytics:", e);
    }
}

// Render metric panels
function renderMetrics(data) {
    if (els.metricRevenue) els.metricRevenue.textContent = `Rs.${data.totalRevenue.toFixed(2)}`;
    if (els.metricCheckouts) els.metricCheckouts.textContent = data.totalCheckouts;
    if (els.metricAvgBasket) els.metricAvgBasket.textContent = `Rs.${data.avgOrderValue.toFixed(2)}`;
}

// Render Top performing product catalog rows
function renderTopProductsTable(products) {
    if (!els.topProductsBody) return;
    
    els.topProductsBody.innerHTML = '';
    
    if (!products || products.length === 0) {
        els.topProductsBody.innerHTML = `
            <tr>
                <td colspan="3" style="text-align: center; color: var(--text-secondary); padding: 24px;">
                    No product metrics available. Check out orders first.
                </td>
            </tr>
        `;
        return;
    }

    products.forEach(p => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td style="font-weight: 500;">${p.name}</td>
            <td>${p.quantity} units</td>
            <td style="color: var(--accent-green); font-weight: 600;">Rs.${p.revenue.toFixed(2)}</td>
        `;
        els.topProductsBody.appendChild(row);
    });
}

// Render Charts.js graphs
function renderCharts(data) {
    // 1. Revenue Over Time Chart (Line Chart)
    const timeLabels = data.timeseries.map((tx, idx) => {
        const d = new Date(tx.timestamp * 1000);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    const timeData = data.timeseries.map(tx => tx.total);
    
    if (revenueChart) revenueChart.destroy();
    
    if (els.revenueChartCanvas) {
        const ctx = els.revenueChartCanvas.getContext('2d');
        revenueChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timeLabels.length > 0 ? timeLabels : ['No Data'],
                datasets: [{
                    label: 'Transaction Total (Rs.)',
                    data: timeData.length > 0 ? timeData : [0],
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#06b6d4',
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                    }
                }
            }
        });
    }

    // 2. Popular Products Chart (Bar Chart)
    const productLabels = data.topProducts.map(p => p.name);
    const productData = data.topProducts.map(p => p.quantity);

    if (productChart) productChart.destroy();

    if (els.productChartCanvas) {
        const ctx = els.productChartCanvas.getContext('2d');
        productChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: productLabels.length > 0 ? productLabels : ['No Data'],
                datasets: [{
                    label: 'Units Sold',
                    data: productData.length > 0 ? productData : [0],
                    backgroundColor: 'rgba(192, 132, 252, 0.7)',
                    borderColor: '#c084fc',
                    borderWidth: 2,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                    }
                }
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', initAnalytics);
