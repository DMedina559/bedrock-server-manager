/**
 * @fileoverview Frontend JavaScript for the account management page.
 * Handles theme selection and other account-related settings.
 */

import {
  getUserProfile,
  updateUserProfile,
  changePassword as changePasswordApi,
  getThemes,
  setUserTheme,
} from "./account_api.js";
import { showStatusMessage, handleApiAction } from "./ui_utils.js";

async function loadUserProfile() {
  try {
    const response = await getUserProfile();
    if (response) {
      const fullNameInput = document.getElementById("full_name");
      const emailInput = document.getElementById("email");
      if (fullNameInput) fullNameInput.value = response.full_name || "";
      if (emailInput) emailInput.value = response.email || "";
    }
  } catch (error) {
    console.error("Failed to load user profile:", error);
    showStatusMessage("Failed to load user profile.", "error");
  }
}

async function handleChangePassword(formElement) {
  const currentPassword = formElement.elements["current_password"].value;
  const newPassword = formElement.elements["new_password"].value;
  const confirmNewPassword = formElement.elements["confirm_new_password"].value;

  if (newPassword !== confirmNewPassword) {
    showStatusMessage("New passwords do not match.", "error");
    return;
  }

  const data = {
    current_password: currentPassword,
    new_password: newPassword,
  };

  const submitButton = formElement.querySelector('button[type="submit"]');

  await handleApiAction(submitButton, async () => {
    const response = await changePasswordApi(data);
    if (response && response.status === "success") {
      formElement.reset();
    }
    return response;
  });
}

async function handleUpdateProfile(formElement) {
  const fullName = formElement.elements["full_name"].value;
  const email = formElement.elements["email"].value;

  const data = {
    full_name: fullName,
    email: email,
  };

  const submitButton = formElement.querySelector('button[type="submit"]');

  await handleApiAction(submitButton, async () => {
    return await updateUserProfile(data);
  });
}

export function initializeAccountPage() {
  loadUserProfile();

  // --- Theme Selector Logic ---
  const themeSelect = document.getElementById("theme-select");
  if (themeSelect) {
    // Populate theme options
    getThemes()
      .then((themes) => {
        if (themes) {
          Object.keys(themes).forEach((themeName) => {
            const option = document.createElement("option");
            option.value = themeName;
            option.textContent =
              themeName.charAt(0).toUpperCase() + themeName.slice(1);
            themeSelect.appendChild(option);
          });
        }

        const currentTheme = themeSelect.dataset.currentTheme;
        if (currentTheme) {
          themeSelect.value = currentTheme;
        }
      })
      .catch((err) => console.error("Failed to load themes:", err));

    themeSelect.addEventListener("change", async (event) => {
      const newTheme = event.target.value;
      const themeStylesheet = document.getElementById("theme-stylesheet");

      try {
        if (themeStylesheet) {
          const themes = await getThemes();
          if (themes && themes[newTheme]) {
            themeStylesheet.href = themes[newTheme];
          }
        }

        // Save the new theme setting for the user
        await setUserTheme(newTheme);
      } catch (error) {
        console.error("Failed to set theme:", error);
        showStatusMessage("Failed to save theme preference.", "warning");
      }
    });
  }

  // --- Sidebar Navigation ---
  // This logic is purely UI navigation (tab switching) and doesn't involve API calls.
  const navLinks = document.querySelectorAll(".sidebar-nav .nav-link");
  const contentSections = document.querySelectorAll(
    ".main-content .content-section",
  );

  navLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      if (!link.getAttribute("data-target")) {
        return;
      }

      event.preventDefault();
      const targetId = link.getAttribute("data-target");

      navLinks.forEach((navLink) => navLink.classList.remove("active"));
      contentSections.forEach((section) => section.classList.remove("active"));

      link.classList.add("active");
      const targetSection = document.getElementById(targetId);
      if (targetSection) {
        targetSection.classList.add("active");
      }
    });
  });

  // Attach event listeners for the forms
  const changePasswordForm = document.getElementById("change-password-form");
  if (changePasswordForm) {
    changePasswordForm.addEventListener("submit", (event) => {
      event.preventDefault();
      handleChangePassword(changePasswordForm);
    });
  }

  const profileForm = document.getElementById("profile-form");
  if (profileForm) {
    profileForm.addEventListener("submit", (event) => {
      event.preventDefault();
      handleUpdateProfile(profileForm);
    });
  }
}
