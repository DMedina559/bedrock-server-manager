/**
 * @fileoverview API for server-specific settings.
 */

import { request } from "./api.js";

/**
 * Gets server settings.
 * @param {string} serverName
 * @returns {Promise<object>}
 */
export function getServerSettings(serverName) {
  return request(`/api/servers/${serverName}/settings`, { method: "GET" });
}

/**
 * Updates a server setting.
 * @param {string} serverName
 * @param {string} key
 * @param {any} value
 * @returns {Promise<object>}
 */
export function updateServerSetting(serverName, key, value) {
  return request(`/api/servers/${serverName}/settings`, {
    method: "POST",
    body: { key, value },
  });
}
