/**
 * @fileoverview API for global settings.
 */

import { request } from "./api.js";

/**
 * Gets global settings.
 * @returns {Promise<object>}
 */
export function getSettings() {
  return request("/api/settings", { method: "GET" });
}

/**
 * Updates a global setting.
 * @param {string} key
 * @param {any} value
 * @returns {Promise<object>}
 */
export function updateSetting(key, value) {
  return request("/api/settings", {
    method: "POST",
    body: { key, value },
  });
}

/**
 * Reloads global settings from file.
 * @returns {Promise<object>}
 */
export function reloadSettings() {
  return request("/api/settings/reload", { method: "POST" });
}
