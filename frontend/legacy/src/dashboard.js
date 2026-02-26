/**
 * @fileoverview Main dashboard logic.
 * Handles UI updates, user interactions, and orchestrates API calls via pure logic modules.
 */

import { showStatusMessage, handleApiAction } from "./ui_utils.js";
import {
  startServer,
  stopServer,
  restartServer,
  sendCommand,
  deleteServer,
  updateServer,
  fetchServers,
} from "./server_actions.js";
import webSocketClient from "./websocket_client.js";

// --- Helper: Get Selected Server ---
function getSelectedServer() {
  const serverSelect = document.getElementById("server-select");
  if (!serverSelect) {
    console.error(
      "Server selection dropdown element ('#server-select') not found.",
    );
    return null;
  }
  const selectedServer = serverSelect.value;
  if (!selectedServer || selectedServer === "") {
    showStatusMessage(
      "Please select a server from the dropdown list first.",
      "warning",
    );
    return null;
  }
  return selectedServer;
}

export function initializeDashboard() {
  const functionName = "DashboardManager";
  console.log(`${functionName}: Initializing all dashboard interactivity.`);

  // --- Constants and Elements ---
  const POLLING_INTERVAL_MS = 60000;
  const serverSelect = document.getElementById("server-select");
  const globalActionButtons = document.querySelectorAll(
    ".server-selection-section .action-buttons-group button",
  );
  const serverDependentSections = document.querySelectorAll(
    ".server-dependent-actions",
  );
  const serverCardList = document.getElementById("server-card-list");
  const noServersMessage = document.getElementById("no-servers-message");

  let pollingIntervalId = null;

  if (!serverSelect || !serverCardList || !noServersMessage) {
    console.error(
      `${functionName}: A critical element for the dashboard is missing. Functionality may be impaired.`,
    );
    showStatusMessage(
      "Dashboard Error: Critical page elements missing.",
      "error",
    );
    return;
  }

  // --- State Management and UI Updates ---

  function updateActionStates(selectedServerName) {
    const hasSelection = selectedServerName && selectedServerName !== "";
    const serverNameEncoded = hasSelection
      ? encodeURIComponent(selectedServerName)
      : "";
    globalActionButtons.forEach((button) => (button.disabled = !hasSelection));
    serverDependentSections.forEach((section) => {
      const span = section.querySelector('span[id^="selected-server-"]');
      if (span) {
        span.textContent = hasSelection
          ? selectedServerName
          : "(No server selected)";
        span.style.fontStyle = hasSelection ? "normal" : "italic";
      }
      section
        .querySelectorAll(".action-button, .action-link")
        .forEach((action) => {
          action.disabled = !hasSelection;
          if (action.tagName === "A" && action.id && hasSelection) {
            let targetUrl = "#";
            switch (action.id) {
              case "config-link-properties":
                targetUrl = `/legacy/server/${serverNameEncoded}/configure_properties`;
                break;
              case "config-link-allowlist":
                targetUrl = `/legacy/server/${serverNameEncoded}/configure_allowlist`;
                break;
              case "config-link-permissions":
                targetUrl = `/legacy/server/${serverNameEncoded}/configure_permissions`;
                break;
              case "config-link-monitor":
                targetUrl = `/legacy/server/${serverNameEncoded}/monitor`;
                break;
              case "config-link-service":
                targetUrl = `/legacy/server/${serverNameEncoded}/configure_service`;
                break;
              case "task-scheduler-menu":
                targetUrl = `/legacy/server/${serverNameEncoded}/scheduler`;
                break;
              case "content-link-world":
                targetUrl = `/legacy/server/${serverNameEncoded}/install_world`;
                break;
              case "content-link-addon":
                targetUrl = `/legacy/server/${serverNameEncoded}/install_addon`;
                break;
              case "backup-link-menu":
                targetUrl = `/legacy/server/${serverNameEncoded}/backup`;
                break;
              case "restore-link-menu":
                targetUrl = `/legacy/server/${serverNameEncoded}/restore`;
                break;
              default:
                targetUrl = "#";
                break;
            }
            action.href = targetUrl;
          } else if (action.tagName === "A" && !hasSelection) {
            action.href = "#";
          }
        });
    });
  }

  function createServerCardElement(server) {
    const card = document.createElement("div");
    card.className = "server-card";
    card.dataset.serverName = server.name;
    const safeServerName = encodeURIComponent(server.name);
    const status = server.status || "UNKNOWN";
    const version = server.version || "N/A";
    card.innerHTML = `
        <div class="server-card-thumbnail">
            <img src="/api/server/${safeServerName}/world/icon" alt="${server.name} World Icon" class="world-icon-img">
        </div>
        <div class="server-card-info">
            <h3>${server.name}</h3>
            <p><span class="info-label">Status:</span> <span class="status-text status-${status.toLowerCase()}">${status.toUpperCase()}</span></p>
            <p><span class="info-label">Version:</span> <span class="version-text">${version}</span></p>
            <p><span class="info-label">Players:</span> <span class="player-count-text">${server.player_count}</span></p>
        </div>
        <div class="server-card-actions">
            <a href="/legacy/servers/${safeServerName}/settings" class="action-link" title="Server Settings">Settings</a>
        </div>`;
    return card;
  }

  function updateServerDropdown(servers) {
    const previouslySelected = serverSelect.value;
    serverSelect.innerHTML = "";
    if (servers.length === 0) {
      const noServerOption = new Option("-- No Servers Installed --", "");
      noServerOption.disabled = true;
      serverSelect.add(noServerOption);
      serverSelect.disabled = true;
      serverSelect.title = "No servers available";
    } else {
      serverSelect.add(new Option("-- Select a Server --", ""));
      servers.forEach((server) =>
        serverSelect.add(new Option(server.name, server.name)),
      );
      serverSelect.disabled = false;
      serverSelect.title = "Select a server";
    }
    serverSelect.value = previouslySelected;
    if (serverSelect.value !== previouslySelected) {
      serverSelect.dispatchEvent(new Event("change"));
    }
  }

  async function updateDashboard() {
    try {
      const data = await fetchServers();
      if (!data || data.status !== "success" || !Array.isArray(data.servers)) {
        console.warn(`${functionName}: Invalid server data received.`);
        return;
      }

      const newServers = data.servers;
      const newServerMap = new Map(newServers.map((s) => [s.name, s]));
      const existingCardElements =
        serverCardList.querySelectorAll(".server-card");

      existingCardElements.forEach((card) => {
        const serverName = card.dataset.serverName;
        if (newServerMap.has(serverName)) {
          const serverData = newServerMap.get(serverName);
          const safeServerName = encodeURIComponent(serverData.name);
          const status = serverData.status || "UNKNOWN";
          const version = serverData.version || "N/A";
          card.innerHTML = `
                    <div class="server-card-thumbnail">
                        <img src="/api/server/${safeServerName}/world/icon" alt="${serverData.name} World Icon" class="world-icon-img">
                    </div>
                    <div class="server-card-info">
                        <h3>${serverData.name}</h3>
                        <p><span class="info-label">Status:</span> <span class="status-text status-${status.toLowerCase()}">${status.toUpperCase()}</span></p>
                        <p><span class="info-label">Version:</span> <span class="version-text">${version}</span></p>
                        <p><span class="info-label">Players:</span> <span class="player-count-text">${serverData.player_count}</span></p>
                    </div>
                    <div class="server-card-actions">
                        <a href="/legacy/servers/${safeServerName}/settings" class="action-link" title="Server Settings">Settings</a>
                    </div>`;
        } else {
          card.remove();
        }
      });

      const existingServerNames = new Set(
        Array.from(existingCardElements).map((card) => card.dataset.serverName),
      );

      newServers.forEach((server) => {
        if (!existingServerNames.has(server.name)) {
          serverCardList.appendChild(createServerCardElement(server));
        }
      });

      updateServerDropdown(newServers);
      noServersMessage.style.display =
        newServers.length === 0 ? "block" : "none";
    } catch (error) {
      console.error(`${functionName}: Error updating dashboard:`, error);
      // Suppress UI error for polling/background updates unless critical
    }
  }

  function setupWebSocket() {
    const refreshTopics = [
      "event:after_server_statuses_updated",
      "event:after_server_start",
      "event:after_server_stop",
      "event:after_delete_server_data",
      "event:after_server_updated",
    ];

    document.addEventListener("websocket-message", (event) => {
      const message = event.detail;
      if (message && message.topic && refreshTopics.includes(message.topic)) {
        updateDashboard();
      }
    });

    const startPolling = () => {
      if (!pollingIntervalId) {
        pollingIntervalId = setInterval(updateDashboard, POLLING_INTERVAL_MS);
      }
    };

    if (webSocketClient.shouldUseFallback()) {
      startPolling();
    } else {
      document.addEventListener("websocket-fallback", () => startPolling());
      refreshTopics.forEach((topic) => webSocketClient.subscribe(topic));
    }
  }

  // --- Event Handlers for Action Buttons ---

  // Start
  document
    .getElementById("start-server-btn")
    ?.addEventListener("click", (e) => {
      const serverName = getSelectedServer();
      if (serverName) {
        handleApiAction(e.currentTarget, () => startServer(serverName));
      }
    });

  // Stop
  document.getElementById("stop-server-btn")?.addEventListener("click", (e) => {
    const serverName = getSelectedServer();
    if (serverName) {
      handleApiAction(e.currentTarget, () => stopServer(serverName));
    }
  });

  // Restart
  document
    .getElementById("restart-server-btn")
    ?.addEventListener("click", (e) => {
      const serverName = getSelectedServer();
      if (serverName) {
        handleApiAction(e.currentTarget, () => restartServer(serverName));
      }
    });

  // Command
  document
    .getElementById("prompt-command-btn")
    ?.addEventListener("click", (e) => {
      const serverName = getSelectedServer();
      if (!serverName) return;

      const command = prompt(
        `Enter command to send to server '${serverName}':`,
      );
      if (command === null) {
        showStatusMessage("Command input cancelled.", "info");
        return;
      }
      const trimmedCommand = command.trim();
      if (!trimmedCommand) {
        showStatusMessage("Command cannot be empty.", "warning");
        return;
      }

      handleApiAction(e.currentTarget, () =>
        sendCommand(serverName, trimmedCommand),
      );
    });

  // Update
  document
    .getElementById("update-server-btn")
    ?.addEventListener("click", (e) => {
      const serverName = getSelectedServer();
      if (serverName) {
        handleApiAction(e.currentTarget, () => updateServer(serverName));
      }
    });

  // Delete
  document
    .getElementById("delete-server-btn")
    ?.addEventListener("click", (e) => {
      const serverName = getSelectedServer(); // Or pass explicitly if needed, but here we use selected
      if (!serverName) return;

      const confirmationMessage = `Are you absolutely sure you want to delete ALL data for server '${serverName}'?\n\nThis includes installation, configuration, and backups and cannot be undone!`;
      if (confirm(confirmationMessage)) {
        handleApiAction(e.currentTarget, () => deleteServer(serverName));
      } else {
        showStatusMessage("Deletion cancelled.", "info");
      }
    });

  serverSelect.addEventListener("change", (event) => {
    updateActionStates(event.target.value);
  });

  // Initial load
  updateDashboard();
  setupWebSocket();
}
