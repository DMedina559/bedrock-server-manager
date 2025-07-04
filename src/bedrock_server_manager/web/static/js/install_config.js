// bedrock_server_manager/web/static/js/install_config.js
/**
 * @fileoverview Frontend JavaScript for handling the multi-step server installation
 * and configuration process (Properties, Allowlist, Permissions, Service).
 * Handles form interactions, input validation, API calls, and navigation between steps.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("CRITICAL ERROR: Missing required functions from utils.js. Ensure utils.js is loaded first.");
    // Display a prominent error on the page as core functionality will fail
    const body = document.querySelector('body');
    if (body) {
        const errorDiv = document.createElement('div');
        errorDiv.textContent = "CRITICAL PAGE ERROR: Required JavaScript utilities are missing. Please reload or contact support.";
        errorDiv.style.color = 'red';
        errorDiv.style.fontWeight = 'bold';
        errorDiv.style.padding = '10px';
        errorDiv.style.border = '2px solid red';
        body.insertBefore(errorDiv, body.firstChild);
    }
}

// --- Initialization for Custom Controls ---
document.addEventListener('DOMContentLoaded', () => {
    const functionName = 'DOMContentLoaded';
    console.log(`${functionName}: Initializing custom form controls (segmented, toggles) on config pages.`);

    // --- Segmented Control Initialization ---
    const segmentedControls = document.querySelectorAll('.segmented-control');
    console.debug(`${functionName}: Found ${segmentedControls.length} segmented control wrapper(s).`);
    segmentedControls.forEach((controlWrapper, index) => {
        const linkedInputId = controlWrapper.dataset.inputId;
        const linkedInput = document.getElementById(linkedInputId);
        const segments = controlWrapper.querySelectorAll('.segment');
        console.debug(`${functionName}: Processing segmented control #${index + 1} linked to input '#${linkedInputId}' with ${segments.length} segments.`);

        if (!linkedInput) {
            console.error(`${functionName}: Segmented control #${index + 1} is missing its linked hidden input (ID: ${linkedInputId}). Control will not function.`, controlWrapper);
            // Optionally disable the control visually
            controlWrapper.style.opacity = '0.5';
            controlWrapper.style.pointerEvents = 'none';
            return; // Skip initialization for this control
        }

        segments.forEach(segment => {
            segment.addEventListener('click', (event) => {
                event.preventDefault();
                const clickedSegment = event.currentTarget;
                const newValue = clickedSegment.dataset.value;
                console.log(`${functionName}: Segment clicked! Control: '${linkedInputId}', New Value: '${newValue}'`);

                // Update hidden input
                linkedInput.value = newValue;
                console.debug(`${functionName}: Set hidden input '#${linkedInputId}' value to '${newValue}'.`);

                // Update active segment visually
                segments.forEach(s => s.classList.remove('active'));
                clickedSegment.classList.add('active');
                console.debug(`${functionName}: Updated active class for segment with value '${newValue}'.`);

                // Optional: Dispatch 'change' for reactivity elsewhere
                // linkedInput.dispatchEvent(new Event('change', { bubbles: true }));
            });
        });
        console.debug(`${functionName}: Event listeners added for segmented control #${index + 1}.`);
    });

    // --- Toggle Switch Initialization ---
    const toggleInputs = document.querySelectorAll('.toggle-input');
    console.debug(`${functionName}: Found ${toggleInputs.length} toggle switch input(s).`);
    toggleInputs.forEach((input, index) => {
        const baseName = input.name.replace('-cb', '');
        // Use optional chaining for safety in case structure is unexpected
        const hiddenFalseInput = input.closest('.form-group-toggle-container')?.querySelector(`.toggle-hidden-false[name="${baseName}"]`);
        console.debug(`${functionName}: Processing toggle #${index + 1} (Name: ${input.name}). Base name inferred: '${baseName}'.`);

        if (!hiddenFalseInput) {
            console.warn(`${functionName}: Could not find associated hidden 'false' input for toggle '${input.name}'. State syncing might be affected.`);
        }

        const syncHiddenFalse = () => {
            if (hiddenFalseInput) {
                // Hidden input for 'false' should be DISABLED when the checkbox is CHECKED (so only 'true' is sent)
                // It should be ENABLED when the checkbox is UNCHECKED (so 'false' is sent)
                hiddenFalseInput.disabled = input.checked;
                console.debug(`${functionName}: Synced toggle '${input.name}' state. Checkbox checked: ${input.checked}, Hidden input '${hiddenFalseInput.name}' disabled: ${hiddenFalseInput.disabled}.`);
            }
        };

        input.addEventListener('change', syncHiddenFalse);
        syncHiddenFalse(); // Initial sync on page load
        console.debug(`${functionName}: Event listener added and initial state synced for toggle #${index + 1}.`);
    });

    console.log(`${functionName}: Custom form control initialization complete.`);
});


// --- Action Functions ---

/**
 * Initiates the server installation process by calling the API.
 * Handles the confirmation step if the server directory already exists and overwrite is needed.
 * Navigates to the first configuration step (properties) upon successful installation.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement - The install button element.
 */
