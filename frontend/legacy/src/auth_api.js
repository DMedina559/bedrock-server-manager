/**
 * @fileoverview API for authentication.
 */

import { request } from "./api.js";

/**
 * Logs in a user.
 * @param {FormData} formData
 * @returns {Promise<object>}
 */
export function login(formData) {
  // /auth/token endpoint expects form data, not JSON
  // request() handles FormData body automatically if we pass it as body
  // and don't set Content-Type to application/json (which request() avoids if body is FormData)
  return request("/auth/token", {
    method: "POST",
    body: formData,
    headers: {
      Accept: "application/json",
    },
  });
}
