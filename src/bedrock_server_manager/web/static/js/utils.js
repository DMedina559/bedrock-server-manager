// bedrock_server_manager/web/static/js/utils.js
/**
 * @fileoverview Utility functions for the Bedrock Server Manager web interface,
 * including status message display and asynchronous API request handling.
 */

// --- Helper: Display Status Messages ---
/**
 * Displays a status message dynamically in a designated area on the page.
 * The message automatically fades out and clears after a set duration.
 * Handles cases where the status area element might be missing.
 *
 * @param {string} message - The text content of the message to display.
 * @param {string} [type='info'] - The type of message, influencing styling.
 *                                 Expected values: 'info', 'success', 'warning', 'error'.
 */
function showStatusMessage(message, type = 'info') {
    const functionName = 'showStatusMessage';
    console.log(`${functionName}: Displaying message (Type: ${type}): "${message}"`);

    const area = document.getElementById('status-message-area');
    if (!area) {
        console.warn(`${functionName}: Element '#status-message-area' not found. Falling back to standard alert.`);
        alert(`${type.toUpperCase()}: ${message}`); // Fallback for critical messages if area missing
        return;
    }

    // Assign classes for styling and set text content
    // Using template literal for cleaner class string construction
    area.className = `message-box message-${type}`;
    area.textContent = message;
    area.style.transition = ''; // Clear previous transitions immediately
    area.style.opacity = '1';   // Make visible instantly

    // Use a unique identifier for the timeout related to *this specific message*
    // This helps prevent race conditions if messages are shown in quick succession.
    const messageId = Date.now() + Math.random(); // Simple unique ID
    area.dataset.currentMessageId = messageId; // Store ID on the element

    console.debug(`${functionName}: Set message content and visibility for messageId ${messageId}.`);

    // Set timeout to fade out and clear the message
    setTimeout(() => {
        // Check if the message currently displayed *still* corresponds to this timeout call
        if (area.dataset.currentMessageId === String(messageId)) {
            console.debug(`${functionName}: Initiating fade-out for messageId ${messageId} ("${message}").`);
            area.style.transition = 'opacity 0.5s ease-out';
            area.style.opacity = '0';

            // Set another timeout to clear content *after* fade completes
            setTimeout(() => {
                // Final check: Only clear if it's still the same message and it faded out
                if (area.dataset.currentMessageId === String(messageId) && area.style.opacity === '0') {
                    console.debug(`${functionName}: Clearing content for messageId ${messageId} after fade.`);
                    area.textContent = '';
                    area.className = 'message-box'; // Reset styles
                    area.style.transition = ''; // Remove transition property
                    delete area.dataset.currentMessageId; // Clean up dataset attribute
                } else {
                    console.debug(`${functionName}: Aborting final clear for messageId ${messageId} - message changed or fade interrupted.`);
                }
            }, 500); // Match fade duration (500ms)
        } else {
            console.debug(`${functionName}: Aborting fade-out for messageId ${messageId} - a newer message was displayed.`);
        }
    }, 5000); // Start fade-out after 5 seconds
}


// --- Helper: Send API Request ---
/**
 * Sends an asynchronous request (using Fetch API) to a server API endpoint.
 * Handles common tasks like setting headers (Accept, Content-Type, CSRF),
 * managing JSON request/response bodies, displaying status messages,
 * handling HTTP errors, parsing application-level success/error statuses,
 * and optionally disabling/re-enabling a button element during the request.
 *
 * @async
 * @param {string|null} serverName - The name of the target server. Use `null` or empty string
 *                                   if `actionPath` is an absolute path (starts with '/').
 * @param {string} actionPath - The API endpoint path. If it starts with '/', it's treated as
 *                             absolute. Otherwise, it's appended to `/api/server/{serverName}/`.
 * @param {string} [method='POST'] - The HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
 * @param {object|null} [body=null] - Optional JavaScript object to send as the JSON request body.
 *                                    Ignored for methods like 'GET'.
 * @param {HTMLElement|null} [buttonElement=null] - Optional button element to disable while the request is pending.
 * @param {boolean} [suppressSuccessPopup=false] - Optional. If true, success messages will not be shown via showStatusMessage.
 * @returns {Promise<object|false>} A promise that resolves with:
 *                                  - The parsed JSON response data object if the HTTP request was successful (status 2xx)
 *                                    and the response was valid JSON or 204 No Content. The caller *must* check the
 *                                    `status` field within this object (`responseData.status === 'success'`) to confirm
 *                                    the *application-level* success of the action.
 *                                  - `false` if the fetch request itself failed (network error, CORS issue, DNS error),
 *                                    if the CSRF token was missing, if URL construction failed, or if an HTTP error
 *                                    status (non-2xx) was received.
 * @throws {Error} Can throw errors if JSON parsing fails unexpectedly on a response claiming to be JSON,
 *                 though attempts are made to handle this gracefully.
 */