async function triggerInstallServer(buttonElement) {
    const functionName = 'triggerInstallServer';
    console.log(`${functionName}: Initiated.`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Get and Validate Inputs ---
    const serverNameInput = document.getElementById('install-server-name');
    const serverVersionInput = document.getElementById('install-server-version');

    if (!serverNameInput || !serverVersionInput) {
        const errorMsg = "Internal page error: Required input fields ('install-server-name', 'install-server-version') not found.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        return;
    }

    const serverName = serverNameInput.value.trim();
    const serverVersion = serverVersionInput.value.trim() || 'LATEST'; // Default to LATEST if empty

    console.log(`${functionName}: User Input - Server Name: "${serverName}", Version: "${serverVersion}"`);

    // Basic frontend validation
    if (!serverName) { return showStatusMessage('Server name cannot be empty.', 'warning'); }
    if (!serverVersion) { return showStatusMessage('Server version cannot be empty (use LATEST or PREVIEW if unsure).', 'warning'); }
    // Basic check for problematic characters (more robust validation happens server-side)
    const invalidChars = /[\\/;:&|<>*?"]/; // Added more potentially problematic chars
    if (invalidChars.test(serverName)) {
        return showStatusMessage('Server name contains invalid characters. Use only letters, numbers, hyphens, underscores.', 'error');
    }
    console.debug(`${functionName}: Frontend input validation passed.`);

    // Clear previous validation errors display
    _clearValidationErrors();

    // --- Initial API Call (overwrite: false) ---
    const initialRequestBody = {
        server_name: serverName,
        server_version: serverVersion,
        overwrite: false
    };
    console.debug(`${functionName}: Constructing initial request body:`, initialRequestBody);
    const apiUrl = '/api/server/install';
    console.log(`${functionName}: Sending initial install request to ${apiUrl}...`);

    // Disable button immediately
    if (buttonElement) buttonElement.disabled = true;

    const initialApiResponse = await sendServerActionRequest(null, apiUrl, 'POST', initialRequestBody, buttonElement);
    console.log(`${functionName}: Initial install API response received:`, initialApiResponse);

    // --- Handle Response (Confirmation, Success, Error) ---
    if (initialApiResponse === false) {
        console.error(`${functionName}: Initial install API call failed (HTTP/Network error or returned false).`);
        // Message shown by sendServerActionRequest, button re-enabled by its finally block
        return;
    }

    if (initialApiResponse.status === 'confirm_needed') {
        console.info(`${functionName}: Server exists, confirmation needed for overwrite.`);
        // --- User Interaction: Confirmation Dialog ---
        const confirmMsg = initialApiResponse.message || `Server '${serverName}' already exists. Overwrite all data? THIS CANNOT BE UNDONE!`;
        if (confirm(confirmMsg)) {
             // User confirmed overwrite
             console.log(`${functionName}: Overwrite confirmed by user. Sending second request...`);
             showStatusMessage("Overwrite confirmed. Re-attempting installation...", "info");
             const overwriteRequestBody = { ...initialRequestBody, overwrite: true }; // Copy initial body and set overwrite to true
             console.debug(`${functionName}: Constructing overwrite request body:`, overwriteRequestBody);

             // --- Second API Call (overwrite: true) ---
             const finalApiResponse = await sendServerActionRequest(null, apiUrl, 'POST', overwriteRequestBody, buttonElement);
             console.log(`${functionName}: Overwrite install API response received:`, finalApiResponse);

             if (finalApiResponse && finalApiResponse.status === 'success') {
                  // Overwrite successful -> Navigate
                  _handleInstallSuccessNavigation(finalApiResponse);
             } else {
                  console.error(`${functionName}: Overwrite install failed. Final API response:`, finalApiResponse);
                  // Error message shown by sendServerActionRequest
             }
        } else {
             // User cancelled overwrite
             console.log(`${functionName}: Overwrite cancelled by user.`);
             showStatusMessage("Installation cancelled (overwrite not confirmed).", "info");
             if (buttonElement) buttonElement.disabled = false; // Re-enable button if confirmation cancelled
        }
    } else if (initialApiResponse.status === 'success') {
         // --- Direct Success (New Install) ---
         console.log(`${functionName}: New server install successful.`);
         _handleInstallSuccessNavigation(initialApiResponse);
    } else {
         // --- Other Errors from Initial Call ---
         console.error(`${functionName}: Initial install attempt failed. Status: ${initialApiResponse.status}, Message: ${initialApiResponse.message}`);
         // Error message shown by sendServerActionRequest
    }
    console.log(`${functionName}: Execution finished.`);
}

/**
 * Helper function to handle navigation after successful server installation.
 * @param {object} apiResponseData - The successful API response data containing 'next_step_url'.
 */
function _handleInstallSuccessNavigation(apiResponseData) {
    const functionName = '_handleInstallSuccessNavigation';
    console.log(`${functionName}: Handling successful install response.`);
    console.debug(`${functionName}: Response data:`, apiResponseData);

    const nextUrl = apiResponseData?.next_step_url;
    const message = apiResponseData?.message || "Server installed successfully!";

    if (nextUrl) {
        console.log(`${functionName}: Found next_step_url: ${nextUrl}. Navigating after delay...`);
        showStatusMessage(`${message} Proceeding to configuration...`, "success");
        setTimeout(() => {
            console.log(`${functionName}: Navigating to ${nextUrl}`);
            window.location.href = nextUrl;
        }, 1500); // Delay for user to see message
    } else {
        // Success, but no next URL provided (shouldn't happen ideally)
        const warnMsg = "Server installed successfully, but next configuration step URL was missing in response.";
        console.warn(`${functionName}: ${warnMsg}`);
        showStatusMessage(warnMsg, "warning");
        // Button should be re-enabled by sendServerActionRequest's finally block in this case
    }
}

/**
 * Clears validation error messages from the form.
 */
function _clearValidationErrors() {
    const functionName = '_clearValidationErrors';
    console.debug(`${functionName}: Clearing validation messages.`);
    // Clear general error area
    const generalErrorArea = document.getElementById('validation-error-area');
    if (generalErrorArea) {
        generalErrorArea.textContent = '';
        generalErrorArea.innerHTML = ''; // Clear potential HTML too
        generalErrorArea.style.display = 'none';
    }
    // Clear specific field errors
    document.querySelectorAll('.validation-error').forEach(el => {
        el.textContent = ''; // Clear text content
    });
     console.debug(`${functionName}: Validation messages cleared.`);
}


/**
 * Gathers data from the server properties configuration form, including handling
 * custom controls like segmented buttons and toggle switches, then sends the data
 * to the API to update `server.properties`. Handles navigation if part of a new install.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement - The save button element.
 * @param {string} serverName - The name of the server being configured.
 * @param {boolean} isNewInstall - Flag indicating if this is part of the new server setup.
 */
async function saveProperties(buttonElement, serverName, isNewInstall) {
    const functionName = 'saveProperties';
    console.log(`${functionName}: Initiated. Server: ${serverName}, NewInstall: ${isNewInstall}`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Gather Form Data ---
    const propertiesData = {};
    // Query elements within the specific config section
    const formElements = document.querySelectorAll('.properties-config-section .form-input, .properties-config-section .toggle-input, .properties-config-section input[type="hidden"]');
    console.debug(`${functionName}: Found ${formElements.length} potential form elements.`);

    formElements.forEach(element => {
        const name = element.getAttribute('name');
        if (!name) return; // Skip unnamed elements

        if (element.type === 'checkbox' && element.classList.contains('toggle-input')) {
             // For toggles, only send 'true' if checked. The hidden input handles 'false'.
            if (element.checked) {
                const baseName = name.replace('-cb', ''); // Use base name
                propertiesData[baseName] = 'true';
                 console.debug(`${functionName}: Gathered toggle '${baseName}' = true (from checkbox)`);
            }
             // 'false' value comes from the corresponding hidden input when it's *not* disabled
        } else if (element.type === 'hidden') {
            // Only include hidden inputs if they are ENABLED
            if (!element.disabled) {
                 propertiesData[name] = element.value;
                 console.debug(`${functionName}: Gathered enabled hidden input '${name}' = '${element.value}'`);
            } else {
                 console.debug(`${functionName}: Skipped disabled hidden input '${name}' (likely toggle false value)`);
            }
        } else if (element.tagName === 'SELECT' || element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
             // Standard inputs (excluding the toggle checkbox itself)
             if (!element.classList.contains('toggle-input')) { // Avoid double-adding toggle state
                  propertiesData[name] = element.value;
                  console.debug(`${functionName}: Gathered input/select/textarea '${name}' = '${element.value}'`);
             }
        }
    });

    console.log(`${functionName}: Properties data gathered for submission:`, propertiesData);

    // --- Clear Previous Validation Errors ---
    _clearValidationErrors();

    // --- Send API Request ---
    const apiUrl = `/api/server/${serverName}/properties/set`;
    console.log(`${functionName}: Calling sendServerActionRequest to save properties at ${apiUrl}...`);

    const payload = { properties: propertiesData };
    const apiResponseData = await sendServerActionRequest(null, apiUrl, 'POST', payload, buttonElement);
    console.log(`${functionName}: Save properties API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    if (apiResponseData && apiResponseData.status === 'success') {
        console.log(`${functionName}: Properties save API call reported success.`);
        const successMsg = apiResponseData.message || "Properties saved successfully.";

        if (isNewInstall) {
             console.log(`${functionName}: Properties saved during new install. Navigating to allowlist config...`);
             showStatusMessage(`${successMsg} Proceeding to Allowlist...`, "success");
             setTimeout(() => {
                 const nextUrl = `/server/${encodeURIComponent(serverName)}/configure_allowlist?new_install=True`; // Ensure server name is URL-safe
                 console.log(`${functionName}: Navigating to ${nextUrl}`);
                 window.location.href = nextUrl;
             }, 1500);
        } else {
             console.log(`${functionName}: Properties saved successfully (standard configuration).`);
             showStatusMessage(successMsg, "success"); // Show success message from API
        }
    } else {
        console.error(`${functionName}: Properties save failed or had validation errors.`);
        // Validation/error messages handled by sendServerActionRequest, including displaying errors
    }
    console.log(`${functionName}: Execution finished.`);
}

/**
 * Gathers player permission levels from the form's select elements and saves them via API.
 * Uses a PUT request, implying replacement of permissions for the submitted players.
 * Handles navigation if part of a new server installation sequence.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement - The save button element.
 * @param {string} serverName - The name of the server being configured.
 * @param {boolean} isNewInstall - Flag indicating if part of the new server setup.
 */
async function savePermissions(buttonElement, serverName, isNewInstall) {
    const functionName = 'savePermissions';
    console.log(`${functionName}: Initiated. Server: ${serverName}, NewInstall: ${isNewInstall}`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Gather Permissions Data ---
    const permissionsData = []; // Array of {xuid, name, permission_level} objects
    const permissionSelects = document.querySelectorAll('select.permission-select'); // Target selects by class
    console.debug(`${functionName}: Found ${permissionSelects.length} permission select elements.`);

    permissionSelects.forEach(select => {
        const xuid = select.dataset.xuid;
        const selectedLevel = select.value;
        
        // Traverse up to the table row (tr) to find the player-name cell
        const tableRow = select.closest('tr');
        let playerName = 'Unknown'; // Default name
        if (tableRow) {
            const nameCell = tableRow.querySelector('.player-name');
            if (nameCell) {
                playerName = nameCell.textContent.trim();
            } else {
                console.warn(`${functionName}: Could not find '.player-name' cell in row for XUID: ${xuid}.`, tableRow);
            }
        } else {
            console.warn(`${functionName}: Could not find parent 'tr' for select element with XUID: ${xuid}.`, select);
        }

        if (xuid && selectedLevel && playerName) {
            permissionsData.push({
                xuid: xuid,
                name: playerName, // Include the player's name
                permission_level: selectedLevel // Keep key as permission_level for consistency with GET response
            });
            console.debug(`${functionName}: Gathered permission - XUID: ${xuid}, Name: ${playerName}, Level: '${selectedLevel}'`);
        } else {
            console.warn(`${functionName}: Skipping select element due to missing data (XUID: ${xuid}, Name: ${playerName}, Level: ${selectedLevel}).`, select);
        }
    });

    console.log(`${functionName}: Permissions data array gathered for submission:`, permissionsData);

    // --- Clear Validation ---
    _clearValidationErrors(); // Clear any previous errors

    // --- Prepare API Request ---
    const requestBody = {
        permissions: permissionsData // Send the array of objects
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Send API Request (Using PUT) ---
    const apiUrl = `/api/server/${serverName}/permissions/set`;
    console.log(`${functionName}: Calling sendServerActionRequest to save permissions at ${apiUrl} (PUT)...`);

    const apiResponseData = await sendServerActionRequest(null, apiUrl, 'PUT', requestBody, buttonElement);
    console.log(`${functionName}: Save permissions API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    if (apiResponseData && apiResponseData.status === 'success') {
        console.log(`${functionName}: Permissions save API call reported success.`);
        const successMsg = apiResponseData.message || "Permissions saved successfully.";

        if (isNewInstall) {
             console.log(`${functionName}: Permissions saved during new install. Navigating to service config...`);
             showStatusMessage(`${successMsg} Proceeding to Service Configuration...`, "success");
             setTimeout(() => {
                 const nextUrl = `/server/${encodeURIComponent(serverName)}/configure_service?new_install=True`;
                 console.log(`${functionName}: Navigating to ${nextUrl}`);
                 window.location.href = nextUrl;
             }, 1500);
        } else {
             console.log(`${functionName}: Permissions saved successfully (standard configuration).`);
             showStatusMessage(successMsg, "success");
        }
    } else {
        console.error(`${functionName}: Permissions save failed or had validation errors.`);
        // Validation/error messages (including individual player errors if API provides them) handled by sendServerActionRequest
    }
    console.log(`${functionName}: Execution finished.`);
}


/**
 * Gathers OS-specific service settings (autoupdate, autostart) from the form
 * and saves them via the API. Handles the optional final step of starting the
 * server and navigating to the dashboard if part of a new install sequence.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement - The save button element.
 * @param {string} serverName - The name of the server being configured.
 * @param {string} currentOs - The detected operating system ('Linux', 'Windows', etc.).
 * @param {boolean} isNewInstall - Flag indicating if part of the new server setup.
 */
async function saveServiceSettings(buttonElement, serverName, currentOs, isNewInstall) {
    const functionName = 'saveServiceSettings';
    console.log(`${functionName}: Initiated. Server: ${serverName}, OS: ${currentOs}, NewInstall: ${isNewInstall}`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Gather Settings ---
    const requestBody = {};
    let startServerAfter = false; // Flag for final step in new install

    const configSection = document.querySelector('.service-config-section');
    if (!configSection) {
         const errorMsg = "Internal page error: Service configuration section not found.";
         console.error(`${functionName}: ${errorMsg}`);
         showStatusMessage(errorMsg, "error");
         return;
    }

    try { // Wrap gathering in try-catch in case querySelector fails unexpectedly
        const autoupdateCheckbox = configSection.querySelector('#service-autoupdate-cb'); // The .toggle-input checkbox
        if (autoupdateCheckbox) {
            requestBody.autoupdate = autoupdateCheckbox.checked; // Boolean value
        } else {
             console.warn(`${functionName}: Autoupdate checkbox (#service-autoupdate-cb) not found.`);
             // Decide default? Or fail? Let's proceed without it for now.
        }

        if (currentOs === 'Linux' || currentOs === 'Windows') {
            const autostartCheckbox = configSection.querySelector('#service-autostart-cb'); // The .toggle-input checkbox
            if (autostartCheckbox) {
                requestBody.autostart = autostartCheckbox.checked; // Boolean value
            } else {
                 console.warn(`${functionName}: Autostart checkbox (#service-autostart-cb) not found.`);
            }
            console.debug(`${functionName}: Settings gathered:`, requestBody);
        } else {
             const errorMsg = `Unsupported OS '${currentOs}' for service configuration.`;
             console.error(`${functionName}: ${errorMsg}`);
             showStatusMessage(errorMsg, "error");
             return; // Cannot proceed
        }

        if (isNewInstall) {
            const startServerCheckbox = configSection.querySelector('#service-start-server'); // The .toggle-input
            startServerAfter = startServerCheckbox ? startServerCheckbox.checked : false;
            console.debug(`${functionName}: New install workflow. Start server after save: ${startServerAfter}`);
        }

    } catch (gatherError) {
        const errorMsg = `Error gathering settings from form: ${gatherError.message}`;
        console.error(`${functionName}: ${errorMsg}`, gatherError);
        showStatusMessage(errorMsg, "error");
        return;
    }

    console.log(`${functionName}: Final request body for service settings:`, requestBody);

    // --- Clear Validation ---
    _clearValidationErrors(); // Clear any potential previous errors

    // --- Call API to Save Settings ---
    const apiUrl = `/api/server/${serverName}/service/update`;
    console.log(`${functionName}: Calling sendServerActionRequest to save service settings at ${apiUrl}...`);

    const saveResponse = await sendServerActionRequest(null, apiUrl, 'POST', requestBody, buttonElement);
    console.log(`${functionName}: Save service settings API call finished. Response data:`, saveResponse);

    if (!saveResponse || saveResponse.status !== 'success') {
        console.error(`${functionName}: Saving service settings failed. API response indicated failure or error.`);
        // Error message shown by sendServerActionRequest
        return; // Stop the workflow if saving settings failed
    }

    // --- Handle Post-Save Actions (Start Server / Navigate) ---
    const saveSuccessMsg = saveResponse.message || "Service settings saved successfully.";
    console.info(`${functionName}: Service settings saved successfully for server '${serverName}'.`);

    if (startServerAfter) {
        console.log(`${functionName}: Service settings saved. Proceeding to start server '${serverName}' as requested...`);
        showStatusMessage(`${saveSuccessMsg} Attempting to start server...`, "info");

        const startButton = document.getElementById('start-server-btn'); // Attempt to find start button if exists on page
        const startResponse = await sendServerActionRequest(serverName, 'start', 'POST', null, startButton);
        console.log(`${functionName}: Start server API call finished. Response data:`, startResponse);

        if (startResponse && startResponse.status === 'success') {
            console.log(`${functionName}: Server start successful after configuration.`);
            if (isNewInstall) {
                showStatusMessage("Server started! Installation complete. Redirecting to dashboard...", "success");
                setTimeout(() => {
                    console.log(`${functionName}: Redirecting to dashboard ('/').`);
                    window.location.href = "/";
                }, 2000); // Longer delay after start
            } else {
                 showStatusMessage(startResponse.message || "Server started successfully.", "success");
            }
        } else {
             // Start failed
             const startErrorMsg = startResponse?.message || "Unknown error starting server.";
             console.warn(`${functionName}: Server failed to start after saving service settings: ${startErrorMsg}`);
             showStatusMessage(`Service settings saved, but server failed to start: ${startErrorMsg}`, "warning");
             // Button re-enabling handled by sendServerActionRequest
             // If it's a new install, maybe don't redirect? Let user see error.
             if (isNewInstall) {
                 console.log(`${functionName}: Staying on page due to server start failure during new install.`);
             }
        }
    } else if (isNewInstall) {
        // New install, saved settings, but didn't request start
        console.log(`${functionName}: Service settings saved. New install complete (server not started). Redirecting to dashboard...`);
        showStatusMessage(`${saveSuccessMsg} Installation complete! Redirecting to dashboard...`, "success");
        setTimeout(() => {
            console.log(`${functionName}: Redirecting to dashboard ('/').`);
            window.location.href = "/";
        }, 1500);
    } else {
         // Standard save, not new install, didn't request start
         console.log(`${functionName}: Service settings saved successfully (standard configuration).`);
         showStatusMessage(saveSuccessMsg, "success");
         // Button re-enabling handled by sendServerActionRequest
    }
    console.log(`${functionName}: Execution finished.`);
}