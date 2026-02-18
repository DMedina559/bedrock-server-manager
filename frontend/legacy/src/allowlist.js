/**
 * @fileoverview Frontend JavaScript for managing the server allowlist.
 * Handles user input, interacts with the allowlist API endpoints, and updates the UI.
 */

import {
  getAllowlist,
  addPlayersToAllowlist,
  removePlayersFromAllowlist,
} from "./allowlist_api.js";
import { showStatusMessage, handleApiAction } from "./ui_utils.js";

export function initializeAllowlistPage() {
  const functionName = "AllowlistManager";
  console.log(`${functionName}: Initializing allowlist page.`);

  const serverNameElement = document.querySelector("p[data-server-name]");
  let serverName = null;

  if (serverNameElement && serverNameElement.dataset.serverName) {
    serverName = serverNameElement.dataset.serverName;
    console.log(`${functionName}: Found server name: '${serverName}'`);
  } else {
    console.error(`${functionName}: Could not find server name.`);
    showStatusMessage(
      "Critical page error: Could not determine server context.",
      "error",
    );
    return;
  }

  async function addAllowlistPlayers(buttonElement) {
    const textArea = document.getElementById("player-names-add");
    const ignoreLimitCheckbox = document.getElementById("ignore-limit-add");

    if (!textArea || !ignoreLimitCheckbox) {
      showStatusMessage(
        "Required 'add player' form elements not found.",
        "error",
      );
      return;
    }

    const playerNamesRaw = textArea.value;
    const playersToAdd = playerNamesRaw
      .split("\n")
      .map((name) => name.trim())
      .filter((name) => name.length > 0);

    if (playersToAdd.length === 0) {
      showStatusMessage("No player names entered.", "warning");
      return;
    }

    const ignoresPlayerLimit = ignoreLimitCheckbox.checked;

    await handleApiAction(buttonElement, async () => {
      const response = await addPlayersToAllowlist(
        serverName,
        playersToAdd,
        ignoresPlayerLimit,
      );
      if (response && response.status === "success") {
        textArea.value = "";
        await fetchAndUpdateAllowlistDisplay();
      }
      return response;
    });
  }

  async function fetchAndUpdateAllowlistDisplay() {
    const displayList = document.getElementById("current-allowlist-display");
    if (!displayList) {
      showStatusMessage(
        "Internal page error: Allowlist display area not found.",
        "error",
      );
      return;
    }

    displayList.innerHTML = "<li><i>Loading allowlist...</i></li>";

    try {
      const response = await getAllowlist(serverName);
      displayList.innerHTML = "";

      if (
        response &&
        response.status === "success" &&
        Array.isArray(response.players)
      ) {
        const players = response.players;
        if (players.length > 0) {
          players.forEach((player) => {
            const li = document.createElement("li");
            li.className = "allowlist-player-item";
            li.innerHTML = `
                <span class="player-name">${player.name || "Unnamed Player"}</span>
                <span class="player-meta"> (Ignores Limit: ${player.ignoresPlayerLimit ? "Yes" : "No"})</span>
            `;
            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.textContent = "Remove";
            removeButton.className =
              "action-button remove-button danger-button";
            removeButton.title = `Remove ${player.name || "this player"}`;
            if (player.name) {
              removeButton.dataset.playerName = player.name;
            } else {
              removeButton.disabled = true;
            }
            li.appendChild(removeButton);
            displayList.appendChild(li);
          });
        } else {
          displayList.innerHTML =
            "<li><i>No players currently in allowlist.</i></li>";
        }
      } else {
        showStatusMessage(
          `Could not refresh allowlist: ${response.message || "API error."}`,
          "error",
        );
      }
    } catch (error) {
      console.error(`${functionName}: Unexpected error:`, error);
      showStatusMessage(`Error updating allowlist: ${error.message}`, "error");
      displayList.innerHTML =
        '<li><i style="color: red;">Error updating display.</i></li>';
    }
  }

  async function removeAllowlistPlayer(buttonElement, playerName) {
    if (
      !confirm(
        `Are you sure you want to remove '${playerName}' from the allowlist?`,
      )
    ) {
      showStatusMessage("Player removal cancelled.", "info");
      return;
    }

    await handleApiAction(buttonElement, async () => {
      const response = await removePlayersFromAllowlist(serverName, [
        playerName,
      ]);
      if (response && response.status === "success") {
        await fetchAndUpdateAllowlistDisplay();
      }
      return response;
    });
  }

  // Attach event listeners
  const addPlayersButton = document.getElementById("add-allowlist-players-btn");
  if (addPlayersButton) {
    addPlayersButton.addEventListener("click", () =>
      addAllowlistPlayers(addPlayersButton),
    );
  }

  const displayList = document.getElementById("current-allowlist-display");
  if (displayList) {
    displayList.addEventListener("click", (event) => {
      const target = event.target;
      if (
        target.classList.contains("remove-button") &&
        target.dataset.playerName
      ) {
        removeAllowlistPlayer(target, target.dataset.playerName);
      }
    });
  }

  fetchAndUpdateAllowlistDisplay();
}
