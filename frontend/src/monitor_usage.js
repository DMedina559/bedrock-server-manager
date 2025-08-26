// frontend/src/monitor_usage.js
/**
 * @fileoverview Frontend JavaScript for the server resource usage monitor page.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

export function initializeMonitorUsagePage() {
    const statusElement = document.getElementById('status-info');
    if (!statusElement) {
        console.error("Monitor page error: #status-info element not found.");
        return;
    }

    const serverName = statusElement.dataset.serverName;
    if (!serverName) {
        statusElement.textContent = "Configuration Error: Server name missing.";
        showStatusMessage("Could not initialize monitoring: server name not found on page.", "error");
        return;
    }

    let statusIntervalId = null;

    async function updateStatus() {
        try {
            const data = await sendServerActionRequest(serverName, 'process_info', 'GET', null, null, true);
            if (data && data.status === 'success' && data.data?.process_info) {
                const info = data.data.process_info;
                statusElement.textContent = `
PID          : ${info.pid ?? 'N/A'}
CPU Usage    : ${info.cpu_percent != null ? info.cpu_percent.toFixed(1) + '%' : 'N/A'}
Memory Usage : ${info.memory_mb != null ? info.memory_mb.toFixed(1) + ' MB' : 'N/A'}
Uptime       : ${info.uptime ?? 'N/A'}
                `.trim();
            } else if (data && data.status === 'error') {
                statusElement.textContent = `Error: ${data.message || 'API error.'}`;
            } else {
                statusElement.textContent = "Server Status: STOPPED or process info not found.";
            }
        } catch (error) {
            statusElement.textContent = `Client-side error: ${error.message}`;
            showStatusMessage(`Client-side error fetching status: ${error.message}`, "error");
            if (statusIntervalId) clearInterval(statusIntervalId);
        }
    }

    updateStatus();
    statusIntervalId = setInterval(updateStatus, 2000);

    // Cleanup interval on page unload
    window.addEventListener('beforeunload', () => {
        if (statusIntervalId) {
            clearInterval(statusIntervalId);
        }
    });

    console.log(`Monitoring started for server: ${serverName}`);
}
