// bedrock-server-manager/web/static/js/backup_restore.js
/**
 * @fileoverview Frontend JavaScript functions for triggering server backup and restore operations.
 * These functions typically gather necessary info, show confirmation dialogs, and
 * then call `sendServerActionRequest` (from utils.js) to interact with the backend API.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded before this script
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    // Optionally display an error to the user on the page itself
}

/**
 * Initiates a backup operation via the API based on the specified type.
 * Shows a confirmation prompt for 'all' type backups.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked, used for disabling during the request.
 * @param {string} serverName - The name of the server to back up.
 * @param {string} backupType - The type of backup requested ('world', 'config', 'all'). Note: 'config' type here implies backing up *all* standard config files unless `triggerSpecificConfigBackup` is used.
 */
function triggerBackup(buttonElement, serverName, backupType) {
    const functionName = 'triggerBackup';
    console.log(`${functionName}: Initiated. Server: '${serverName}', Type: '${backupType}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Confirmation for potentially long/impactful operations ---
    if (backupType === 'all') {
        console.debug(`${functionName}: Backup type is 'all'. Prompting user for confirmation.`);
        const confirmationMessage = `Perform a full backup (world + standard config files) for server '${serverName}'? This may take a few moments.`;
        if (!confirm(confirmationMessage)) {
            console.log(`${functionName}: Full backup cancelled by user.`);
            showStatusMessage('Full backup cancelled.', 'info');
            return; // Abort operation
        }
        console.log(`${functionName}: User confirmed 'all' backup.`);
    }

    // --- Prepare API Request ---
    const requestBody = {
        backup_type: backupType
        // 'file_to_backup' is NOT included here; this triggers backup of the type specified ('world' or 'all')
        // or implicitly backs up standard configs if backupType is 'config' without a specific file.
        // The backend API handler for 'config' without a file needs to handle this case if desired.
        // Usually, the UI would call triggerSpecificConfigBackup for individual files.
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const absoluteActionPath = `/api/server/${serverName}/backup/action`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${absoluteActionPath} for backup type '${backupType}'...`);
    // sendServerActionRequest handles disabling button, showing status messages, and handling response
    sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Backup request initiated (asynchronous).`);
}

/**
 * Initiates a backup operation for a *specific* configuration file via the API.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked.
 * @param {string} serverName - The name of the server.
 * @param {string} filename - The relative path or name of the specific configuration file to back up (e.g., "server.properties").
 */
function triggerSpecificConfigBackup(buttonElement, serverName, filename) {
    const functionName = 'triggerSpecificConfigBackup';
    console.log(`${functionName}: Initiated. Server: '${serverName}', File: '${filename}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!filename || typeof filename !== 'string' || !filename.trim()) {
        const errorMsg = "Internal error: No filename provided for specific config backup.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedFilename = filename.trim();

    // --- Prepare API Request ---
    const requestBody = {
        backup_type: 'config', // Specify config type
        file_to_backup: trimmedFilename // Provide the specific filename
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const absoluteActionPath = `/api/server/${serverName}/backup/action`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${absoluteActionPath} for specific config backup ('${trimmedFilename}')...`);
    sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Specific config backup request initiated (asynchronous).`);
}

/**
 * Initiates a restore operation for a specific backup file via the API, after user confirmation.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked.
 * @param {string} serverName - The name of the server to restore to.
 * @param {string} restoreType - The type of restore ('world' or 'config').
 * @param {string} backupFilePath - The full path (as known by the server/backend) of the backup file to restore.
 */
