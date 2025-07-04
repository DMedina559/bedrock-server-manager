// bedrock_server_manager/web/static/js/content_management.js
/**
 * @fileoverview Frontend JavaScript functions for triggering content installation
 * (worlds and addons) via API calls based on user interaction.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded before this script
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    // Optionally display an error to the user on the page itself
}

/**
 * Handles the user clicking an 'Install World' button.
 * Prompts for confirmation (warning about overwrites) and then calls the API
 * endpoint to install the specified world file.
 *
 * @param {HTMLButtonElement} buttonElement - The 'Install' button element that was clicked.
 * @param {string} serverName - The name of the target server.
 * @param {string} worldFilePath - The full path or unique identifier of the .mcworld file
 *                                (as provided by the backend/template).
 */
function triggerWorldInstall(buttonElement, serverName, worldFilePath) {
    const functionName = 'triggerWorldInstall';
    console.log(`${functionName}: Initiated. Server: '${serverName}', File: '${worldFilePath}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!worldFilePath || typeof worldFilePath !== 'string' || !worldFilePath.trim()) {
        const errorMsg = "Internal error: World file path is missing or invalid.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedWorldFilePath = worldFilePath.trim();

    // Extract filename for user messages (handles / and \ separators)
    const filenameForDisplay = trimmedWorldFilePath.split(/[\\/]/).pop() || trimmedWorldFilePath;
    console.debug(`${functionName}: Extracted filename for display: '${filenameForDisplay}'`);

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for world install confirmation.`);
    const confirmationMessage = `Install world '${filenameForDisplay}' for server '${serverName}'?\n\n` +
        `WARNING: This will permanently REPLACE the current world data for this server! Continue?`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: World installation cancelled by user.`);
        showStatusMessage('World installation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log(`${functionName}: User confirmed world installation.`);

    // --- Prepare API Request ---
    const requestBody = {
        filename: trimmedWorldFilePath // Send the path/identifier provided by the backend
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/world/install`; // Updated for FastAPI prefix
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl}...`);
    // sendServerActionRequest handles button disabling, status messages, and response processing
    sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: World install request initiated (asynchronous).`);
}


/**
 * Initiates the world export process by sending an API request.
 * Assumes 'sendServerActionRequest' is globally available.
 *
 * @param {HTMLElement} buttonElement - The button element that was clicked.
 * @param {string} serverName - The name of the server whose world should be exported.
 */
async function triggerWorldExport(buttonElement, serverName) {
    const functionName = 'triggerWorldExport';
    console.log(`${functionName}: Triggered for server '${serverName}'`);

    // Confirm export if desired, though it's not destructive like import
    // if (!confirm(`Export the current world for server '${serverName}'?`)) {
    //     console.log(`${functionName}: User cancelled export.`);
    //     showStatusMessage("World export cancelled.", "info");
    //     return;
    // }

    console.log(`${functionName}: Sending API request to export world.`);
    // Call the generic request handler
    // Export endpoint doesn't require a request body (body = null)
    const absoluteActionPath = `/api/server/${serverName}/world/export`; // Updated for FastAPI prefix
    const result = await sendServerActionRequest(
        null, // serverName is now part of absolute path
        absoluteActionPath,
        'POST',
        null,           // No request body needed
        buttonElement
    );

    // Handle specific responses
    if (result && result.status === 'success') {
        console.log(`${functionName}: World export reported success. Exported file: ${result.export_file}`);
        showStatusMessage(result.message + " Refreshing list...", 'success');
        setTimeout(() => { window.location.reload(); }, 2000); // Example: Refresh after 2s
    } else if (result === false) {
        console.error(`${functionName}: World export failed (Network/HTTP error or application error reported).`);
    } else {
        console.warn(`${functionName}: World export completed with status: ${result?.status || 'unknown'}`);
    }
}

/**
 * Initiates the world reset process by sending an API request.
 * Assumes 'sendServerActionRequest' is globally available.
 *
 * @param {HTMLElement} buttonElement - The button element that was clicked.
 * @param {string} serverName - The name of the server whose world should be exported.
 */
async function triggerWorldReset(buttonElement, serverName) {
    const functionName = 'triggerWorldReset';
    console.log(`${functionName}: Triggered for server '${serverName}'`);

    // Confirm reset if desired, though it's not destructive like import
    if (!confirm(`WARNING: Reset the current world for server '${serverName}'?`)) {
        console.log(`${functionName}: User cancelled reset.`);
        showStatusMessage("World export cancelled.", "info");
        return;
    }

    console.log(`${functionName}: Sending API request to reset world.`);
    // Call the generic request handler
    // Export endpoint doesn't require a request body (body = null)
    const absoluteActionPath = `/api/server/${serverName}/world/reset`; // Updated for FastAPI prefix
    const result = await sendServerActionRequest(
        null, // serverName is now part of absolute path
        absoluteActionPath,
        'DELETE',
        null,           // No request body needed
        buttonElement
    );

    // Handle specific responses
    if (result && result.status === 'success') {
        console.log(`${functionName}: World reset reported success.`);
    } else if (result === false) {
        console.error(`${functionName}: World reset failed (Network/HTTP error or application error reported).`);
    } else {
        console.warn(`${functionName}: World reset completed with status: ${result?.status || 'unknown'}`);
    }
}


/**
 * Handles the user clicking an 'Install Addon' button.
 * Prompts for confirmation and then calls the API endpoint to install the
 * specified addon file (.mcaddon or .mcpack).
 *
 * @param {HTMLButtonElement} buttonElement - The 'Install' button element that was clicked.
 * @param {string} serverName - The name of the target server.
 * @param {string} addonFilePath - The full path or unique identifier of the addon file
 *                                (as provided by the backend/template).
 */
function triggerAddonInstall(buttonElement, serverName, addonFilePath) {
    const functionName = 'triggerAddonInstall';
    console.log(`${functionName}: Initiated. Server: '${serverName}', File: '${addonFilePath}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Input Validation ---
    if (!addonFilePath || typeof addonFilePath !== 'string' || !addonFilePath.trim()) {
        const errorMsg = "Internal error: Addon file path is missing or invalid.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }
    const trimmedAddonFilePath = addonFilePath.trim();

    // Extract filename for user messages
    const filenameForDisplay = trimmedAddonFilePath.split(/[\\/]/).pop() || trimmedAddonFilePath;
    console.debug(`${functionName}: Extracted filename for display: '${filenameForDisplay}'`);

    // --- Confirmation ---
    console.debug(`${functionName}: Prompting user for addon install confirmation.`);
    // Confirmation message is less severe than world install, but still good practice
    const confirmationMessage = `Install addon '${filenameForDisplay}' for server '${serverName}'?`;
    if (!confirm(confirmationMessage)) {
        console.log(`${functionName}: Addon installation cancelled by user.`);
        showStatusMessage('Addon installation cancelled.', 'info');
        return; // Abort if user cancels
    }
    console.log(`${functionName}: User confirmed addon installation.`);

    // --- Prepare API Request ---
    const requestBody = {
        filename: trimmedAddonFilePath // Send the path/identifier provided by the backend
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Call API Helper ---
    const apiUrl = `/api/server/${serverName}/addon/install`; // Updated for FastAPI prefix
    console.log(`${functionName}: Calling sendServerActionRequest to ${apiUrl}...`);
    sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);

    console.log(`${functionName}: Addon install request initiated (asynchronous).`);
}