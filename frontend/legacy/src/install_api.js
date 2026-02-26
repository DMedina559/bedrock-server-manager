/**
 * @fileoverview API for server installation.
 */

import { request } from "./api.js";

/**
 * Installs a server.
 * @param {object} data - The installation data (server_name, server_version, overwrite, etc.).
 * @returns {Promise<object>}
 */
export function installServer(data) {
  return request("/api/server/install", { method: "POST", body: data });
}

/**
 * Lists available custom server zips.
 * @returns {Promise<object>}
 */
export function listCustomZips() {
  return request("/api/downloads/list", { method: "GET" });
}

/**
 * Checks the status of a task.
 * @param {string} taskId
 * @returns {Promise<object>}
 */
export function getTaskStatus(taskId) {
  return request(`/api/tasks/status/${taskId}`, { method: "GET" });
}
