// frontend/src/backup_restore.js
/**
 * @fileoverview Frontend JavaScript functions for triggering server backup and restore operations.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

export function triggerBackup(buttonElement, serverName, backupType) {
  const functionName = 'triggerBackup';
  console.log(`${functionName}: Initiated. Server: '${serverName}', Type: '${backupType}'`);

  if (backupType === 'all') {
    const confirmationMessage = `Perform a full backup (world + config) for server '${serverName}'?`;
    if (!confirm(confirmationMessage)) {
      showStatusMessage('Full backup cancelled.', 'info');
      return;
    }
  }

  const requestBody = { backup_type: backupType };
  const absoluteActionPath = `/api/server/${serverName}/backup/action`;
  sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);
}

export function triggerSpecificConfigBackup(buttonElement, serverName, filename) {
  const functionName = 'triggerSpecificConfigBackup';
  console.log(`${functionName}: Initiated. Server: '${serverName}', File: '${filename}'`);

  if (!filename || !filename.trim()) {
    showStatusMessage('Internal error: No filename provided.', 'error');
    return;
  }

  const requestBody = {
    backup_type: 'config',
    file_to_backup: filename.trim(),
  };
  const absoluteActionPath = `/api/server/${serverName}/backup/action`;
  sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);
}

export function triggerRestore(buttonElement, serverName, restoreType, backupFilePath) {
  const functionName = 'triggerRestore';
  console.log(`${functionName}: Initiated. Server: '${serverName}', Type: '${restoreType}', File: '${backupFilePath}'`);

  if (!backupFilePath || !backupFilePath.trim()) {
    showStatusMessage('Internal error: No backup file path provided.', 'error');
    return;
  }

  const backupFilename = backupFilePath.trim().split(/[\\/]/).pop();
  const confirmationMessage = `Are you sure you want to restore backup '${backupFilename}' for server '${serverName}'? This will OVERWRITE current data!`;
  if (!confirm(confirmationMessage)) {
    showStatusMessage('Restore operation cancelled.', 'info');
    return;
  }

  const requestBody = {
    restore_type: restoreType.toLowerCase(),
    backup_file: backupFilePath.trim(),
  };
  const absoluteActionPath = `/api/server/${serverName}/restore/action`;
  sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);
}

export function triggerRestoreAll(buttonElement, serverName) {
  const functionName = 'triggerRestoreAll';
  console.log(`${functionName}: Initiated for server: '${serverName}'`);

  const confirmationMessage = `Are you sure you want to restore ALL latest backups for server '${serverName}'? This will OVERWRITE current world and configuration files!`;
  if (!confirm(confirmationMessage)) {
    showStatusMessage('Restore All operation cancelled.', 'info');
    return;
  }

  const requestBody = {
    restore_type: 'all',
    backup_file: null,
  };
  const absoluteActionPath = `/api/server/${serverName}/restore/action`;
  sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);
}

export async function handleSelectBackupType(buttonElement, serverName, restoreType) {
  const functionName = 'handleSelectBackupType';
  console.log(`${functionName}: Initiated for server '${serverName}', type '${restoreType}'.`);

  const requestBody = { restore_type: restoreType };
  const absoluteActionPath = `/api/server/${serverName}/restore/select_backup_type`;

  try {
    const responseData = await sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);
    if (responseData && responseData.status === 'success' && responseData.redirect_url) {
      window.location.href = responseData.redirect_url;
    } else if (responseData && responseData.message) {
      showStatusMessage(responseData.message, responseData.status === 'success' ? 'success' : 'error');
    }
  } catch (error) {
    console.error(`${functionName}: Unexpected error: ${error.message}`, error);
    showStatusMessage('An unexpected error occurred.', 'error');
    if (buttonElement) buttonElement.disabled = false;
  }
}

export function initializeBackupRestorePage() {
  console.log('Backup/Restore page script loaded.');

  const page = document.getElementById('backup-restore-page');
  const serverName = page?.dataset.serverName;

  document
    .getElementById('backup-world-btn')
    ?.addEventListener('click', (e) => triggerBackup(e.currentTarget, serverName, 'world'));
  document
    .getElementById('backup-all-btn')
    ?.addEventListener('click', (e) => triggerBackup(e.currentTarget, serverName, 'all'));

  document
    .getElementById('select-world-backup-btn')
    ?.addEventListener('click', (e) => handleSelectBackupType(e.currentTarget, serverName, 'world'));
  document
    .getElementById('select-properties-backup-btn')
    ?.addEventListener('click', (e) => handleSelectBackupType(e.currentTarget, serverName, 'properties'));
  document
    .getElementById('select-allowlist-backup-btn')
    ?.addEventListener('click', (e) => handleSelectBackupType(e.currentTarget, serverName, 'allowlist'));
  document
    .getElementById('select-permissions-backup-btn')
    ?.addEventListener('click', (e) => handleSelectBackupType(e.currentTarget, serverName, 'permissions'));
  document
    .getElementById('restore-all-btn')
    ?.addEventListener('click', (e) => triggerRestoreAll(e.currentTarget, serverName));

  document
    .getElementById('backup-allowlist-btn')
    ?.addEventListener('click', (e) => triggerSpecificConfigBackup(e.currentTarget, serverName, 'allowlist.json'));
  document
    .getElementById('backup-permissions-btn')
    ?.addEventListener('click', (e) => triggerSpecificConfigBackup(e.currentTarget, serverName, 'permissions.json'));
  document
    .getElementById('backup-properties-btn')
    ?.addEventListener('click', (e) => triggerSpecificConfigBackup(e.currentTarget, serverName, 'server.properties'));

  document.querySelectorAll('.restore-backup-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      const btn = e.currentTarget;
      const restoreType = btn.dataset.restoreType;
      const backupPath = btn.dataset.backupPath;
      triggerRestore(btn, serverName, restoreType, backupPath);
    });
  });
}
