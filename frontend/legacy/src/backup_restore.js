/**
 * @fileoverview Frontend JavaScript functions for triggering server backup and restore operations.
 */

import {
  triggerBackup,
  triggerRestore,
  selectBackupType,
} from "./backup_api.js";
import { showStatusMessage, handleApiAction } from "./ui_utils.js";

export function initializeBackupRestorePage() {
  console.log("Backup/Restore page script loaded.");

  const page = document.getElementById("backup-restore-page");
  const serverName = page?.dataset.serverName;

  // --- Handlers ---
  function handleBackup(buttonElement, backupType) {
    if (backupType === "all") {
      const confirmationMessage = `Perform a full backup (world + config) for server '${serverName}'?`;
      if (!confirm(confirmationMessage)) {
        showStatusMessage("Full backup cancelled.", "info");
        return;
      }
    }

    handleApiAction(buttonElement, () =>
      triggerBackup(serverName, { backup_type: backupType }),
    );
  }

  function handleSpecificConfigBackup(buttonElement, filename) {
    if (!filename || !filename.trim()) {
      showStatusMessage("Internal error: No filename provided.", "error");
      return;
    }

    handleApiAction(buttonElement, () =>
      triggerBackup(serverName, {
        backup_type: "config",
        file_to_backup: filename.trim(),
      }),
    );
  }

  function handleRestore(buttonElement, restoreType, backupFilePath) {
    if (!backupFilePath || !backupFilePath.trim()) {
      showStatusMessage(
        "Internal error: No backup file path provided.",
        "error",
      );
      return;
    }

    const backupFilename = backupFilePath.trim().split(/[\\/]/).pop();
    const confirmationMessage = `Are you sure you want to restore backup '${backupFilename}' for server '${serverName}'? This will OVERWRITE current data!`;
    if (!confirm(confirmationMessage)) {
      showStatusMessage("Restore operation cancelled.", "info");
      return;
    }

    handleApiAction(buttonElement, () =>
      triggerRestore(serverName, {
        restore_type: restoreType.toLowerCase(),
        backup_file: backupFilePath.trim(),
      }),
    );
  }

  function handleRestoreAll(buttonElement) {
    const confirmationMessage = `Are you sure you want to restore ALL latest backups for server '${serverName}'? This will OVERWRITE current world and configuration files!`;
    if (!confirm(confirmationMessage)) {
      showStatusMessage("Restore All operation cancelled.", "info");
      return;
    }

    handleApiAction(buttonElement, () =>
      triggerRestore(serverName, {
        restore_type: "all",
        backup_file: null,
      }),
    );
  }

  async function handleSelectType(buttonElement, restoreType) {
    await handleApiAction(buttonElement, async () => {
      const response = await selectBackupType(serverName, restoreType);
      if (response && response.status === "success" && response.redirect_url) {
        window.location.href = response.redirect_url;
      }
      return response;
    });
  }

  // --- Event Listeners ---
  document
    .getElementById("backup-world-btn")
    ?.addEventListener("click", (e) => handleBackup(e.currentTarget, "world"));
  document
    .getElementById("backup-all-btn")
    ?.addEventListener("click", (e) => handleBackup(e.currentTarget, "all"));

  document
    .getElementById("select-world-backup-btn")
    ?.addEventListener("click", (e) =>
      handleSelectType(e.currentTarget, "world"),
    );
  document
    .getElementById("select-properties-backup-btn")
    ?.addEventListener("click", (e) =>
      handleSelectType(e.currentTarget, "properties"),
    );
  document
    .getElementById("select-allowlist-backup-btn")
    ?.addEventListener("click", (e) =>
      handleSelectType(e.currentTarget, "allowlist"),
    );
  document
    .getElementById("select-permissions-backup-btn")
    ?.addEventListener("click", (e) =>
      handleSelectType(e.currentTarget, "permissions"),
    );
  document
    .getElementById("restore-all-btn")
    ?.addEventListener("click", (e) => handleRestoreAll(e.currentTarget));

  document
    .getElementById("backup-allowlist-btn")
    ?.addEventListener("click", (e) =>
      handleSpecificConfigBackup(e.currentTarget, "allowlist.json"),
    );
  document
    .getElementById("backup-permissions-btn")
    ?.addEventListener("click", (e) =>
      handleSpecificConfigBackup(e.currentTarget, "permissions.json"),
    );
  document
    .getElementById("backup-properties-btn")
    ?.addEventListener("click", (e) =>
      handleSpecificConfigBackup(e.currentTarget, "server.properties"),
    );

  document.querySelectorAll(".restore-backup-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      const restoreType = btn.dataset.restoreType;
      const backupPath = btn.dataset.backupPath;
      handleRestore(btn, restoreType, backupPath);
    });
  });
}
