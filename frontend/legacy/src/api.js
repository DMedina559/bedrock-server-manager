/**
 * @fileoverview Core API client for making HTTP requests.
 * Handles fetch logic, headers, authentication, and response parsing.
 * This module is pure JavaScript and does not interact with the DOM.
 */

/**
 * Custom error class for API-related errors.
 */
export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Sends an HTTP request to the API.
 *
 * @param {string} url - The URL to request. relative URLs are supported.
 * @param {object} [options={}] - Fetch options (method, body, headers, etc.).
 * @returns {Promise<any>} Resolves with the response data (JSON or null for 204).
 * @throws {ApiError} If the response status is not 2xx.
 */
export async function request(url, options = {}) {
  const { method = "GET", body, headers = {}, ...restOptions } = options;

  const defaultHeaders = {
    Accept: "application/json",
  };

  let jwtToken = sessionStorage.getItem("jwt_token");
  if (!jwtToken) {
    jwtToken = localStorage.getItem("jwt_token");
  }

  if (jwtToken) {
    defaultHeaders["Authorization"] = `Bearer ${jwtToken}`;
  }

  const config = {
    method: method.toUpperCase(),
    headers: { ...defaultHeaders, ...headers },
    ...restOptions,
  };

  if (body) {
    if (
      !config.headers["Content-Type"] &&
      !(body instanceof FormData) &&
      typeof body === "object"
    ) {
      config.headers["Content-Type"] = "application/json";
      config.body = JSON.stringify(body);
    } else {
      config.body = body;
    }
  }

  try {
    const response = await fetch(url, config);

    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers.get("content-type");
    let data;
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      let errorMessage = `Request failed with status ${response.status}`;
      if (typeof data === "object" && data !== null && data.message) {
        errorMessage = data.message;
      } else if (typeof data === "string" && data.length > 0) {
        errorMessage = data.substring(0, 200);
      }

      throw new ApiError(errorMessage, response.status, data);
    }

    if (
      data &&
      typeof data === "object" &&
      data.status &&
      data.status === "error"
    ) {
      throw new ApiError(
        data.message || "Application error",
        response.status,
        data,
      );
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(error.message, 0, null);
  }
}

// ... helpers
export function get(url, options = {}) {
  return request(url, { ...options, method: "GET" });
}

export function post(url, body, options = {}) {
  return request(url, { ...options, method: "POST", body });
}

export function put(url, body, options = {}) {
  return request(url, { ...options, method: "PUT", body });
}

export function del(url, options = {}) {
  return request(url, { ...options, method: "DELETE" });
}
