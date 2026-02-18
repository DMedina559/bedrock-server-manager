/**
 * @fileoverview Frontend JavaScript functions for triggering content installation
 * (worlds and addons) via API calls based on user interaction.
 */

import {
  installWorld,
  exportWorld,
  resetWorld,
  installAddon,
} from "./content_api.js";
import { showStatusMessage, handleApiAction } from "./ui_utils.js";

function handleWorldInstall(buttonElement, serverName, worldFilePath) {
  const filenameForDisplay =
    worldFilePath.split(/[\\/]/).pop() || worldFilePath;
  const confirmationMessage = `Install world '${filenameForDisplay}' for server '${serverName}'?\n\nWARNING: This will permanently REPLACE the current world data!`;
  if (!confirm(confirmationMessage)) {
    showStatusMessage("World installation cancelled.", "info");
    return;
  }
  handleApiAction(buttonElement, () => installWorld(serverName, worldFilePath));
}

function handleWorldExport(buttonElement, serverName) {
  handleApiAction(buttonElement, async () => {
    const result = await exportWorld(serverName);
    if (result && result.status === "success") {
      showStatusMessage(result.message + " Refreshing list...", "success");
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    }
    return result;
  });
}

function handleWorldReset(buttonElement, serverName) {
  if (
    !confirm(`WARNING: Reset the current world for server '${serverName}'?`)
  ) {
    showStatusMessage("World reset cancelled.", "info");
    return;
  }
  handleApiAction(buttonElement, () => resetWorld(serverName));
}

function handleAddonInstall(buttonElement, serverName, addonFilePath) {
  const filenameForDisplay =
    addonFilePath.split(/[\\/]/).pop() || addonFilePath;
  const confirmationMessage = `Install addon '${filenameForDisplay}' for server '${serverName}'?`;
  if (!confirm(confirmationMessage)) {
    showStatusMessage("Addon installation cancelled.", "info");
    return;
  }
  handleApiAction(buttonElement, () => installAddon(serverName, addonFilePath));
}

export function initializeContentManagementPage() {
  console.log("Content management page script loaded.");

  const page = document.getElementById("content-management-page");
  const serverName = page?.dataset.serverName;

  document
    .getElementById("export-world-btn")
    ?.addEventListener("click", (e) =>
      handleWorldExport(e.currentTarget, serverName),
    );
  document
    .getElementById("reset-world-btn")
    ?.addEventListener("click", (e) =>
      handleWorldReset(e.currentTarget, serverName),
    );

  document.querySelectorAll(".install-addon-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      const addonPath = btn.dataset.addonPath;
      handleAddonInstall(btn, serverName, addonPath);
    });
  });

  document.querySelectorAll(".import-world-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      const worldPath = btn.dataset.worldPath;
      handleWorldInstall(btn, serverName, worldPath);
    });
  });
}
