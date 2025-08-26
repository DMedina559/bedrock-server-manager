// frontend/src/users.js
import { sendServerActionRequest } from './utils.js';

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(
    () => {
      alert('Copied to clipboard');
    },
    (err) => {
      alert('Could not copy text: ', err);
    },
  );
}

function generateToken() {
  const form = document.getElementById('generate-token-form');
  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());

  sendServerActionRequest(null, '/register/generate-token', 'POST', data).then((response) => {
    if (response && response.status === 'success') {
      window.location.href = response.redirect_url;
    }
  });
}

function disableUser(userId) {
  if (confirm('Are you sure you want to disable this user?')) {
    sendServerActionRequest(null, `/users/${userId}/disable`, 'POST').then((response) => {
      if (response && response.status === 'success') {
        window.location.reload();
      }
    });
  }
}

function enableUser(userId) {
  if (confirm('Are you sure you want to enable this user?')) {
    sendServerActionRequest(null, `/users/${userId}/enable`, 'POST').then((response) => {
      if (response && response.status === 'success') {
        window.location.reload();
      }
    });
  }
}

function deleteUser(userId) {
  if (confirm('Are you sure you want to delete this user?')) {
    sendServerActionRequest(null, `/users/${userId}/delete`, 'POST').then((response) => {
      if (response && response.status === 'success') {
        window.location.reload();
      }
    });
  }
}

function updateUserRole(userId) {
  const role = document.getElementById(`role-${userId}`).value;
  const data = { role: role };

  sendServerActionRequest(null, `/users/${userId}/role`, 'POST', data).then((response) => {
    if (response && response.status === 'success') {
      window.location.reload();
    }
  });
}

export function initializeUsersPage() {
  document.getElementById('generate-token-btn')?.addEventListener('click', generateToken);

  document.querySelectorAll('.copy-link-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      copyToClipboard(e.currentTarget.dataset.link);
    });
  });

  document.querySelectorAll('.update-role-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      updateUserRole(e.currentTarget.dataset.userId);
    });
  });

  document.querySelectorAll('.disable-user-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      disableUser(e.currentTarget.dataset.userId);
    });
  });

  document.querySelectorAll('.enable-user-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      enableUser(e.currentTarget.dataset.userId);
    });
  });

  document.querySelectorAll('.delete-user-btn').forEach((button) => {
    button.addEventListener('click', (e) => {
      deleteUser(e.currentTarget.dataset.userId);
    });
  });
}
