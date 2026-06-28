/**
 * Shared Utilities for Smart Trolley Web Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Highlight Active Sidebar Nav Link
    const currentPath = window.location.pathname.split('/').pop() || 'index.html';
    const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
    
    navItems.forEach(item => {
        const itemHref = item.getAttribute('href');
        if (itemHref === currentPath || (currentPath === '' && itemHref === 'index.html')) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // 2. Arduino Connection Status Polling
    const statusText = document.querySelector('.status-indicator span:last-child');
    const pulseDot = document.querySelector('.pulse-dot');

    async function checkStatus() {
        try {
            const res = await fetch('/api/dashboard');
            if (res.ok) {
                const data = await res.json();
                if (pulseDot && statusText) {
                    if (data.arduinoConnected) {
                        pulseDot.style.backgroundColor = 'var(--accent-green)';
                        pulseDot.style.boxShadow = '0 0 8px var(--accent-green)';
                        statusText.textContent = `Arduino Online (${data.serialPort})`;
                    } else {
                        pulseDot.style.backgroundColor = 'var(--accent-red)';
                        pulseDot.style.boxShadow = '0 0 8px var(--accent-red)';
                        statusText.textContent = 'Arduino Offline';
                    }
                }
            }
        } catch (e) {
            if (pulseDot && statusText) {
                pulseDot.style.backgroundColor = 'var(--accent-red)';
                statusText.textContent = 'Server Offline';
            }
        }
    }

    checkStatus();
    setInterval(checkStatus, 3000);
});
