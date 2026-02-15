/**
 * @fileoverview API for plugin management.
 */

import { request } from "./api.js";

/**
 * Gets installed plugins.
 * @returns {Promise<object>}
 */
export function getPlugins() {
  return request("/api/plugins", { method: "GET" });
}

/**
 * Reloads all plugins.
 * @returns {Promise<object>}
 */
export function reloadPlugins() {
  return request("/api/plugins/reload", { method: "PUT" });
}

/**
 * Toggles a plugin's enabled state.
 * @param {string} pluginName
 * @param {boolean} enabled
 * @returns {Promise<object>}
 */
export function setPluginState(pluginName, enabled) {
  return request(`/api/plugins/${pluginName}`, {
    method: "POST",
    body: { enabled },
  });
}
