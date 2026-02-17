/**
 * @fileoverview Core API client for making HTTP requests in V2.
 * Handles fetch logic, headers, authentication, and response parsing.
 * Matches functionality of frontend/legacy/src/api.js
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

  const jwtToken = localStorage.getItem("jwt_token");
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
      try {
        data = await response.json();
      } catch (jsonError) {
        // Fallback if JSON parsing fails but header said JSON (rare but possible)
        throw new ApiError(
          "Invalid JSON response from server",
          response.status,
          null,
        );
      }
    } else {
      // If not JSON, treat as text (could be HTML error page, plain text, etc.)
      const text = await response.text();

      // If we expected JSON (based on Accept header) but got HTML (e.g. 404 page, 500 error page, or Login page redirect)
      // we should probably treat it as an error unless the caller explicitly handles it.
      if (!response.ok) {
        throw new ApiError(
          `Request failed with status ${response.status} (Non-JSON response)`,
          response.status,
          text,
        );
      }

      // If success (200) but HTML (e.g. redirected to login page without 401), this is tricky.
      // Legacy behavior might just return the text.
      // But usually our API should return JSON.
      data = text;

      // Check if it looks like the login page (common issue when session expires and backend redirects instead of 401)
      if (
        typeof text === "string" &&
        text.includes("<!DOCTYPE html>") &&
        text.includes("Login")
      ) {
        // Force a 401 style error so AuthContext can handle logout
        throw new ApiError("Session expired (Redirected to Login)", 401, null);
      }
    }

    if (!response.ok) {
      let errorMessage = `Request failed with status ${response.status}`;
      if (typeof data === "object" && data !== null && data.message) {
        errorMessage = data.message;
      } else if (typeof data === "object" && data !== null && data.detail) {
        // FastAPI often returns 'detail'
        errorMessage = data.detail;
      } else if (typeof data === "string" && data.length > 0) {
        errorMessage = data.substring(0, 200);
      }

      throw new ApiError(errorMessage, response.status, data);
    }

    // Legacy API sometimes returns { status: "error", message: "..." } even with 200 OK
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
    // Network errors
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
