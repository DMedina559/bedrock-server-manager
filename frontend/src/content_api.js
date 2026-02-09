/**
 * @fileoverview API for content management (worlds, addons).
 */

import { request } from "./api.js";

/**
 * Installs a world from a file path.
 * @param {string} serverName
 * @param {string} filePath
 * @returns {Promise<object>}
 */
export function installWorld(serverName, filePath) {
  return request(`/api/server/${serverName}/world/install`, {
    method: "POST",
    body: { filename: filePath },
  });
}

/**
 * Exports the current world.
 * @param {string} serverName
 * @returns {Promise<object>}
 */
export function exportWorld(serverName) {
  return request(`/api/server/${serverName}/world/export`, { method: "POST" });
}

/**
 * Resets the current world.
 * @param {string} serverName
 * @returns {Promise<object>}
 */
export function resetWorld(serverName) {
  return request(`/api/server/${serverName}/world/reset`, { method: "DELETE" });
}

/**
 * Installs an addon from a file path.
 * @param {string} serverName
 * @param {string} filePath
 * @returns {Promise<object>}
 */
export function installAddon(serverName, filePath) {
  return request(`/api/server/${serverName}/addon/install`, {
    method: "POST",
    body: { filename: filePath },
  });
}
