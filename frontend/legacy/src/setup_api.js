/**
 * @fileoverview API for initial server setup.
 */

import { request } from "./api.js";

/**
 * Creates the first user.
 * @param {object} data - { username, password }
 * @returns {Promise<object>}
 */
export function createFirstUser(data) {
  return request("/setup/create-first-user", {
    method: "POST",
    body: data,
  });
}
