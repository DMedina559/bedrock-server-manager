/**
 * @fileoverview Handles frontend authentication logic, specifically login.
 */

import { login } from "./auth_api.js";
import { showStatusMessage, handleApiAction } from "./ui_utils.js";

export function initializeLoginPage() {
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const loginButton = loginForm.querySelector('button[type="submit"]');
      handleLoginAttempt(loginButton, loginForm);
    });
  }
}

async function handleLoginAttempt(buttonElement, formElement) {
  const functionName = "handleLoginAttempt";
  console.log(`${functionName}: Initiated.`);

  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");

  if (!usernameInput || !passwordInput) {
    console.error(`${functionName}: Login form elements not found.`);
    showStatusMessage(
      "Internal page error: Login form elements missing.",
      "error",
    );
    return;
  }

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const rememberMe = document.getElementById("rememberMe")?.checked;

  if (!username) {
    showStatusMessage("Username is required.", "warning");
    usernameInput.focus();
    return;
  }
  if (!password) {
    showStatusMessage("Password is required.", "warning");
    passwordInput.focus();
    return;
  }

  const formData = new FormData(formElement);
  // Remember Me is handled client-side for storage location, but could be sent if backend supports it.

  await handleApiAction(
    buttonElement,
    async () => {
      const response = await login(formData);

      if (response && response.access_token) {
        if (rememberMe) {
          localStorage.setItem("jwt_token", response.access_token);
          sessionStorage.removeItem("jwt_token");
        } else {
          sessionStorage.setItem("jwt_token", response.access_token);
          localStorage.removeItem("jwt_token");
        }

        showStatusMessage(
          response.message || "Login successful! Redirecting...",
          "success",
        );
        const nextUrl = new URLSearchParams(window.location.search).get("next");
        // Only allow same-origin, root-relative paths to avoid open redirects.
        const redirectPath =
          typeof nextUrl === "string" &&
          nextUrl.startsWith("/") &&
          !nextUrl.startsWith("//")
            ? nextUrl
            : "/";
        setTimeout(() => {
          window.location.href = redirectPath;
        }, 500);
      }
      return response;
    },
    "Attempting login...",
  );
}
