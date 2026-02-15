/**
 * @fileoverview API for user registration.
 */

import { request } from "./api.js";

/**
 * Registers a new user.
 * @param {string} token
 * @param {object} data - { username, password }
 * @returns {Promise<object>}
 */
export function registerUser(token, data) {
  return request(`/register/${token}`, {
    method: "POST",
    body: data,
  });
}
