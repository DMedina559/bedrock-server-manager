/**
 * @fileoverview API functions for user management.
 */

import { request } from "./api.js";

/**
 * Generates a registration token.
 * @param {object} data - The data for token generation (e.g., expiration).
 * @returns {Promise<object>}
 */
export function generateRegistrationToken(data) {
  return request("/register/generate-token", { method: "POST", body: data });
}

/**
 * Disables a user.
 * @param {string} userId
 * @returns {Promise<object>}
 */
export function disableUser(userId) {
  return request(`/users/${userId}/disable`, { method: "POST" });
}

/**
 * Enables a user.
 * @param {string} userId
 * @returns {Promise<object>}
 */
export function enableUser(userId) {
  return request(`/users/${userId}/enable`, { method: "POST" });
}

/**
 * Deletes a user.
 * @param {string} userId
 * @returns {Promise<object>}
 */
export function deleteUser(userId) {
  return request(`/users/${userId}/delete`, { method: "POST" });
}

/**
 * Updates a user's role.
 * @param {string} userId
 * @param {string} newRole - 'admin' or 'user'
 * @returns {Promise<object>}
 */
export function updateUserRole(userId, newRole) {
  return request(`/users/${userId}/role`, {
    method: "POST",
    body: { role: newRole },
  });
}
