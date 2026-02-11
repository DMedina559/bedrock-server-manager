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

  await handleApiAction(
    buttonElement,
    async () => {
      const response = await login(formData);

      if (response && response.access_token) {
        localStorage.setItem("jwt_token", response.access_token);
        showStatusMessage(
          response.message || "Login successful! Redirecting...",
          "success",
        );
        const nextUrl = new URLSearchParams(window.location.search).get("next");
        setTimeout(() => {
          window.location.href = nextUrl || "/";
        }, 500);
      }
      return response;
    },
    "Attempting login...",
  );
}
