// frontend/src/auth.js
/**
 * @fileoverview Handles frontend authentication logic, specifically login.
 */

import { showStatusMessage } from './utils.js';

export function initializeLoginPage() {
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const loginButton = loginForm.querySelector('button[type="submit"]');
      handleLoginAttempt(loginButton);
    });
  }
}

async function handleLoginAttempt(buttonElement) {
  const functionName = 'handleLoginAttempt';
  console.log(`${functionName}: Initiated.`);

  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');

  if (!usernameInput || !passwordInput) {
    console.error(`${functionName}: Login form elements not found.`);
    showStatusMessage('Internal page error: Login form elements missing.', 'error');
    return;
  }

  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!username) {
    showStatusMessage('Username is required.', 'warning');
    usernameInput.focus();
    return;
  }
  if (!password) {
    showStatusMessage('Password is required.', 'warning');
    passwordInput.focus();
    return;
  }

  if (buttonElement) buttonElement.disabled = true;
  showStatusMessage('Attempting login...', 'info');

  const formData = new FormData();
  formData.append('username', username);
  formData.append('password', password);

  try {
    const response = await fetch('/auth/token', {
      method: 'POST',
      body: formData,
      headers: {
        Accept: 'application/json',
      },
    });

    const responseData = await response.json();

    if (response.ok && responseData.access_token) {
      if (responseData.access_token) {
        localStorage.setItem('jwt_token', responseData.access_token);
      }
      showStatusMessage(responseData.message || 'Login successful! Redirecting...', 'success');

      const nextUrl = new URLSearchParams(window.location.search).get('next');
      setTimeout(() => {
        window.location.href = nextUrl || '/';
      }, 500);
    } else {
      const errorMessage = responseData.detail || responseData.message || 'Login failed.';
      showStatusMessage(errorMessage, 'error');
      if (passwordInput) passwordInput.value = '';
      if (buttonElement) buttonElement.disabled = false;
    }
  } catch (error) {
    const errorMsg = `Network or processing error during login: ${error.message}`;
    showStatusMessage(errorMsg, 'error');
    if (passwordInput) passwordInput.value = '';
    if (buttonElement) buttonElement.disabled = false;
  }
}
