// frontend/src/allowlist.js
/**
 * @fileoverview Frontend JavaScript for managing the server allowlist.
 * Handles user input, interacts with the allowlist API endpoints, and updates the UI.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

export function initializeAllowlistPage() {
  const functionName = 'AllowlistManager';
  console.log(`${functionName}: Initializing allowlist page.`);

  const serverNameElement = document.querySelector('p[data-server-name]');
  let serverName = null;

  if (serverNameElement && serverNameElement.dataset.serverName) {
    serverName = serverNameElement.dataset.serverName;
    console.log(`${functionName}: Found server name: '${serverName}'`);
  } else {
    console.error(`${functionName}: Could not find server name.`);
    showStatusMessage('Critical page error: Could not determine server context.', 'error');
    return;
  }

  async function addAllowlistPlayers(buttonElement) {
    const functionName = 'addAllowlistPlayers';
    console.log(`${functionName}: Initiated. Server: ${serverName}`);
    console.debug(`${functionName}: Button Element:`, buttonElement);

    const textArea = document.getElementById('player-names-add');
    const ignoreLimitCheckbox = document.getElementById('ignore-limit-add');

    if (!textArea || !ignoreLimitCheckbox) {
      const errorMsg = "Required 'add player' form elements not found.";
      console.error(`${functionName}: ${errorMsg}`);
      showStatusMessage(`Internal page error: ${errorMsg}`, 'error');
      return;
    }

    const playerNamesRaw = textArea.value;
    const playersToAdd = playerNamesRaw
      .split('\n')
      .map((name) => name.trim())
      .filter((name) => name.length > 0);

    if (playersToAdd.length === 0) {
      const warnMsg = 'No player names entered.';
      console.warn(`${functionName}: ${warnMsg}`);
      showStatusMessage(warnMsg, 'warning');
      return;
    }

    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;
    const requestBody = {
      players: playersToAdd,
      ignoresPlayerLimit: ignoresPlayerLimit,
    };

    const apiResponseData = await sendServerActionRequest(
      serverName,
      'allowlist/add',
      'POST',
      requestBody,
      buttonElement,
    );

    if (apiResponseData && apiResponseData.status === 'success') {
      const message = apiResponseData.message || 'Players processed.';
      showStatusMessage(message, 'success');
      textArea.value = '';
      await fetchAndUpdateAllowlistDisplay();
    }
  }

  async function fetchAndUpdateAllowlistDisplay() {
    const functionName = 'fetchAndUpdateAllowlistDisplay';
    console.log(`${functionName}: Initiating for server: ${serverName}`);

    const displayList = document.getElementById('current-allowlist-display');
    if (!displayList) {
      console.error(`${functionName}: Target display element not found.`);
      showStatusMessage('Internal page error: Allowlist display area not found.', 'error');
      return;
    }

    displayList.innerHTML = '<li><i>Loading allowlist...</i></li>';

    try {
      const apiResponseData = await sendServerActionRequest(serverName, 'allowlist/get', 'GET', null, null, true);
      displayList.innerHTML = '';

      if (apiResponseData && apiResponseData.status === 'success' && Array.isArray(apiResponseData.players)) {
        const players = apiResponseData.players;
        if (players.length > 0) {
          players.forEach((player) => {
            const li = document.createElement('li');
            li.className = 'allowlist-player-item';
            li.innerHTML = `
                            <span class="player-name">${player.name || 'Unnamed Player'}</span>
                            <span class="player-meta"> (Ignores Limit: ${player.ignoresPlayerLimit ? 'Yes' : 'No'})</span>
                        `;
            const removeButton = document.createElement('button');
            removeButton.type = 'button';
            removeButton.textContent = 'Remove';
            removeButton.className = 'action-button remove-button danger-button';
            removeButton.title = `Remove ${player.name || 'this player'}`;
            if (player.name) {
              // Use data attribute instead of onclick
              removeButton.dataset.playerName = player.name;
            } else {
              removeButton.disabled = true;
            }
            li.appendChild(removeButton);
            displayList.appendChild(li);
          });
        } else {
          displayList.innerHTML = '<li><i>No players currently in allowlist.</i></li>';
        }
      } else {
        const errorMsg = `Could not refresh allowlist: ${apiResponseData.message || 'API returned an error.'}`;
        showStatusMessage(errorMsg, 'error');
      }
    } catch (error) {
      console.error(`${functionName}: Unexpected error:`, error);
      showStatusMessage(`Client-side error updating allowlist: ${error.message}`, 'error');
      displayList.innerHTML = '<li><i style="color: red;">Error updating display.</i></li>';
    }
  }

  async function removeAllowlistPlayer(buttonElement, playerName) {
    if (!confirm(`Are you sure you want to remove '${playerName}' from the allowlist?`)) {
      showStatusMessage('Player removal cancelled.', 'info');
      return;
    }

    const requestBody = { players: [playerName] };
    const apiResponseData = await sendServerActionRequest(
      serverName,
      'allowlist/remove',
      'DELETE',
      requestBody,
      buttonElement,
    );

    if (apiResponseData && apiResponseData.status === 'success') {
      await fetchAndUpdateAllowlistDisplay();
      showStatusMessage(apiResponseData.message || `Player ${playerName} processed.`, 'success');
    }
  }

  // Attach event listeners
  const addPlayersButton = document.getElementById('add-allowlist-players-btn');
  if (addPlayersButton) {
    addPlayersButton.addEventListener('click', () => addAllowlistPlayers(addPlayersButton));
  }

  // Event delegation for remove buttons
  const displayList = document.getElementById('current-allowlist-display');
  if (displayList) {
    displayList.addEventListener('click', (event) => {
      const target = event.target;
      if (target.classList.contains('remove-button') && target.dataset.playerName) {
        removeAllowlistPlayer(target, target.dataset.playerName);
      }
    });
  }

  // Initial fetch
  fetchAndUpdateAllowlistDisplay();
}