function triggerRestore(buttonElement, serverName, restoreType, backupFilePath) {
    const functionName = 'triggerRestore';
    console.log(`${functionName}: Initiated. Server: '${serverName}', Type: '${restoreType}', File: '${backupFilePath}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!backupFilePath || typeof backupFilePath !== 'string' || !backupFilePath.trim()) {
        const errorMsg = "Internal error: No backup file path provided for restore.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedBackupFilePath = backupFilePath.trim();
    const backupFilename = trimmedBackupFilePath.split(/[\\/]/).pop(); // Extract filename for messages

    const validTypes = ['world', 'properties', 'allowlist', 'permissions'];
    if (!restoreType || !validTypes.includes(restoreType.toLowerCase())) {
        const errorMsg = `Internal error: Invalid restore type '${restoreType}'.`;
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const normalizedRestoreType = restoreType.toLowerCase();

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for restore confirmation.`);
    const confirmationMessage = `Are you sure you want to restore backup '${backupFilename}' for server '${serverName}'?\n\nThis will OVERWRITE the current server ${normalizedRestoreType} data!`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Restore operation cancelled by user.`);
        showStatusMessage('Restore operation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log(`${functionName}: User confirmed restore operation.`);

    // --- Prepare API Request ---
    const requestBody = {
        restore_type: normalizedRestoreType,
        backup_file: trimmedBackupFilePath // Send the full path
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const absoluteActionPath = `/api/server/${serverName}/restore/action`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${absoluteActionPath} for restore type '${normalizedRestoreType}'...`);
    sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Restore request initiated (asynchronous).`);
}

/**
 * Initiates restoring ALL latest backup files (world, configs) for a server via the API,
 * after user confirmation.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked.
 * @param {string} serverName - The name of the server to restore.
 */
function triggerRestoreAll(buttonElement, serverName) {
    const functionName = 'triggerRestoreAll';
    console.log(`${functionName}: Initiated for server: '${serverName}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for Restore All confirmation.`);
    const confirmationMessage = `Are you sure you want to restore ALL latest backups for server '${serverName}'?\n\nThis will OVERWRITE the current world and configuration files!`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Restore All operation cancelled by user.`);
        showStatusMessage('Restore All operation cancelled.', 'info');
        return;
    }
    console.log(`${functionName}: User confirmed Restore All operation.`);

    // --- Prepare API Request ---
    // For a 'restore all' operation, the backend doesn't need a specific backup file.
    const requestBody = {
        restore_type: 'all',
        backup_file: null // Explicitly send null
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const absoluteActionPath = `/api/server/${serverName}/restore/action`;
    console.log(`${functionName}: Calling sendServerActionRequest to ${absoluteActionPath} for restore all...`);
    sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Restore All request initiated (asynchronous).`);
}


/**
 * Handles the click for selecting a backup type to restore.
 * This will make an API call to an endpoint that then shows the selection page.
 *
 * @param {HTMLButtonElement} buttonElement - The button element clicked.
 * @param {string} serverName - The name of the server.
 * @param {string} restoreType - The type of restore to initiate (e.g., 'world', 'properties').
 */
async function handleSelectBackupType(buttonElement, serverName, restoreType) {
    const functionName = 'handleSelectBackupType';
    console.log(`${functionName}: Initiated for server '${serverName}', type '${restoreType}'.`);

    const requestBody = {
        restore_type: restoreType
    };

    // The API endpoint for this action will be POST /backup-restore/api/server/<serverName>/restore/select_backup_type
    // It should return a JSON response. If successful, the response might contain 
    // a URL to redirect to.

    const absoluteActionPath = `/api/server/${serverName}/restore/select_backup_type`;

    try {
        // Assuming sendServerActionRequest returns a promise that resolves with the response data
        const responseData = await sendServerActionRequest(null, absoluteActionPath, 'POST', requestBody, buttonElement);

        if (responseData && responseData.status === 'success') {
            // Backend returns a URL to redirect to
            if (responseData.redirect_url) {
                console.log(`${functionName}: Redirecting to ${responseData.redirect_url}`);
                window.location.href = responseData.redirect_url;
            }
            // Option 2: Backend returns HTML content to inject (more complex)
            // else if (responseData.html_content) {
            //     console.log(`${functionName}: Received HTML content to display.`);
            //     // This would require significant changes to how the page flow works.
            //     // For now, a redirect is simpler if the backend can provide it.
            //     // If not, the backend might need to be updated to provide a redirect_url
            //     // or this JS needs to handle raw data and build the next step.
            // } 
            else {
                // Fallback: If successful but no clear next step from API, log and show message.
                // This might happen if the API itself handles the redirect (e.g. returns a 302)
                // which sendServerActionRequest might not fully handle for page navigation.
                console.log(`${functionName}: Action successful. Response:`, responseData);
                if (responseData.message) {
                    showStatusMessage(responseData.message, 'success');
                }
                // If the Python route itself renders and returns HTML, window.location.href might not be needed
                // if the fetch response is directly the new page's HTML. But sendServerActionRequest expects JSON.
                // For now, this assumes the Python route will respond with JSON that includes a redirect_url.
            }
        } else if (responseData && responseData.status === 'error') {
            console.error(`${functionName}: API error: ${responseData.message}`);
            showStatusMessage(responseData.message || 'Failed to initiate backup type selection.', 'error');
        } else if (responseData === false) {
            // sendServerActionRequest returned false, meaning a fetch/network error or CSRF token issue (though CSRF is removed).
            // The error message should have already been shown by sendServerActionRequest.
            console.error(`${functionName}: sendServerActionRequest failed.`);
        }
    } catch (error) {
        console.error(`${functionName}: Unexpected error: ${error.message}`, error);
        showStatusMessage('An unexpected error occurred.', 'error');
        if (buttonElement) buttonElement.disabled = false; // Ensure button is re-enabled
    }
}