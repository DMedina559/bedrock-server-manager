/**
 * @fileoverview API functions for account management.
 */

import { request } from "./api.js";

/**
 * Gets the current user's profile.
 * @returns {Promise<object>}
 */
export function getUserProfile() {
  return request("/api/account", { method: "GET" });
}

/**
 * Updates the current user's profile.
 * @param {object} data - { full_name, email }
 * @returns {Promise<object>}
 */
export function updateUserProfile(data) {
  return request("/api/account/profile", { method: "POST", body: data });
}

/**
 * Changes the current user's password.
 * @param {object} data - { current_password, new_password }
 * @returns {Promise<object>}
 */
export function changePassword(data) {
  return request("/api/account/change-password", {
    method: "POST",
    body: data,
  });
}

/**
 * Gets available themes.
 * @returns {Promise<object>}
 */
export function getThemes() {
  return request("/api/themes", { method: "GET" });
}

/**
 * Sets the user's theme.
 * @param {string} themeName
 * @returns {Promise<object>}
 */
export function setUserTheme(themeName) {
  return request("/api/account/theme", {
    method: "POST",
    body: { theme: themeName },
  });
}
