// bedrock_server_manager/web/static/js/allowlist.js
/**
 * @fileoverview Frontend JavaScript for managing the server allowlist.
 * Handles user input, interacts with the allowlist API endpoints, and updates the UI.
 * Depends on functions defined in utils.js (showStatusMessage, sendServerActionRequest).
 */

// Ensure utils.js is loaded before this script
if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first.");
}

/**
 * Gathers player names from the 'add players' textarea, validates them,
 * and sends a request to the API endpoint responsible for **adding** these
 * players to the existing allowlist. Refreshes the displayed allowlist on success.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement - The 'Add Players' button element.
 * @param {string} serverName - The name of the server.
 */
async function addAllowlistPlayers(buttonElement, serverName) {
    const functionName = 'addAllowlistPlayers';
    console.log(`${functionName}: Initiated. Server: ${serverName}`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    // --- Get DOM Elements ---
    const textArea = document.getElementById('player-names-add'); // Specific textarea for adding
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-add'); // Specific checkbox

    if (!textArea || !ignoreLimitCheckbox) {
        const errorMsg = "Required 'add player' form elements ('player-names-add', 'ignore-limit-add') not found.";
        console.error(`${functionName}: ${errorMsg}`);
        showStatusMessage(`Internal page error: ${errorMsg}`, "error");
        return;
    }
    console.debug(`${functionName}: Found 'add players' form elements.`);

    // --- Process Input ---
    const playerNamesRaw = textArea.value;
    const playersToAdd = playerNamesRaw.split('\n')
        .map(name => name.trim())
        .filter(name => name.length > 0);

    if (playersToAdd.length === 0) {
        const warnMsg = "No player names entered in the 'Add Players' text area.";
        console.warn(`${functionName}: ${warnMsg}`);
        showStatusMessage(warnMsg, "warning");
        return; // Don't proceed if no names provided
    }

    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;
    console.debug(`${functionName}: Players to add (count: ${playersToAdd.length}):`, playersToAdd);
    console.debug(`${functionName}: Ignore player limit for these players: ${ignoresPlayerLimit}`);

    // --- Construct API Request ---
    // Match the expected body format of the /allowlist/add route
    const requestBody = {
        players: playersToAdd,             // Send list of names under 'players' key
        ignoresPlayerLimit: ignoresPlayerLimit // Send boolean under 'ignoresPlayerLimit' key
    };
    console.debug(`${functionName}: Constructed request body:`, requestBody);

    // --- Send API Request ---
    // Use the specific endpoint for adding players (POST /api/server/.../allowlist/add)
    const apiUrl = `/api/server/${serverName}/allowlist/add`; // Correct endpoint
    console.log(`${functionName}: Calling sendServerActionRequest to add players at ${apiUrl}...`);

    const apiResponseData = await sendServerActionRequest(
        serverName,
        'allowlist/add', // Correct action path relative to server
        'POST',
        requestBody,
        buttonElement
    );

    console.log(`${functionName}: Add players API call finished. Response data:`, apiResponseData);

    // --- Handle API Response ---
    if (apiResponseData && apiResponseData.status === 'success') {
        console.log(`${functionName}: Add players API call reported success.`);
        const message = apiResponseData.message || "Players processed.";
        showStatusMessage(message, "success"); // Show the message from the API

        // Clear the 'add' text area on success only if players were added/processed successfully
        console.debug(`${functionName}: Clearing 'add players' textarea.`);
        textArea.value = '';
        // Optionally reset checkbox
        // ignoreLimitCheckbox.checked = false;

        // Refresh the displayed allowlist to show the updated list
        console.log(`${functionName}: Initiating allowlist display refresh.`);
        await fetchAndUpdateAllowlistDisplay(serverName); // Await the update

    } else {
        console.error(`${functionName}: Adding players failed or application reported an error.`);
        // Error message shown by sendServerActionRequest
    }
    console.log(`${functionName}: Execution finished.`);
}


/**
 * Fetches the current allowlist from the API and updates the
 * `#current-allowlist-display` list element on the page, including "Remove" buttons.
 * Handles showing/hiding the 'no players' message element.
 *
 * @async
 * @param {string} serverName - The name of the server whose allowlist should be fetched and displayed.
 */
async function fetchAndUpdateAllowlistDisplay(serverName) {
    const functionName = 'fetchAndUpdateAllowlistDisplay';
    console.log(`${functionName}: Initiating for server: ${serverName}`);

    const displayList = document.getElementById('current-allowlist-display');

    if (!displayList) {
        console.error(`${functionName}: Target display element '#current-allowlist-display' not found. Cannot update UI.`);
        showStatusMessage("Internal page error: Allowlist display area not found.", "error");
        return;
    }
    console.debug(`${functionName}: Found display list UL element.`);

    displayList.innerHTML = '';
    const loadingLi = document.createElement('li');
    loadingLi.textContent = 'Loading allowlist...';
    loadingLi.style.fontStyle = 'italic';
    displayList.appendChild(loadingLi);

    try {
        const apiResponseData = await sendServerActionRequest(
            serverName,
            'allowlist/get', // Corrected actionPath
            'GET',
            null,
            null
        );

        displayList.removeChild(loadingLi);
        console.debug(`${functionName}: Received response from sendServerActionRequest:`, apiResponseData);

        if (apiResponseData === false) { // Error handled by sendServerActionRequest
            console.error(`${functionName}: sendServerActionRequest reported an HTTP/Network error or unexpected content type.`);
            // showStatusMessage already called by sendServerActionRequest
            // Optionally, display a persistent error in the list area if needed
            // displayList.innerHTML = '<li style="color: red;">Error loading allowlist data. Check console.</li>';
            return;
        }

        if (apiResponseData.status === 'success' && Array.isArray(apiResponseData.players)) { // Corrected to apiResponseData.players
            const players = apiResponseData.players; // Corrected to apiResponseData.players
            console.log(`${functionName}: API success status. Processing ${players.length} player entries.`);

            if (players.length > 0) {
                players.forEach(player => {
                    const li = document.createElement('li');
                    li.classList.add('allowlist-player-item');
                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'player-name';
                    nameSpan.textContent = player.name || 'Unnamed Player';
                    const metaSpan = document.createElement('span');
                    metaSpan.className = 'player-meta';
                    metaSpan.textContent = ` (Ignores Limit: ${player.ignoresPlayerLimit ? 'Yes' : 'No'})`;
                    const removeButton = document.createElement('button');
                    removeButton.type = 'button';
                    removeButton.textContent = 'Remove';
                    removeButton.className = 'action-button remove-button danger-button';
                    removeButton.title = `Remove ${player.name || 'this player'}`;
                    if (player.name) {
                        removeButton.onclick = () => removeAllowlistPlayer(removeButton, serverName, player.name);
                    } else {
                        removeButton.disabled = true;
                        removeButton.title = "Cannot remove player with missing name";
                    }
                    li.appendChild(nameSpan);
                    li.appendChild(metaSpan);
                    li.appendChild(removeButton);
                    displayList.appendChild(li);
                });
            } else {
                console.log(`${functionName}: Allowlist is empty. Displaying 'no players' message.`);
                const li = document.createElement('li');
                li.id = 'no-players-message'; // Keep ID if CSS targets it
                li.textContent = 'No players currently in allowlist.';
                li.style.fontStyle = 'italic';
                li.style.color = '#aaa';
                displayList.appendChild(li);
            }
            console.log(`${functionName}: Allowlist display updated successfully.`);

        } else { // API call was successful (HTTP 200), but app status 'error' or unexpected format
            const errorMsg = `Could not refresh allowlist: ${apiResponseData.message || 'API returned an error or invalid data.'}`;
            console.error(`${functionName}: ${errorMsg}`);
            showStatusMessage(errorMsg, "error"); // Use showStatusMessage for this API error
        }

    } catch (error) { // Catch unexpected errors *within* this function's try block
        console.error(`${functionName}: Unexpected error during UI update:`, error);
        showStatusMessage(`Client-side error updating allowlist: ${error.message}`, "error");
        if (displayList.contains(loadingLi)) { // Ensure loader is removed on error
            displayList.removeChild(loadingLi);
        }
        // displayList.innerHTML = '<li style="color: red;">Error updating display.</li>'; // Replaced by showStatusMessage
    }
    console.log(`${functionName}: Execution finished.`);
}


/**
 * Handles removing a player from the allowlist via API after confirmation.
 * Adapts to use the bulk DELETE endpoint by sending a single-player array.
 *
 * @async
 * @param {HTMLButtonElement} buttonElement The remove button clicked.
 * @param {string} serverName The name of the server.
 * @param {string} playerName The name of the player to remove.
 */
async function removeAllowlistPlayer(buttonElement, serverName, playerName) {
    const functionName = 'removeAllowlistPlayer';
    console.log(`${functionName}: Initiated for Player: '${playerName}', Server: '${serverName}'`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    if (!playerName) {
        console.error(`${functionName}: Player name missing.`);
        showStatusMessage("Internal error: Player name missing for removal.", "error");
        return;
    }

    if (!confirm(`Are you sure you want to remove '${playerName}' from the allowlist for server '${serverName}'?`)) {
        console.log(`${functionName}: Player removal cancelled by user.`);
        showStatusMessage('Player removal cancelled.', 'info');
        return;
    }

    console.log(`${functionName}: Deletion confirmed for '${playerName}'.`);

    const actionPath = 'allowlist/remove';
    const requestBody = {
        players: [playerName]
    };

    console.log(`${functionName}: Calling sendServerActionRequest (DELETE ${actionPath}) with body:`, requestBody);

    const apiResponseData = await sendServerActionRequest(
        serverName,
        actionPath,
        'DELETE',
        requestBody,
        buttonElement
    );

    console.log(`${functionName}: Delete allowlist player API call finished. Response data:`, apiResponseData);

    if (apiResponseData && apiResponseData.status === 'success') {
        console.log(`${functionName}: Player '${playerName}' removal reported success by API.`);
        const listItem = buttonElement.closest('li');
        if (listItem) {
            listItem.remove();
            console.debug(`${functionName}: Removed list item for '${playerName}'.`);
            const list = document.getElementById('current-allowlist-display');
            // const noPlayersLi = document.getElementById('no-players-message'); // This element is created dynamically now
            if (list && list.querySelectorAll('li').length === 0) { // Simpler check if list is empty
                // Re-create the "no players" message if needed
                const li = document.createElement('li');
                li.id = 'no-players-message';
                li.textContent = 'No players currently in allowlist.';
                li.style.fontStyle = 'italic';
                li.style.color = '#aaa';
                list.appendChild(li);
                console.debug(`${functionName}: List is now empty, displayed 'no players' message.`);
            }
        } else {
            console.warn(`${functionName}: Could not find parent list item to remove. Refreshing list as fallback.`);
            await fetchAndUpdateAllowlistDisplay(serverName); // Await refresh
        }
        showStatusMessage(apiResponseData.message || `Player ${playerName} processed.`, "success");
    } else {
        console.error(`${functionName}: Player '${playerName}' removal failed or API reported an error.`);
        // Error message is shown by sendServerActionRequest
    }
    console.log(`${functionName}: Execution finished.`);
}


document.addEventListener('DOMContentLoaded', () => {
    const functionName = 'AllowlistDOMContentLoaded';
    console.log(`${functionName}: DOM fully loaded and parsed.`);

    const serverNameElement = document.querySelector('p[data-server-name]');
    let foundServerName = null;

    if (serverNameElement && serverNameElement.dataset.serverName) {
        foundServerName = serverNameElement.dataset.serverName;
        console.log(`${functionName}: Found server name from data attribute: '${foundServerName}'`);
    } else {
        console.error(`${functionName}: Could not find server name via data-server-name attribute on paragraph.`);
        showStatusMessage("Critical page error: Could not determine server context.", "error");
        return;
    }

    if (foundServerName) {
        console.log(`${functionName}: Performing initial fetch and display of allowlist for server '${foundServerName}'.`);
        fetchAndUpdateAllowlistDisplay(foundServerName);
    }
});
