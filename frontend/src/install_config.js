/**
 * @fileoverview Frontend JavaScript for handling the multi-step server installation
 * and configuration process.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';
import webSocketClient from './websocket_client.js';

function _clearValidationErrors() {
  const errorArea = document.getElementById('validation-error-area');
  if (errorArea) {
    errorArea.innerHTML = '';
    errorArea.style.display = 'none';
  }
  document.querySelectorAll('.validation-error').forEach((el) => (el.textContent = ''));
}

function _handleInstallSuccessNavigation(apiResponseData) {
  const nextUrl = apiResponseData?.next_step_url;
  const message = apiResponseData?.message || 'Server installed successfully!';
  if (nextUrl) {
    showStatusMessage(`${message} Proceeding to configuration...`, 'success');
    setTimeout(() => (window.location.href = nextUrl), 1500);
  } else {
    showStatusMessage('Server installed, but next step URL is missing.', 'warning');
  }
}

function pollTaskStatus(taskId, successCallback) {
  const intervalId = setInterval(async () => {
    try {
      const response = await fetch(`/api/tasks/status/${taskId}`);
      if (!response.ok) {
        clearInterval(intervalId);
        showStatusMessage(`Error checking task status: ${response.statusText}`, 'error');
        return;
      }
      const data = await response.json();
      if (data.status === 'success') {
        clearInterval(intervalId);
        if (successCallback) successCallback(data.result);
        else showStatusMessage(data.message || 'Task completed successfully.', 'success');
      } else if (data.status === 'error') {
        clearInterval(intervalId);
        showStatusMessage(`Task failed: ${data.message}`, 'error');
      }
      // No "in_progress" message spam for polling
    } catch (error) {
      clearInterval(intervalId);
      showStatusMessage(`Error polling task status: ${error.message}`, 'error');
    }
  }, 2000);
}

function monitorTaskWithWebSocket(taskId, successCallback) {
  const topic = `task:${taskId}`;
  console.log(`Monitoring task ${taskId} via WebSocket on topic ${topic}`);
  webSocketClient.subscribe(topic);

  const handleTaskUpdate = (event) => {
    const message = event.detail;

    // Only handle messages for this specific task
    if (!message || message.topic !== topic) {
      return;
    }

    const taskData = message.data;
    if (taskData.status === 'success') {
      showStatusMessage(taskData.message || 'Task completed successfully.', 'success');
      if (successCallback) successCallback(taskData.result);
      cleanup();
    } else if (taskData.status === 'error') {
      showStatusMessage(`Task failed: ${taskData.message}`, 'error');
      cleanup();
    } else if (taskData.message) {
      // Provide in-progress updates
      showStatusMessage(`Task in progress: ${taskData.message}`, 'info');
    }
  };

  const cleanup = () => {
    console.log(`Cleaning up listener for task ${taskId}`);
    webSocketClient.unsubscribe(topic);
    document.removeEventListener('websocket-message', handleTaskUpdate);
  };

  document.addEventListener('websocket-message', handleTaskUpdate);
}

export async function triggerInstallServer(buttonElement) {
  const serverNameInput = document.getElementById('install-server-name');
  const serverVersionInput = document.getElementById('install-server-version');
  const serverName = serverNameInput.value.trim();
  const serverVersion = serverVersionInput.value.trim() || 'LATEST';

  if (!serverName) return showStatusMessage('Server name cannot be empty.', 'warning');
  if (!/^[a-zA-Z0-9_-]+$/.test(serverName)) return showStatusMessage('Server name has invalid characters.', 'error');

  _clearValidationErrors();

  const requestBody = { server_name: serverName, server_version: serverVersion, overwrite: false };
  if (serverVersion.toUpperCase() === 'CUSTOM') {
    requestBody.server_zip_path = document.getElementById('custom-zip-path').value;
  }

  const startMonitoring = (taskResponse) => {
    if (webSocketClient.shouldUseFallback()) {
      console.warn('WebSocket not available, falling back to polling for task monitoring.');
      pollTaskStatus(taskResponse.task_id, _handleInstallSuccessNavigation);
    } else {
      monitorTaskWithWebSocket(taskResponse.task_id, _handleInstallSuccessNavigation);
    }
  };

  const initialResponse = await sendServerActionRequest(
    null,
    '/api/server/install',
    'POST',
    requestBody,
    buttonElement,
  );

  if (initialResponse) {
    if (initialResponse.status === 'confirm_needed') {
      if (confirm(initialResponse.message)) {
        const finalResponse = await sendServerActionRequest(
          null,
          '/api/server/install',
          'POST',
          { ...requestBody, overwrite: true },
          buttonElement,
        );
        if (finalResponse && finalResponse.status === 'pending') {
          startMonitoring(finalResponse);
        }
      } else {
        showStatusMessage('Installation cancelled.', 'info');
        if (buttonElement) buttonElement.disabled = false;
      }
    } else if (initialResponse.status === 'pending') {
      startMonitoring(initialResponse);
    }
  }
}

export async function saveProperties(buttonElement, serverName, isNewInstall) {
  const propertiesData = {};
  const formElements = document.querySelectorAll(
    '.properties-config-section .form-input, .properties-config-section .toggle-input, .properties-config-section input[type="hidden"]',
  );
  formElements.forEach((el) => {
    if (!el.name) return;
    if (el.type === 'checkbox' && el.classList.contains('toggle-input')) {
      if (el.checked) propertiesData[el.name.replace('-cb', '')] = 'true';
    } else if (el.type === 'hidden') {
      if (!el.disabled) propertiesData[el.name] = el.value;
    } else if (!el.classList.contains('toggle-input')) {
      propertiesData[el.name] = el.value;
    }
  });

  _clearValidationErrors();
  const response = await sendServerActionRequest(
    null,
    `/api/server/${serverName}/properties/set`,
    'POST',
    { properties: propertiesData },
    buttonElement,
  );

  if (response && response.status === 'success') {
    const message = response.message || 'Properties saved.';
    if (isNewInstall) {
      showStatusMessage(`${message} Proceeding to Allowlist...`, 'success');
      setTimeout(
        () => (window.location.href = `/server/${encodeURIComponent(serverName)}/configure_allowlist?new_install=True`),
        1500,
      );
    } else {
      showStatusMessage(message, 'success');
    }
  }
}

async function loadPermissions() {
  const loader = document.getElementById('permissions-loader');
  const tableBody = document.getElementById('permissions-table-body');
  const configSection = document.getElementById('install-config-page');
  const serverName = configSection?.dataset.serverName;

  if (!tableBody || !serverName) {
    console.error('Required elements for loading permissions not found.');
    return;
  }

  try {
    const data = await sendServerActionRequest(serverName, 'permissions/get', 'GET', null, null, true);
    tableBody.innerHTML = ''; // Clear loader/previous content

    if (data && data.status === 'success' && data.data && data.data.permissions && Array.isArray(data.data.permissions)) {
      const playerRowTemplate = document.getElementById('player-row-template');
      const noPlayersTemplate = document.getElementById('no-players-row-template');

      if (data.data.permissions.length > 0) {
        data.data.permissions.forEach((player) => {
          const rowClone = playerRowTemplate.content.cloneNode(true);
          rowClone.querySelector('.player-name').textContent = player.name;
          rowClone.querySelector('.player-xuid').textContent = player.xuid;
          const select = rowClone.querySelector('.permission-select');
          select.dataset.xuid = player.xuid;
          select.value = player.permission_level;
          tableBody.appendChild(rowClone);
        });
      } else {
        const noPlayersRow = noPlayersTemplate.content.cloneNode(true);
        tableBody.appendChild(noPlayersRow);
      }
      if (configSection) configSection.style.display = 'block';
    } else {
      showStatusMessage(data?.message || 'Failed to load permissions.', 'error');
    }
  } catch (error) {
    showStatusMessage(`Client-side error loading permissions: ${error.message}`, 'error');
  } finally {
    if (loader) loader.style.display = 'none';
  }
}

export async function savePermissions(buttonElement, serverName, isNewInstall) {
  const permissions = Array.from(document.querySelectorAll('select.permission-select')).map((select) => ({
    xuid: select.dataset.xuid,
    name: select.closest('tr').querySelector('.player-name').textContent.trim(),
    permission_level: select.value,
  }));

  _clearValidationErrors();
  const response = await sendServerActionRequest(
    null,
    `/api/server/${serverName}/permissions/set`,
    'PUT',
    { permissions },
    buttonElement,
  );

  if (response && response.status === 'success') {
    const message = response.message || 'Permissions saved.';
    if (isNewInstall) {
      showStatusMessage(`${message} Proceeding to Service Config...`, 'success');
      setTimeout(
        () => (window.location.href = `/server/${encodeURIComponent(serverName)}/configure_service?new_install=True`),
        1500,
      );
    } else {
      showStatusMessage(message, 'success');
    }
  }
}

export async function saveServiceSettings(buttonElement, serverName, currentOs, isNewInstall) {
  const settings = {
    autoupdate: document.getElementById('service-autoupdate-cb').checked,
    autostart: document.getElementById('service-autostart-cb').checked,
  };
  const startAfter = isNewInstall && document.getElementById('service-start-server').checked;

  _clearValidationErrors();
  const saveResponse = await sendServerActionRequest(
    null,
    `/api/server/${serverName}/service/update`,
    'POST',
    settings,
    buttonElement,
  );

  if (saveResponse && ['success', 'success_with_warning'].includes(saveResponse.status)) {
    const message = saveResponse.message || 'Service settings saved.';
    if (startAfter) {
      showStatusMessage(`${message} Starting server...`, 'info');
      const startResponse = await sendServerActionRequest(serverName, 'start', 'POST', null, buttonElement);
      if (startResponse && startResponse.status === 'success') {
        showStatusMessage('Server started! Installation complete. Redirecting...', 'success');
        setTimeout(() => (window.location.href = '/'), 2000);
      } else {
        showStatusMessage(
          `Settings saved, but server failed to start: ${startResponse?.message || 'Unknown error'}`,
          'warning',
        );
      }
    } else if (isNewInstall) {
      showStatusMessage(`${message} Installation complete! Redirecting...`, 'success');
      setTimeout(() => (window.location.href = '/'), 1500);
    } else {
      showStatusMessage(message, 'success');
    }
  }
}

async function checkCustomVersion(version) {
  const customZipGroup = document.getElementById('custom-zip-selector-group');
  const zipListContainer = document.getElementById('custom-zip-list');
  const hiddenInput = document.getElementById('custom-zip-path');

  if (version.toUpperCase() === 'CUSTOM') {
    customZipGroup.style.display = 'block';
    const data = await sendServerActionRequest(null, '/api/downloads/list', 'GET', null, null, true);
    zipListContainer.innerHTML = '';
    hiddenInput.value = '';

    if (data && data.custom_zips && data.custom_zips.length > 0) {
      data.custom_zips.forEach((zip, index) => {
        const radioId = `custom-zip-${index}`;
        const radioWrapper = document.createElement('div');
        radioWrapper.classList.add('radio-item');

        const input = document.createElement('input');
        input.type = 'radio';
        input.id = radioId;
        input.name = 'custom-zip-selection';
        input.value = zip;
        input.addEventListener('change', () => {
          hiddenInput.value = zip;
        });

        const label = document.createElement('label');
        label.htmlFor = radioId;
        label.textContent = zip;

        radioWrapper.appendChild(input);
        radioWrapper.appendChild(label);
        zipListContainer.appendChild(radioWrapper);

        // Pre-select the first item
        if (index === 0) {
          input.checked = true;
          hiddenInput.value = zip;
        }
      });
    } else {
      zipListContainer.innerHTML = '<p>No custom zips found in the downloads/custom directory.</p>';
    }
  } else {
    customZipGroup.style.display = 'none';
    hiddenInput.value = '';
  }
}

export function initializeInstallConfigPage() {
  console.log('Install/config page script loaded.');

  const installConfigPage = document.getElementById('install-config-page');
  const serverName = installConfigPage?.dataset.serverName;
  const isNewInstall = installConfigPage?.dataset.isNewInstall === 'true';
  const os = installConfigPage?.dataset.os;

  const serverVersionInput = document.getElementById('install-server-version');
  if (serverVersionInput) {
    serverVersionInput.addEventListener('input', (e) => checkCustomVersion(e.target.value));
    // Also check on initial load
    checkCustomVersion(serverVersionInput.value);
  }

  document
    .getElementById('install-server-btn')
    ?.addEventListener('click', (e) => triggerInstallServer(e.currentTarget));
  document
    .getElementById('save-permissions-btn')
    ?.addEventListener('click', (e) => savePermissions(e.currentTarget, serverName, isNewInstall));
  document
    .getElementById('submit-properties-btn')
    ?.addEventListener('click', (e) => saveProperties(e.currentTarget, serverName, isNewInstall));
  document
    .getElementById('save-service-settings-btn')
    ?.addEventListener('click', (e) => saveServiceSettings(e.currentTarget, serverName, os, isNewInstall));

  if (new URLSearchParams(window.location.search).has('in_setup')) {
    const bannerContainer = document.getElementById('setup-banner-container');
    if (bannerContainer) {
      bannerContainer.innerHTML = `
            <div class="setup-banner">
                <h3>Step 3: Install a Server</h3>
                <p>
                    Install and configure your first Bedrock Server. This will include setting server.properties, allowlist, and other files.
                </p>
                <a href="/" class="action-button">Skip</a>
            </div>
        `;
    }
  }

  // Custom controls initialization
  document.querySelectorAll('.segmented-control').forEach((control) => {
    const input = document.getElementById(control.dataset.inputId);
    if (input) {
      control.querySelectorAll('.segment').forEach((segment) => {
        segment.addEventListener('click', (e) => {
          e.preventDefault();
          input.value = segment.dataset.value;
          control.querySelectorAll('.segment').forEach((s) => s.classList.remove('active'));
          segment.classList.add('active');
        });
      });
    }
  });

  document.querySelectorAll('.toggle-input').forEach((input) => {
    const hidden = input
      .closest('.form-group-toggle-container')
      ?.querySelector(`.toggle-hidden-false[name="${input.name.replace('-cb', '')}"]`);
    if (hidden) {
      const sync = () => (hidden.disabled = input.checked);
      input.addEventListener('change', sync);
      sync();
    }
  });

  // Logic from configure_properties.html
  const setInputValue = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.value = value;
  };

  const setToggleState = (id, value) => {
    const el = document.getElementById(id);
    if (el) {
      el.checked = String(value).toLowerCase() === 'true';
      el.dispatchEvent(new Event('change'));
    }
  };

  const setSegmentedControlState = (hiddenInputId, value) => {
    const hiddenInput = document.getElementById(hiddenInputId);
    const controlWrapper = document.querySelector(`[data-input-id="${hiddenInputId}"]`);
    if (hiddenInput && controlWrapper) {
      hiddenInput.value = value;
      controlWrapper.querySelectorAll('.segment').forEach((s) => s.classList.remove('active'));
      const activeSegment = controlWrapper.querySelector(`.segment[data-value="${value}"]`);
      if (activeSegment) activeSegment.classList.add('active');
    }
  };

  function populateForm(properties) {
    const propertyMap = {
      'server-name': { id: 'server-name', type: 'input' },
      'level-name': { id: 'level-name', type: 'input' },
      gamemode: { id: 'gamemode-hidden', type: 'segment' },
      difficulty: { id: 'difficulty-hidden', type: 'segment' },
      'allow-cheats': { id: 'allow-cheats-cb', type: 'toggle' },
      'max-players': { id: 'max-players', type: 'input' },
      'level-seed': { id: 'level-seed', type: 'input' },
      'server-port': { id: 'server-port', type: 'input' },
      'server-portv6': { id: 'server-portv6', type: 'input' },
      'enable-lan-visibility': { id: 'enable-lan-visibility-cb', type: 'toggle' },
      'allow-list': { id: 'allow-list-cb', type: 'toggle' },
      'default-player-permission-level': { id: 'default-player-permission-level-hidden', type: 'segment' },
      'view-distance': { id: 'view-distance', type: 'input' },
      'tick-distance': { id: 'tick-distance', type: 'input' },
      'online-mode': { id: 'online-mode-cb', type: 'toggle' },
      'texturepack-required': { id: 'texturepack-required-cb', type: 'toggle' },
    };

    for (const key in properties) {
      if (Object.prototype.hasOwnProperty.call(properties, key) && propertyMap[key]) {
        const prop = propertyMap[key];
        const value = properties[key];
        if (value === undefined) continue;

        switch (prop.type) {
          case 'input':
            setInputValue(prop.id, value);
            break;
          case 'toggle':
            setToggleState(prop.id, value);
            break;
          case 'segment':
            setSegmentedControlState(prop.id, value);
            break;
        }
      }
    }
  }

  async function loadProperties() {
    const loader = document.getElementById('properties-loader');
    const formContainer = document.getElementById('properties-form-container');
    try {
      const data = await sendServerActionRequest(serverName, 'properties/get', 'GET', null, null);
      if (data && data.status === 'success' && data.properties) {
        populateForm(data.properties);
        if (formContainer) formContainer.style.display = 'block';
      } else {
        showStatusMessage(data?.message || 'Failed to load server properties.', 'error');
      }
    } catch (error) {
      showStatusMessage(`Client-side error loading properties: ${error.message}`, 'error');
    } finally {
      if (loader) loader.style.display = 'none';
    }
  }

  if (document.getElementById('properties-form-container')) {
    loadProperties();
  }

  if (document.getElementById('permissions-table-body')) {
    loadPermissions();
  }
}
