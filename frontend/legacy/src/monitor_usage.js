/**
 * @fileoverview Frontend JavaScript for the server resource usage monitor page.
 */

import { getServerUsage } from "./server_actions.js";
import { showStatusMessage } from "./ui_utils.js";
import webSocketClient from "./websocket_client.js";

export function initializeMonitorUsagePage() {
  const statusElement = document.getElementById("status-info");
  if (!statusElement) {
    console.error("Monitor page error: #status-info element not found.");
    return;
  }

  const serverName = statusElement.dataset.serverName;
  if (!serverName) {
    statusElement.textContent = "Configuration Error: Server name missing.";
    showStatusMessage(
      "Could not initialize monitoring: server name not found on page.",
      "error",
    );
    return;
  }

  let pollingIntervalId = null;

  function updateStatusDisplay(processInfo) {
    if (processInfo) {
      statusElement.textContent = `
PID          : ${processInfo.pid ?? "N/A"}
CPU Usage    : ${processInfo.cpu_percent != null ? processInfo.cpu_percent.toFixed(1) + "%" : "N/A"}
Memory Usage : ${processInfo.memory_mb != null ? processInfo.memory_mb.toFixed(1) + " MB" : "N/A"}
Uptime       : ${processInfo.uptime ?? "N/A"}
            `.trim();
    } else {
      statusElement.textContent =
        "Server Status: STOPPED or process info not found.";
    }
  }

  async function pollStatus() {
    try {
      const data = await getServerUsage(serverName);

      if (data && data.status === "success") {
        updateStatusDisplay(data.data?.process_info);
      } else {
        // Handle application error or stopped status if returned structurally
        updateStatusDisplay(null);
      }
    } catch (error) {
      // Handle ApiError or network error
      console.warn("Polling error:", error);
      statusElement.textContent = `Error polling status: ${error.message}`;
      if (error.status === 404) {
        clearInterval(pollingIntervalId);
        statusElement.textContent = "Server not found.";
      }
    }
  }

  function setupWebSocket() {
    const topic = `resource-monitor:${serverName}`;

    const handleMessage = (event) => {
      const message = event.detail;
      if (
        message &&
        message.topic === topic &&
        message.type === "resource_update"
      ) {
        updateStatusDisplay(message.data?.process_info);
      }
    };

    document.addEventListener("websocket-message", handleMessage);

    const startPolling = () => {
      if (!pollingIntervalId) {
        console.warn("Monitor Page: Starting polling (fallback).");
        pollStatus(); // Initial poll
        pollingIntervalId = setInterval(pollStatus, 2000);
      }
    };

    if (webSocketClient.shouldUseFallback()) {
      startPolling();
    } else {
      // Listen for fallback event
      document.addEventListener("websocket-fallback", () => {
        startPolling();
      });

      webSocketClient.subscribe(topic);
    }

    // Cleanup function
    return () => {
      if (pollingIntervalId) clearInterval(pollingIntervalId);
      webSocketClient.unsubscribe(topic);
      document.removeEventListener("websocket-message", handleMessage);
    };
  }

  // Initial load and setup
  const cleanup = setupWebSocket();

  // Cleanup on page unload
  window.addEventListener("beforeunload", cleanup);

  console.log(`Monitoring started for server: ${serverName}`);
}
