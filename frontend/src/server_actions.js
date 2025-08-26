// frontend/src/server_actions.js
/**
 * @fileoverview Frontend JavaScript functions for triggering common server actions
 * like start, stop, restart, delete, update, and sending commands via API calls.
 * These are typically attached to onclick events of buttons in the UI.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

/**
 * Gets the currently selected server name from the '#server-select' dropdown.
 * Displays a warning message if no server is selected or the dropdown is missing.
 *
 * @returns {string|null} The selected server name, or null if selection is invalid or element missing.
 */
function getSelectedServer() {
  const functionName = 'getSelectedServer';
  console.debug(`${functionName}: Attempting to get selected server from #server-select dropdown.`);

  const serverSelect = document.getElementById('server-select');
  if (!serverSelect) {
    const errorMsg = "Internal page error: Server selection dropdown element ('#server-select') not found.";
    console.error(`${functionName}: ${errorMsg}`);
    showStatusMessage(errorMsg, 'error');
    return null;
  }

  const selectedServer = serverSelect.value; // The value attribute of the selected <option>
  console.debug(`${functionName}: Value from dropdown: "${selectedServer}"`);

  if (!selectedServer || selectedServer === '') {
    // Check for empty string value explicitly
    const warnMsg = 'Please select a server from the dropdown list first.';
    console.warn(`${functionName}: ${warnMsg}`);
    showStatusMessage(warnMsg, 'warning');
    return null;
  }

  console.debug(`${functionName}: Returning selected server name: '${selectedServer}'`);
  return selectedServer;
}

// --- Global Action Functions (Typically called via onclick) ---

/**
 * Initiates the 'start' server action via API for the currently selected server.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Start' button element clicked.
 */
export function startServer(buttonElement) {
  const functionName = 'startServer';
  console.log(`${functionName}: Action triggered.`);
  console.debug(`${functionName}: Button Element:`, buttonElement);

  const serverName = getSelectedServer(); // Get selected server, handles null/warning message
  if (serverName) {
    const actionPath = 'start'; // Relative API path
    const method = 'POST';
    console.log(`${functionName}: Attempting to start server '${serverName}' via API call to ${actionPath}...`);
    sendServerActionRequest(serverName, actionPath, method, null, buttonElement);
    console.log(`${functionName}: API request initiated for '${serverName}' (asynchronous).`);
  } else {
    console.warn(`${functionName}: Action aborted because no server was selected.`);
    // User message already shown by getSelectedServer()
  }
}

/**
 * Initiates the 'stop' server action via API for the currently selected server.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Stop' button element clicked.
 */
export function stopServer(buttonElement) {
  const functionName = 'stopServer';
  console.log(`${functionName}: Action triggered.`);
  console.debug(`${functionName}: Button Element:`, buttonElement);

  const serverName = getSelectedServer();
  if (serverName) {
    const actionPath = 'stop';
    const method = 'POST';
    console.log(`${functionName}: Attempting to stop server '${serverName}' via API call to ${actionPath}...`);
    sendServerActionRequest(serverName, actionPath, method, null, buttonElement);
    console.log(`${functionName}: API request initiated for '${serverName}' (asynchronous).`);
  } else {
    console.warn(`${functionName}: Action aborted because no server was selected.`);
  }
}

/**
 * Initiates the 'restart' server action via API for the currently selected server.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Restart' button element clicked.
 */
export function restartServer(buttonElement) {
  const functionName = 'restartServer';
  console.log(`${functionName}: Action triggered.`);
  console.debug(`${functionName}: Button Element:`, buttonElement);

  const serverName = getSelectedServer();
  if (serverName) {
    const actionPath = 'restart';
    const method = 'POST';
    console.log(`${functionName}: Attempting to restart server '${serverName}' via API call to ${actionPath}...`);
    sendServerActionRequest(serverName, actionPath, method, null, buttonElement);
    console.log(`${functionName}: API request initiated for '${serverName}' (asynchronous).`);
  } else {
    console.warn(`${functionName}: Action aborted because no server was selected.`);
  }
}

/**
 * Prompts the user to enter a console command and sends it to the currently selected server via API.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Send Command' button element clicked.
 */
