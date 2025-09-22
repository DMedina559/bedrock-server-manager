/**
 * @fileoverview Frontend JavaScript for the server resource usage monitor page.
 */

import { showStatusMessage } from './utils.js';
import webSocketClient from './websocket_client.js';

export function initializeMonitorUsagePage() {
  const statusElement = document.getElementById('status-info');
  if (!statusElement) {
    console.error('Monitor page error: #status-info element not found.');
    return;
  }

  const serverName = statusElement.dataset.serverName;
  if (!serverName) {
    statusElement.textContent = 'Configuration Error: Server name missing.';
    showStatusMessage('Could not initialize monitoring: server name not found on page.', 'error');
    return;
  }

  let pollingIntervalId = null;

  function updateStatusDisplay(processInfo) {
    if (processInfo) {
      statusElement.textContent = `
PID          : ${processInfo.pid ?? 'N/A'}
CPU Usage    : ${processInfo.cpu_percent != null ? processInfo.cpu_percent.toFixed(1) + '%' : 'N/A'}
Memory Usage : ${processInfo.memory_mb != null ? processInfo.memory_mb.toFixed(1) + ' MB' : 'N/A'}
Uptime       : ${processInfo.uptime ?? 'N/A'}
            `.trim();
    } else {
      statusElement.textContent = 'Server Status: STOPPED or process info not found.';
    }
  }

  async function pollStatus() {
    try {
      // Use fetch directly as sendServerActionRequest is for actions, not silent polling
      const response = await fetch(`/api/server/${encodeURIComponent(serverName)}/process_info`);
      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }
      const data = await response.json();

      if (data && data.status === 'success') {
        updateStatusDisplay(data.data?.process_info);
      } else if (data && data.status === 'error') {
        statusElement.textContent = `Error: ${data.message || 'API error.'}`;
      } else {
        updateStatusDisplay(null);
      }
    } catch (error) {
      statusElement.textContent = `Client-side error: ${error.message}`;
      if (pollingIntervalId) clearInterval(pollingIntervalId);
    }
  }

  function setupWebSocket() {
    const topic = `resource-monitor:${serverName}`;

    document.addEventListener('websocket-message', (event) => {
      const message = event.detail;
      if (message && message.topic === topic && message.type === 'resource_update') {
        const processInfo = message.data?.process_info;
        updateStatusDisplay(processInfo);
      }
    });

    document.addEventListener('websocket-fallback', () => {
      console.warn('Monitor Page: WebSocket connection failed. Falling back to polling.');
      if (!pollingIntervalId) {
        pollStatus(); // Initial poll
        pollingIntervalId = setInterval(pollStatus, 2000);
      }
    });

    webSocketClient.subscribe(topic);
  }

  // Initial load and setup
  setupWebSocket();

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
    }
    // The websocket client handles its own connection state, but we can unsubscribe
    const topic = `resource-monitor:${serverName}`;
    webSocketClient.unsubscribe(topic);
  });

  console.log(`Monitoring started for server: ${serverName}`);
}
