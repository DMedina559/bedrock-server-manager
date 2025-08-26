// frontend/src/content_management.js
/**
 * @fileoverview Frontend JavaScript functions for triggering content installation
 * (worlds and addons) via API calls based on user interaction.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

export function triggerWorldInstall(buttonElement, serverName, worldFilePath) {
  const filenameForDisplay = worldFilePath.split(/[\\/]/).pop() || worldFilePath;
  const confirmationMessage = `Install world '${filenameForDisplay}' for server '${serverName}'?\n\nWARNING: This will permanently REPLACE the current world data!`;
  if (!confirm(confirmationMessage)) {
    showStatusMessage('World installation cancelled.', 'info');
    return;
  }
  const requestBody = { filename: worldFilePath };
  const apiUrl = `/api/server/${serverName}/world/install`;
  sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);
}

export async function triggerWorldExport(buttonElement, serverName) {
  const absoluteActionPath = `/api/server/${serverName}/world/export`;
  const result = await sendServerActionRequest(null, absoluteActionPath, 'POST', null, buttonElement);
  if (result && result.status === 'success') {
    showStatusMessage(result.message + ' Refreshing list...', 'success');
    setTimeout(() => {
      window.location.reload();
    }, 2000);
  }
}

export async function triggerWorldReset(buttonElement, serverName) {
  if (!confirm(`WARNING: Reset the current world for server '${serverName}'?`)) {
    showStatusMessage('World reset cancelled.', 'info');
    return;
  }
  const absoluteActionPath = `/api/server/${serverName}/world/reset`;
  await sendServerActionRequest(null, absoluteActionPath, 'DELETE', null, buttonElement);
}

export function triggerAddonInstall(buttonElement, serverName, addonFilePath) {
  const filenameForDisplay = addonFilePath.split(/[\\/]/).pop() || addonFilePath;
  const confirmationMessage = `Install addon '${filenameForDisplay}' for server '${serverName}'?`;
  if (!confirm(confirmationMessage)) {
    showStatusMessage('Addon installation cancelled.', 'info');
    return;
  }
  const requestBody = { filename: addonFilePath };
  const apiUrl = `/api/server/${serverName}/addon/install`;
  sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);
}

export function initializeContentManagementPage() {
  console.log('Content management page script loaded.');

  const page = document.getElementById('content-management-page');
  const serverName = page?.dataset.serverName;

  document
    .getElementById('export-world-btn')
    ?.addEventListener('click', (e) => triggerWorldExport(e.currentTarget, serverName));
  document
    .getElementById('reset-world-btn')
    ?.addEventListener('click', (e) => triggerWorldReset(e.currentTarget, serverName));

  document.querySelectorAll('.install-addon-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      const btn = e.currentTarget;
      const addonPath = btn.dataset.addonPath;
      triggerAddonInstall(btn, serverName, addonPath);
    });
  });

  document.querySelectorAll('.import-world-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      const btn = e.currentTarget;
      const worldPath = btn.dataset.worldPath;
      triggerWorldInstall(btn, serverName, worldPath);
    });
  });
}
