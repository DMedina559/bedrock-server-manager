// frontend/src/account.js
/**
 * @fileoverview Frontend JavaScript for the account management page.
 * Handles theme selection and other account-related settings.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

function loadUserProfile() {
  sendServerActionRequest(null, '/api/account', 'GET', null, null, true).then((response) => {
    if (response) {
      document.getElementById('full_name').value = response.full_name || '';
      document.getElementById('email').value = response.email || '';
    }
  });
}

function changePassword() {
  const form = document.getElementById('change-password-form');
  const currentPassword = form.elements['current_password'].value;
  const newPassword = form.elements['new_password'].value;
  const confirmNewPassword = form.elements['confirm_new_password'].value;

  if (newPassword !== confirmNewPassword) {
    showStatusMessage('New passwords do not match.', 'error');
    return;
  }

  const data = {
    current_password: currentPassword,
    new_password: newPassword,
  };

  sendServerActionRequest(null, '/api/account/change-password', 'POST', data).then((response) => {
    if (response && response.status === 'success') {
      form.reset();
    }
  });
}

function updateProfile() {
  const form = document.getElementById('profile-form');
  const fullName = form.elements['full_name'].value;
  const email = form.elements['email'].value;

  const data = {
    full_name: fullName,
    email: email,
  };

  sendServerActionRequest(null, '/api/account/profile', 'POST', data);
}

export function initializeAccountPage() {
  loadUserProfile();
  // --- Theme Selector Logic ---
  const themeSelect = document.getElementById('theme-select');
  if (themeSelect) {
    // Populate theme options
    sendServerActionRequest(null, '/api/themes', 'GET', null, null, true).then((themes) => {
      if (themes) {
        Object.keys(themes).forEach((themeName) => {
          const option = document.createElement('option');
          option.value = themeName;
          option.textContent = themeName.charAt(0).toUpperCase() + themeName.slice(1);
          themeSelect.appendChild(option);
        });
      }

      // Set initial value from the data attribute on the select element
      const currentTheme = themeSelect.dataset.currentTheme;
      if (currentTheme) {
        themeSelect.value = currentTheme;
      }
    });

    themeSelect.addEventListener('change', async (event) => {
      const newTheme = event.target.value;
      const themeStylesheet = document.getElementById('theme-stylesheet');
      if (themeStylesheet) {
        const themes = await sendServerActionRequest(null, `/api/themes`, 'GET', null, null, true);
        if (themes) {
          themeStylesheet.href = themes[newTheme];
        }
      }

      // Save the new theme setting for the user
      await sendServerActionRequest(null, '/api/account/theme', 'POST', { theme: newTheme }, null);
    });
  }

  // --- Sidebar Navigation ---
  const navLinks = document.querySelectorAll('.sidebar-nav .nav-link');
  const contentSections = document.querySelectorAll('.main-content .content-section');

  navLinks.forEach((link) => {
    link.addEventListener('click', (event) => {
      // Check if it's a link to another page
      if (!link.getAttribute('data-target')) {
        return;
      }

      event.preventDefault();
      const targetId = link.getAttribute('data-target');

      // Deactivate all links and sections
      navLinks.forEach((navLink) => navLink.classList.remove('active'));
      contentSections.forEach((section) => section.classList.remove('active'));

      // Activate the clicked link and target section
      link.classList.add('active');
      const targetSection = document.getElementById(targetId);
      if (targetSection) {
        targetSection.classList.add('active');
      }
    });
  });

  // Attach event listeners for the forms
  const changePasswordForm = document.getElementById('change-password-form');
  if (changePasswordForm) {
    changePasswordForm.addEventListener('submit', (event) => {
      event.preventDefault();
      changePassword();
    });
  }

  const profileForm = document.getElementById('profile-form');
  if (profileForm) {
    profileForm.addEventListener('submit', (event) => {
      event.preventDefault();
      updateProfile();
    });
  }
}
