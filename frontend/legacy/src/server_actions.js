/**
 * @fileoverview Logic for common server actions (start, stop, restart, delete, etc.).
 * Pure business logic, decoupled from the DOM.
 */

import { request } from "./api.js";

/**
 * Starts a server.
 * @param {string} serverName - The name of the server to start.
 * @returns {Promise<object>} The API response.
 */
export function startServer(serverName) {
  if (!serverName) throw new Error("Server name is required.");
  return request(`/api/server/${serverName}/start`, { method: "POST" });
}

/**
 * Stops a server.
 * @param {string} serverName - The name of the server to stop.
 * @returns {Promise<object>} The API response.
 */
export function stopServer(serverName) {
  if (!serverName) throw new Error("Server name is required.");
  return request(`/api/server/${serverName}/stop`, { method: "POST" });
}

/**
 * Restarts a server.
 * @param {string} serverName - The name of the server to restart.
 * @returns {Promise<object>} The API response.
 */
export function restartServer(serverName) {
  if (!serverName) throw new Error("Server name is required.");
  return request(`/api/server/${serverName}/restart`, { method: "POST" });
}

/**
 * Sends a command to a server console.
 * @param {string} serverName - The name of the server.
 * @param {string} command - The command string.
 * @returns {Promise<object>} The API response.
 */
export function sendCommand(serverName, command) {
  if (!serverName) throw new Error("Server name is required.");
  if (!command || !command.trim()) throw new Error("Command cannot be empty.");
  return request(`/api/server/${serverName}/send_command`, {
    method: "POST",
    body: { command: command.trim() },
  });
}

/**
 * Deletes a server.
 * @param {string} serverName - The name of the server to delete.
 * @returns {Promise<object>} The API response.
 */
export function deleteServer(serverName) {
  if (!serverName) throw new Error("Server name is required.");
  return request(`/api/server/${serverName}/delete`, { method: "DELETE" });
}

/**
 * Updates a server.
 * @param {string} serverName - The name of the server to update.
 * @returns {Promise<object>} The API response.
 */
export function updateServer(serverName) {
  if (!serverName) throw new Error("Server name is required.");
  return request(`/api/server/${serverName}/update`, { method: "POST" });
}

/**
 * Fetches the list of all servers.
 * @returns {Promise<object>} The API response containing the list of servers.
 */
export function fetchServers() {
  return request("/api/servers", { method: "GET" });
}

/**
 * Fetches the process info/usage for a server.
 * @param {string} serverName
 * @returns {Promise<object>}
 */
export function getServerUsage(serverName) {
  if (!serverName) throw new Error("Server name is required.");
  return request(`/api/server/${serverName}/process_info`, { method: "GET" });
}
