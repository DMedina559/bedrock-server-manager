/**
 * @fileoverview API for server configuration (properties, permissions, service).
 */

import { request } from "./api.js";

/**
 * Gets server properties.
 * @param {string} serverName
 * @returns {Promise<object>}
 */
export function getServerProperties(serverName) {
  return request(`/api/server/${serverName}/properties/get`, { method: "GET" });
}

/**
 * Sets server properties.
 * @param {string} serverName
 * @param {object} properties - The properties object.
 * @returns {Promise<object>}
 */
export function setServerProperties(serverName, properties) {
  return request(`/api/server/${serverName}/properties/set`, {
    method: "POST",
    body: { properties },
  });
}

/**
 * Gets server permissions (allowlist).
 * @param {string} serverName
 * @returns {Promise<object>}
 */
export function getServerPermissions(serverName) {
  return request(`/api/server/${serverName}/permissions/get`, {
    method: "GET",
  });
}

/**
 * Sets server permissions (allowlist).
 * @param {string} serverName
 * @param {Array<object>} permissions - List of permission objects.
 * @returns {Promise<object>}
 */
export function setServerPermissions(serverName, permissions) {
  return request(`/api/server/${serverName}/permissions/set`, {
    method: "PUT",
    body: { permissions },
  });
}

/**
 * Updates server service settings (autostart, autoupdate).
 * @param {string} serverName
 * @param {object} settings - The settings object.
 * @returns {Promise<object>}
 */
export function updateServiceSettings(serverName, settings) {
  return request(`/api/server/${serverName}/service/update`, {
    method: "POST",
    body: settings,
  });
}
