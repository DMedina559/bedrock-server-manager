// bedrock_server_manager/web/static/js/monitor_usage.js
/**
 * @fileoverview Frontend JavaScript for the server resource usage monitor page.
 * Periodically fetches status (CPU, Memory, Uptime, PID) for a specific server
 * from the backend API and updates the designated display area on the page.
 *
 * @requires serverName - A global JavaScript variable (typically set via Jinja2 template)
 *                         containing the name of the server to monitor.
 * @requires utils.js - For showStatusMessage and sendServerActionRequest.
 */

// Ensure utils.js is loaded
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    const statusElementFallback = document.getElementById('status-info');
    if (statusElementFallback) statusElementFallback.textContent = "CRITICAL PAGE ERROR: Utilities not loaded.";
}

async function updateStatus() {
    const timestamp = new Date().toISOString();
    const functionName = 'updateStatus';
    const statusElement = document.getElementById('status-info'); // Get element once

    if (typeof serverName === 'undefined' || !serverName) {
        console.error(`[${timestamp}] ${functionName}: CRITICAL - 'serverName' variable is not defined or empty. Cannot fetch status.`);
        if (typeof showStatusMessage === 'function') {
            // Show persistent error on the page if serverName is missing, and stop polling.
            showStatusMessage("Configuration Error: Server name missing for monitoring. Status updates stopped.", "error");
            if (statusElement) statusElement.textContent = "Configuration Error: Server name missing.";
            if (statusIntervalId) clearInterval(statusIntervalId); // Stop further polling
        } else {
            if (statusElement) statusElement.textContent = "Configuration Error: Server name missing.";
        }
        return;
    }

    if (!statusElement) {
        console.error(`[${timestamp}] ${functionName}: Error - Target display element '#status-info' not found. Cannot update status. Polling stopped.`);
        if (statusIntervalId) clearInterval(statusIntervalId); // Stop further polling
        return;
    }

    console.debug(`[${timestamp}] ${functionName}: Initiating status fetch for server: '${serverName}'`);
    const actionPath = 'process_info';

    try {
        // Pass `true` for suppressSuccessPopup for silent polling
        const data = await sendServerActionRequest(serverName, actionPath, 'GET', null, null, true);

        if (data && data.status === 'success' && data.data) { // Check data.data
            const info = data.data.process_info; // Access process_info from data.data
            if (info) {
                const statusText = `
PID          : ${info.pid ?? 'N/A'}
CPU Usage    : ${info.cpu_percent != null ? info.cpu_percent.toFixed(1) + '%' : 'N/A'}
Memory Usage : ${info.memory_mb != null ? info.memory_mb.toFixed(1) + ' MB' : 'N/A'}
Uptime       : ${info.uptime ?? 'N/A'}
                `.trim();
                statusElement.textContent = statusText;
            } else {
                statusElement.textContent = "Server Status: STOPPED (Process info not found)";
            }
        } else if (data && data.status === 'error') {
            // Error pop-up already shown by sendServerActionRequest.
            // Update the on-page display to a persistent error state.
            statusElement.textContent = `Error fetching status: ${data.message || 'API error occurred.'}`;
            console.warn(`[${timestamp}] ${functionName}: API reported error for server '${serverName}': ${data.message || '(No message provided)'}`);
        } else if (data === false) {
            // Network/fetch error. Pop-up already shown by sendServerActionRequest.
            // Update the on-page display to a persistent error state.
            statusElement.textContent = "Error fetching status: Network or server connection issue.";
            console.error(`[${timestamp}] ${functionName}: Failed to fetch server status for '${serverName}' due to network/server issue.`);
        } else {
            // Unexpected response structure from sendServerActionRequest (should not happen)
            statusElement.textContent = "Error fetching status: Unexpected response.";
            console.error(`[${timestamp}] ${functionName}: Unexpected response from sendServerActionRequest for '${serverName}'.`);
        }
    } catch (error) {
        // This catch is for unexpected errors in this function's logic (e.g. if sendServerActionRequest itself throws)
        console.error(`[${timestamp}] ${functionName}: Unexpected client-side error in updateStatus for '${serverName}':`, error);
        if (typeof showStatusMessage === 'function') {
            showStatusMessage(`Client-side error fetching status: ${error.message}`, "error");
        }
        statusElement.textContent = `Client-side error: ${error.message}`;
    }
}

let statusIntervalId = null;

document.addEventListener('DOMContentLoaded', () => {
    const timestamp = new Date().toISOString();
    const functionName = 'DOMContentLoaded (Monitor)';
    console.log(`[${timestamp}] ${functionName}: Page loaded. Initializing server status monitoring.`);
    const statusElement = document.getElementById('status-info'); // Defined here for initial check

    if (typeof serverName === 'undefined' || !serverName) {
        console.error(`[${timestamp}] ${functionName}: CRITICAL - Global 'serverName' is not defined. Monitoring will not start.`);
        const errorMessage = "Error: Server name not specified for monitoring. Status updates cannot start.";
        if (typeof showStatusMessage === 'function') {
            showStatusMessage(errorMessage, "error");
        }
        if (statusElement) { // Check if statusElement itself exists
            statusElement.textContent = errorMessage;
        }
        return;
    }

    console.log(`[${timestamp}] ${functionName}: Performing initial status update for server '${serverName}'.`);
    updateStatus();

    const updateIntervalMilliseconds = 2000;
    console.log(`[${timestamp}] ${functionName}: Setting status update interval to ${updateIntervalMilliseconds}ms.`);
    statusIntervalId = setInterval(updateStatus, updateIntervalMilliseconds);
});

// window.addEventListener('beforeunload', () => {
//     if (statusIntervalId) {
//         console.log(`[${new Date().toISOString()}] Clearing status update interval (ID: ${statusIntervalId}) on page unload.`);
//         clearInterval(statusIntervalId);
//     }
// });