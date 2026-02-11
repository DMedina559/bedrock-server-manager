/**
 * @fileoverview API for allowlist management.
 */

import { request } from "./api.js";

/**
 * Gets the allowlist.
 * @param {string} serverName
 * @returns {Promise<object>}
 */
export function getAllowlist(serverName) {
  return request(`/api/server/${serverName}/allowlist/get`, { method: "GET" });
}

/**
 * Adds players to the allowlist.
 * @param {string} serverName
 * @param {Array<string>} players - List of player names.
 * @param {boolean} ignoresPlayerLimit
 * @returns {Promise<object>}
 */
export function addPlayersToAllowlist(serverName, players, ignoresPlayerLimit) {
  return request(`/api/server/${serverName}/allowlist/add`, {
    method: "POST",
    body: { players, ignoresPlayerLimit },
  });
}

/**
 * Removes players from the allowlist.
 * @param {string} serverName
 * @param {Array<string>} players - List of player names.
 * @returns {Promise<object>}
 */
export function removePlayersFromAllowlist(serverName, players) {
  return request(`/api/server/${serverName}/allowlist/remove`, {
    method: "DELETE",
    body: { players },
  });
}
