// frontend/src/setup.js
import { sendServerActionRequest, showStatusMessage } from './utils.js';

function submitForm() {
  const form = document.getElementById('setup-form');
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const confirm_password = document.getElementById('confirm_password').value;

  if (!username || !password || !confirm_password) {
    showStatusMessage('All fields are required.', 'error');
    return;
  }

  if (password !== confirm_password) {
    showStatusMessage('Passwords do not match.', 'error');
    return;
  }

  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());

  sendServerActionRequest(null, '/setup/create-first-user', 'POST', data).then((response) => {
    if (response && response.status === 'success') {
      window.location.href = response.redirect_url;
    }
  });
}

export function initializeSetupPage() {
  const setupForm = document.getElementById('setup-form');
  if (setupForm) {
    setupForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitForm();
    });
  }
}