export function promptCommand(buttonElement) {
  const functionName = 'promptCommand';
  console.log(`${functionName}: Action triggered.`);
  console.debug(`${functionName}: Button Element:`, buttonElement);

  const serverName = getSelectedServer();
  if (!serverName) {
    console.warn(`${functionName}: Action aborted because no server was selected.`);
    return; // Exit if no server selected
  }

  // --- User Interaction: Prompt for Command ---
  console.debug(`${functionName}: Prompting user for command input for server '${serverName}'.`);
  const command = prompt(`Enter command to send to server '${serverName}':`);
  // --- End User Interaction ---

  if (command === null) {
    // User pressed Cancel on the prompt
    console.log(`${functionName}: Command input cancelled by user.`);
    showStatusMessage('Command input cancelled.', 'info');
    return;
  }

  const trimmedCommand = command.trim();
  console.debug(`${functionName}: User entered command: "${command}", Trimmed: "${trimmedCommand}"`);

  if (trimmedCommand === '') {
    console.warn(`${functionName}: Command is empty after trimming.`);
    showStatusMessage('Command cannot be empty.', 'warning');
    return; // Don't send empty command
  }

  // --- Prepare and Send API Request ---
  const actionPath = 'send_command';
  const method = 'POST';
  const requestBody = { command: trimmedCommand }; // API expects command in body
  console.debug(`${functionName}: Constructed request body:`, requestBody);
  console.log(
    `${functionName}: Attempting to send command '${trimmedCommand}' to server '${serverName}' via API call to ${actionPath}...`,
  );
  sendServerActionRequest(serverName, actionPath, method, requestBody, buttonElement);
  console.log(`${functionName}: API request initiated for '${serverName}' (asynchronous).`);
}

/**
 * Prompts the user for confirmation and initiates the 'delete' server action via API.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Delete' button element clicked.
 * @param {string} serverName - The name of the server to delete (passed directly, not from select).
 */
export function deleteServer(buttonElement, serverName) {
  const functionName = 'deleteServer';
  console.log(`${functionName}: Action triggered for server: '${serverName}'`);
  console.debug(`${functionName}: Button Element:`, buttonElement);

  // --- Input Validation ---
  if (!serverName || typeof serverName !== 'string' || !serverName.trim()) {
    const errorMsg = 'Internal error: Server name is missing or invalid for delete action.';
    console.error(`${functionName}: ${errorMsg}`);
    showStatusMessage(errorMsg, 'error');
    return;
  }
  const trimmedServerName = serverName.trim(); // Use trimmed name internally

  // --- Confirmation ---
  console.debug(`${functionName}: Prompting user for delete confirmation for server '${trimmedServerName}'.`);
  const confirmationMessage = `Are you absolutely sure you want to delete ALL data for server '${trimmedServerName}'?\n\nThis includes installation, configuration, and backups and cannot be undone!`;
  if (confirm(confirmationMessage)) {
    console.log(`${functionName}: Deletion confirmed by user for '${trimmedServerName}'. Sending API request...`);
    // --- Prepare and Send API Request ---
    const actionPath = 'delete';
    const method = 'DELETE'; // Use DELETE HTTP method
    // Call API helper
    sendServerActionRequest(trimmedServerName, actionPath, method, null, buttonElement);
    console.log(`${functionName}: API request initiated for '${trimmedServerName}' (asynchronous).`);
    // Success/Error message handled by sendServerActionRequest
    // Consider adding specific logic here to remove the server row from the UI *after* successful deletion response?
  } else {
    console.log(`${functionName}: Deletion cancelled by user for '${trimmedServerName}'.`);
    showStatusMessage('Deletion cancelled.', 'info');
  }
}

/**
 * Initiates the 'update' server action via API for a specific server.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Update' button element clicked.
 * @param {string} serverName - The name of the server to update (passed directly).
 */
export function triggerServerUpdate(buttonElement, serverName) {
  const functionName = 'triggerServerUpdate';
  console.log(`${functionName}: Action triggered for server: '${serverName}'`);
  console.debug(`${functionName}: Button Element:`, buttonElement);

  // --- Input Validation ---
  if (!serverName || typeof serverName !== 'string' || !serverName.trim()) {
    const errorMsg = 'Internal error: Server name is missing or invalid for update action.';
    console.error(`${functionName}: ${errorMsg}`);
    showStatusMessage(errorMsg, 'error');
    return;
  }
  const trimmedServerName = serverName.trim();

  // --- Confirmation (Optional, but recommended for potentially long operations) ---
  // const confirmationMessage = `Check for updates and update server '${trimmedServerName}' if needed?`;
  // if (!confirm(confirmationMessage)) {
  //     console.log(`${functionName}: Update cancelled by user for '${trimmedServerName}'.`);
  //     showStatusMessage('Update cancelled.', 'info');
  //     return;
  // }
  // console.log(`${functionName}: User confirmed update check for '${trimmedServerName}'.`);

  // --- Prepare and Send API Request ---
  const actionPath = 'update';
  const method = 'POST';
  console.log(`${functionName}: Attempting to update server '${trimmedServerName}' via API call to ${actionPath}...`);
  sendServerActionRequest(trimmedServerName, actionPath, method, null, buttonElement);
  console.log(`${functionName}: API request initiated for '${trimmedServerName}' (asynchronous).`);
}