async function sendServerActionRequest(serverName, actionPath, method = 'POST', body = null, buttonElement = null, suppressSuccessPopup = false) {
    const functionName = 'sendServerActionRequest';
    // Use console.debug for potentially verbose parameter logging
    console.debug(`${functionName}: Initiating request - Server: '${serverName || 'N/A'}', Path: '${actionPath}', Method: ${method}, SuppressSuccess: ${suppressSuccessPopup}`);
    if (body) console.debug(`${functionName}: Request Body:`, body); // Log body only if present
    if (buttonElement) console.debug(`${functionName}: Associated Button:`, buttonElement);

    // --- 2. Construct URL ---
    let apiUrl;
    if (actionPath.startsWith('/')) {
        apiUrl = actionPath; // Use as absolute path
        console.debug(`${functionName}: Using absolute URL: ${apiUrl}`);
    } else if (serverName && serverName.trim()) { // Check serverName is not empty/whitespace
        apiUrl = `/api/server/${serverName}/${actionPath}`; // Construct relative path
        console.debug(`${functionName}: Using relative URL for server '${serverName}': ${apiUrl}`);
    } else {
        const errorMsg = "Invalid arguments: 'serverName' is required for relative action paths.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(errorMsg, "error");
        if (buttonElement) buttonElement.disabled = false;
        return false; // Critical configuration failure
    }

    // --- 3. Prepare Fetch Request ---
    console.debug(`${functionName}: Preparing fetch request to ${apiUrl} (Method: ${method})`);
    if (buttonElement) {
        console.debug(`${functionName}: Disabling button.`);
        buttonElement.disabled = true;
    }
    // Show initial user feedback immediately
    if (!suppressSuccessPopup) {
        showStatusMessage(`Processing action at ${apiUrl}...`, 'info');
    }

    const fetchOptions = {
        method: method.toUpperCase(), // Ensure method is uppercase
        headers: {
            'Accept': 'application/json', // We always want JSON back
        }
    };

    // Add JWT to headers if available
    const jwtToken = localStorage.getItem('jwt_token');
    if (jwtToken) {
        fetchOptions.headers['Authorization'] = `Bearer ${jwtToken}`;
        console.debug(`${functionName}: Added JWT to Authorization header.`);
    } else {
        console.debug(`${functionName}: No JWT found in localStorage.`);
    }
    // CSRF header removed earlier

    // Add body and Content-Type header if applicable
    const methodAllowsBody = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(fetchOptions.method);
    if (body && methodAllowsBody) {
        try {
            fetchOptions.body = JSON.stringify(body);
            fetchOptions.headers['Content-Type'] = 'application/json';
            console.debug(`${functionName}: Added JSON body and Content-Type header.`);
        } catch (stringifyError) {
            const errorMsg = `Failed to stringify request body: ${stringifyError.message}`;
            console.error(`${functionName}: ${errorMsg}`, body);
            showStatusMessage(errorMsg, "error");
            if (buttonElement) buttonElement.disabled = false;
            return false; // Cannot proceed if body cannot be stringified
        }
    } else if (body && !methodAllowsBody) {
        console.warn(`${functionName}: Body provided for HTTP method '${fetchOptions.method}' which typically does not support it. Body ignored.`);
    } else {
        console.debug(`${functionName}: No request body provided or method does not support it.`);
    }

    // --- 4. Execute Fetch Request and Process Response ---
    let responseData = null; // To store parsed JSON response
    let httpSuccess = false; // Track if HTTP status code was 2xx

    try {
        console.debug(`${functionName}: Executing fetch(${apiUrl}, ...)`);
        const response = await fetch(apiUrl, fetchOptions);
        console.log(`${functionName}: Response received - Status: ${response.status}, OK: ${response.ok}`);
        httpSuccess = response.ok; // ok is true for statuses in the range 200-299

        // --- Process Body based on Status and Content-Type ---
        if (response.status === 204) { // Handle No Content explicitly
            console.log(`${functionName}: Received 204 No Content. Treating as success.`);
            responseData = { status: 'success', message: `Action at ${apiUrl} successful (No Content).` };
            // httpSuccess is already true
        } else {
            // Try to read body (JSON preferred, fallback to text)
            const contentType = response.headers.get('content-type');
            console.debug(`${functionName}: Response Content-Type: ${contentType}`);
            if (contentType && contentType.includes('application/json')) {
                console.debug(`${functionName}: Parsing JSON response body...`);
                responseData = await response.json(); // Can throw error if invalid JSON
                console.debug(`${functionName}: Parsed JSON response:`, responseData);
            } else {
                // Not JSON - read as text and handle based on HTTP status
                console.debug(`${functionName}: Response not JSON. Reading as text...`);
                const textResponse = await response.text();
                console.warn(`${functionName}: Received non-JSON response (Status: ${response.status}). Body (truncated): ${textResponse.substring(0, 500)}`);
                if (!httpSuccess) { // If HTTP status indicated error (non-2xx)
                    // Construct an error object from the text response
                    responseData = {
                        status: 'error',
                        message: `Request failed (Status ${response.status}): ${textResponse.substring(0, 200)}${textResponse.length > 200 ? '...' : ''}`
                    };
                    console.debug(`${functionName}: Created error object from text response.`);
                } else {
                    // HTTP status was 2xx, but body wasn't JSON/204 - this is unexpected
                    const warnMsg = `Request to ${apiUrl} succeeded (Status ${response.status}) but returned unexpected content type: ${contentType}. Check server logs.`;
                    console.warn(`${functionName}: ${warnMsg}`);
                    showStatusMessage(warnMsg, 'warning');
                    // Return false to indicate API contract violation, even though HTTP was ok.
                    // Button is re-enabled in finally block for this case.
                    return false;
                }
            }
        }

        // --- 5. Handle Response Based on HTTP Status ---
        if (!httpSuccess) {
            // Process HTTP errors (4xx, 5xx)
            const errorMessage = responseData?.message || `Request failed with status ${response.status}`;
            console.error(`${functionName}: HTTP Error - Status: ${response.status}, Message: "${errorMessage}"`);

            // Specific handling for validation errors (400 with 'errors' object)
            if (response.status === 400 && responseData?.errors && typeof responseData.errors === 'object') {
                showStatusMessage(errorMessage || "Validation failed. Please check fields.", "error");
                // Display field-specific errors (assuming helper elements exist)
                const errorArea = document.getElementById('validation-error-area');
                let generalErrors = [];
                Object.entries(responseData.errors).forEach(([field, msg]) => {
                    const fieldErrorEl = document.querySelector(`.validation-error[data-field="${field}"]`);
                    if (fieldErrorEl) { fieldErrorEl.textContent = msg; }
                    else { generalErrors.push(`<strong>${field}:</strong> ${msg}`); }
                });
                if (errorArea && generalErrors.length > 0) { errorArea.innerHTML = generalErrors.join('<br>'); }
            }
            // Specific handling for CSRF error (often 400 with specific message from Flask-WTF)
            else if (response.status === 400 && errorMessage.toLowerCase().includes("csrf token")) {
                const csrfErrorMsg = "Security token error. Please refresh the page and try again.";
                console.error(`${functionName}: CSRF Token Error detected.`);
                showStatusMessage(csrfErrorMsg, "error");
            }
            else {
                // Show generic error message for other HTTP errors
                showStatusMessage(errorMessage, "error");
            }
            // Return false as the HTTP request failed
            return false;
        } else {
            // --- 6. Handle Application-Level Status in SUCCESSFUL (2xx) HTTP Responses ---
            console.debug(`${functionName}: HTTP request successful (Status: ${response.status}). Checking application status in response...`);
            // Check 'status' field within the JSON response data
            if (responseData && responseData.status === 'success') {
                const successMsg = responseData.message || `Action at ${apiUrl} completed successfully.`;
                console.info(`${functionName}: Application success. Message: "${successMsg}"`);
                if (!suppressSuccessPopup) { // Only show popup if not suppressed
                    showStatusMessage(successMsg, 'success');
                }
                // Optionally trigger UI updates based on success here if needed
            } else if (responseData && responseData.status === 'confirm_needed') {
                // Special status - let the caller handle confirmation logic
                console.info(`${functionName}: Application status 'confirm_needed'. Returning data for confirmation handling.`);
                // Message usually shown by caller based on responseData.message
                // Button is handled in finally block (remains disabled)
            } else {
                // HTTP success (2xx), but application status is 'error' or missing/unexpected
                const appStatus = responseData?.status || 'unknown';
                const appMessage = responseData?.message || `Action at ${apiUrl} reported status: ${appStatus}.`;
                console.warn(`${functionName}: HTTP success but application status is '${appStatus}'. Message: ${appMessage}`);
                showStatusMessage(appMessage, 'warning'); // Use warning or error depending on severity preference
            }
        }

    } catch (error) { // Catch network errors, CORS, DNS, unexpected JSON parse errors
        const errorMsg = `Network or processing error during action at ${apiUrl}: ${error.message}`;
        console.error(`${functionName}: Fetch failed - ${errorMsg}`, error);
        showStatusMessage(errorMsg, 'error');
        // Ensure button is re-enabled if an error occurs before finally might run reliably
        if (buttonElement) buttonElement.disabled = false;
        return false; // Indicate failure
    } finally {
        // --- 7. Final Button Re-enabling Logic ---
        // Re-enable the button unless the operation requires confirmation ('confirm_needed')
        console.debug(`${functionName}: Finally block executing. httpSuccess=${httpSuccess}, responseData.status=${responseData?.status}`);
        if (buttonElement) { // Only if a button was provided
            if (responseData?.status !== 'confirm_needed') {
                if (buttonElement.disabled) {
                    console.debug(`${functionName}: Re-enabling button in finally block.`);
                    buttonElement.disabled = false;
                } else {
                    console.debug(`${functionName}: Button was already enabled in finally block.`);
                }
            } else {
                console.debug(`${functionName}: Button remains disabled due to 'confirm_needed' status.`);
            }
        }
    }

    // Log the final data object being returned to the caller
    console.debug(`${functionName}: Returning response data object (or false if HTTP error occurred):`, responseData);
    // Return the parsed data object if HTTP was successful (caller checks internal status),
    // otherwise return false (already returned within error handling blocks).
    return httpSuccess ? responseData : false;
}
