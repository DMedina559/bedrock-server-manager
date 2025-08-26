// frontend/src/register.js
import { sendServerActionRequest, showStatusMessage } from './utils.js';

function submitForm() {
  const form = document.getElementById('register-form');
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

  const token = document.getElementById('register-form').dataset.token;

  sendServerActionRequest(null, `/register/${token}`, 'POST', data).then((response) => {
    if (response && response.status === 'success') {
      window.location.href = response.redirect_url;
    }
  });
}

export function initializeRegisterPage() {
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitForm();
    });
  }
}
