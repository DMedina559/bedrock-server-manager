import { sendServerActionRequest, showStatusMessage } from './utils.js';
import {
  startServer,
  stopServer,
  restartServer,
  promptCommand,
  triggerServerUpdate,
  deleteServer,
} from './server_actions.js';
import webSocketClient from './websocket_client.js';

export function initializeDashboard() {
  const functionName = 'DashboardManager';
  console.log(`${functionName}: Initializing all dashboard interactivity.`);

  // --- Constants and Elements ---
  const POLLING_INTERVAL_MS = 60000;
  const serverSelect = document.getElementById('server-select');
  const globalActionButtons = document.querySelectorAll('.server-selection-section .action-buttons-group button');
  const serverDependentSections = document.querySelectorAll('.server-dependent-actions');
  const serverCardList = document.getElementById('server-card-list');
  const noServersMessage = document.getElementById('no-servers-message');

  let pollingIntervalId = null;

  if (!serverSelect || !serverCardList || !noServersMessage) {
    console.error(`${functionName}: A critical element for the dashboard is missing. Functionality may be impaired.`);
    if (typeof showStatusMessage === 'function') {
      showStatusMessage('Dashboard Error: Critical page elements missing.', 'error');
    } else {
      const body = document.querySelector('body');
      if (body)
        body.insertAdjacentHTML(
          'afterbegin',
          '<p style="color:red; text-align:center; padding:10px; background:lightyellow; border:1px solid red;">Critical Dashboard Error: Page elements missing.</p>',
        );
    }
    return;
  }

  // --- State Management and UI Updates ---

  function updateActionStates(selectedServerName) {
    const hasSelection = selectedServerName && selectedServerName !== '';
    const serverNameEncoded = hasSelection ? encodeURIComponent(selectedServerName) : '';
    globalActionButtons.forEach((button) => (button.disabled = !hasSelection));
    serverDependentSections.forEach((section) => {
      const span = section.querySelector('span[id^="selected-server-"]');
      const actions = section.querySelectorAll('.action-button, .action-link');
      if (span) {
        span.textContent = hasSelection ? selectedServerName : '(No server selected)';
        span.style.fontStyle = hasSelection ? 'normal' : 'italic';
      }
      actions.forEach((action) => {
        action.disabled = !hasSelection;
        if (action.tagName === 'A' && action.id && hasSelection) {
          let targetUrl = '#';
          switch (action.id) {
            // Routes without router prefix (or handled by main_router)
            case 'config-link-properties':
              targetUrl = `/server/${serverNameEncoded}/configure_properties`;
              break;
            case 'config-link-allowlist':
              targetUrl = `/server/${serverNameEncoded}/configure_allowlist`;
              break;
            case 'config-link-permissions':
              targetUrl = `/server/${serverNameEncoded}/configure_permissions`;
              break;
            case 'config-link-monitor':
              targetUrl = `/server/${serverNameEncoded}/monitor`;
              break;
            case 'config-link-service':
              targetUrl = `/server/${serverNameEncoded}/configure_service`;
              break;
            case 'task-scheduler-menu':
              targetUrl = `/server/${serverNameEncoded}/scheduler`;
              break; // This redirects via main_router

            // Routes with /content prefix
            case 'content-link-world':
              targetUrl = `/server/${serverNameEncoded}/install_world`;
              break;
            case 'content-link-addon':
              targetUrl = `/server/${serverNameEncoded}/install_addon`;
              break;

            // Routes with /backup-restore prefix
            case 'backup-link-menu':
              targetUrl = `/server/${serverNameEncoded}/backup`;
              break;
            case 'restore-link-menu':
              targetUrl = `/server/${serverNameEncoded}/restore`;
              break;

            default:
              console.warn(`${functionName}: No URL map for link ID '${action.id}'.`);
              targetUrl = '#'; // Ensure it's a safe default
              break;
          }
          action.href = targetUrl;
        } else if (action.tagName === 'A' && !hasSelection) {
          action.href = '#';
        }
      });
    });
  }

  function createServerCardElement(server) {
    const card = document.createElement('div');
    card.className = 'server-card';
    card.dataset.serverName = server.name;
    const safeServerName = encodeURIComponent(server.name);
    const status = server.status || 'UNKNOWN';
    const version = server.version || 'N/A';
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
            <a href="/servers/${safeServerName}/settings" class="action-link" title="Server Settings">Settings</a>
        </div>`;
    return card;
  }

  function updateServerDropdown(servers) {
    const previouslySelected = serverSelect.value;
    serverSelect.innerHTML = '';
    if (servers.length === 0) {
      const noServerOption = new Option('-- No Servers Installed --', '');
      noServerOption.disabled = true;
      serverSelect.add(noServerOption);
      serverSelect.disabled = true;
      serverSelect.title = 'No servers available';
    } else {
      serverSelect.add(new Option('-- Select a Server --', ''));
      servers.forEach((server) => serverSelect.add(new Option(server.name, server.name)));
      serverSelect.disabled = false;
      serverSelect.title = 'Select a server';
    }
    serverSelect.value = previouslySelected;
    if (serverSelect.value !== previouslySelected) {
      serverSelect.dispatchEvent(new Event('change'));
    }
  }

  async function updateDashboard() {
    try {
      // Use sendServerActionRequest and suppress success pop-up for polling
      const data = await sendServerActionRequest(null, '/api/servers', 'GET', null, null, true);

      if (!data || data.status !== 'success' || !Array.isArray(data.servers)) {
        console.warn(
          `${functionName}: API call to /api/servers did not return success or valid server data. Message:`,
          data?.message,
        );
        if (typeof showStatusMessage === 'function' && !(data && data.message && data.status === 'error')) {
          showStatusMessage('Failed to update dashboard: Could not retrieve server list.', 'warning');
        }
        return;
      }

      const newServers = data.servers;
      const newServerMap = new Map(newServers.map((s) => [s.name, s]));
      const existingCardElements = serverCardList.querySelectorAll('.server-card');
      const existingServerNames = new Set(Array.from(existingCardElements).map((card) => card.dataset.serverName));

      existingCardElements.forEach((card) => {
        const serverName = card.dataset.serverName;
        if (newServerMap.has(serverName)) {
          const serverData = newServerMap.get(serverName);
          const safeServerName = encodeURIComponent(serverData.name);
          const status = serverData.status || 'UNKNOWN';
          const version = serverData.version || 'N/A';
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
                        <a href="/servers/${safeServerName}/settings" class="action-link" title="Server Settings">Settings</a>
                    </div>`;
        } else {
          card.remove();
        }
      });

      newServers.forEach((server) => {
        if (!existingServerNames.has(server.name)) {
          serverCardList.appendChild(createServerCardElement(server));
        }
      });

      updateServerDropdown(newServers);
      noServersMessage.style.display = newServers.length === 0 ? 'block' : 'none';
    } catch (error) {
      console.error(`${functionName}: Client-side error during dashboard update:`, error);
      if (typeof showStatusMessage === 'function') {
        showStatusMessage(`Dashboard update error: ${error.message}`, 'error');
      }
    }
  }

  function setupWebSocket() {
    // Topics that trigger a full dashboard refresh
    const refreshTopics = [
      'event:after_server_statuses_updated',
      'event:after_server_start',
      'event:after_server_stop',
      'event:after_delete_server_data',
      'event:after_server_updated',
      // Any other events that should trigger a refresh
    ];

    document.addEventListener('websocket-message', (event) => {
      const message = event.detail;
      if (message && message.topic && refreshTopics.includes(message.topic)) {
        console.log(`${functionName}: Received relevant WebSocket event on topic '${message.topic}'. Refreshing dashboard.`);
        updateDashboard();
      }
    });

    // Handle fallback to polling if WebSocket connection fails
    document.addEventListener('websocket-fallback', () => {
      console.warn(`${functionName}: WebSocket connection failed. Falling back to polling.`);
      if (!pollingIntervalId) {
        pollingIntervalId = setInterval(updateDashboard, POLLING_INTERVAL_MS);
        console.log(`${functionName}: Polling started as a fallback.`);
      }
    });

    refreshTopics.forEach(topic => webSocketClient.subscribe(topic));
  }


  serverSelect.addEventListener('change', (event) => {
    updateActionStates(event.target.value);
  });

  // Attach event listeners to buttons
  document.getElementById('start-server-btn')?.addEventListener('click', (e) => startServer(e.currentTarget));
  document.getElementById('stop-server-btn')?.addEventListener('click', (e) => stopServer(e.currentTarget));
  document.getElementById('restart-server-btn')?.addEventListener('click', (e) => restartServer(e.currentTarget));
  document.getElementById('prompt-command-btn')?.addEventListener('click', (e) => promptCommand(e.currentTarget));
  document
    .getElementById('update-server-btn')
    ?.addEventListener('click', (e) => triggerServerUpdate(e.currentTarget, serverSelect.value));
  document
    .getElementById('delete-server-btn')
    ?.addEventListener('click', (e) => deleteServer(e.currentTarget, serverSelect.value));

  // Initial load
  updateDashboard();

  // Setup WebSocket connection and listeners
  setupWebSocket();

  // The global 'websocket-fallback' event listener in setupWebSocket will handle starting polling if needed.
  console.log(`${functionName}: Initialization complete.`);
}
