/**
 * @fileoverview API for server backups.
 */

import { request } from "./api.js";

/**
 * Triggers a backup action.
 * @param {string} serverName
 * @param {object} data - { backup_type, file_to_backup }
 * @returns {Promise<object>}
 */
export function triggerBackup(serverName, data) {
  return request(`/api/server/${serverName}/backup/action`, {
    method: "POST",
    body: data,
  });
}

/**
 * Triggers a restore action.
 * @param {string} serverName
 * @param {object} data - { restore_type, backup_file }
 * @returns {Promise<object>}
 */
export function triggerRestore(serverName, data) {
  return request(`/api/server/${serverName}/restore/action`, {
    method: "POST",
    body: data,
  });
}

/**
 * Selects a backup type (helper for restore page).
 * @param {string} serverName
 * @param {string} restoreType
 * @returns {Promise<object>}
 */
export function selectBackupType(serverName, restoreType) {
  return request(`/api/server/${serverName}/restore/select_backup_type`, {
    method: "POST",
    body: { restore_type: restoreType },
  });
}
