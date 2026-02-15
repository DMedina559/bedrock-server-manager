/**
 * @fileoverview User management page scripts.
 */

import * as UsersApi from "./users_api.js";
import { handleApiAction, showStatusMessage } from "./ui_utils.js";

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(
    () => {
      showStatusMessage("Copied to clipboard", "success");
    },
    (err) => {
      console.error("Could not copy text: ", err);
      showStatusMessage("Could not copy text.", "error");
    },
  );
}

function handleGenerateToken(buttonElement) {
  const form = document.getElementById("generate-token-form");
  if (!form) return;

  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());

  handleApiAction(buttonElement, async () => {
    const response = await UsersApi.generateRegistrationToken(data);
    if (response && response.status === "success" && response.redirect_url) {
      window.location.href = response.redirect_url;
    } else if (response && response.status === "success") {
      // Fallback if no redirect, though the backend seems to redirect
      window.location.reload();
    }
    return response;
  });
}

function handleDisableUser(buttonElement) {
  const userId = buttonElement.dataset.userId;
  if (confirm("Are you sure you want to disable this user?")) {
    handleApiAction(buttonElement, async () => {
      const response = await UsersApi.disableUser(userId);
      if (response && response.status === "success") {
        window.location.reload();
      }
      return response;
    });
  }
}

function handleEnableUser(buttonElement) {
  const userId = buttonElement.dataset.userId;
  if (confirm("Are you sure you want to enable this user?")) {
    handleApiAction(buttonElement, async () => {
      const response = await UsersApi.enableUser(userId);
      if (response && response.status === "success") {
        window.location.reload();
      }
      return response;
    });
  }
}

function handleDeleteUser(buttonElement) {
  const userId = buttonElement.dataset.userId;
  if (confirm("Are you sure you want to delete this user?")) {
    handleApiAction(buttonElement, async () => {
      const response = await UsersApi.deleteUser(userId);
      if (response && response.status === "success") {
        window.location.reload();
      }
      return response;
    });
  }
}

function handleUpdateUserRole(buttonElement) {
  const userId = buttonElement.dataset.userId;
  const selectElement = document.getElementById(`role-${userId}`);
  const role = selectElement ? selectElement.value : null;

  if (!role) {
    showStatusMessage("Error: Role not selected.", "error");
    return;
  }

  handleApiAction(buttonElement, async () => {
    const response = await UsersApi.updateUserRole(userId, role);
    if (response && response.status === "success") {
      window.location.reload();
    }
    return response;
  });
}

export function initializeUsersPage() {
  const generateTokenBtn = document.getElementById("generate-token-btn");
  if (generateTokenBtn) {
    generateTokenBtn.addEventListener("click", (e) =>
      handleGenerateToken(e.currentTarget),
    );
  }

  document.querySelectorAll(".copy-link-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      // The link is in the data-link attribute
      const link = e.currentTarget.dataset.link;
      if (link) copyToClipboard(link);
    });
  });

  document.querySelectorAll(".update-role-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      handleUpdateUserRole(e.currentTarget);
    });
  });

  document.querySelectorAll(".disable-user-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      handleDisableUser(e.currentTarget);
    });
  });

  document.querySelectorAll(".enable-user-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      handleEnableUser(e.currentTarget);
    });
  });

  document.querySelectorAll(".delete-user-btn").forEach((button) => {
    button.addEventListener("click", (e) => {
      handleDeleteUser(e.currentTarget);
    });
  });
}
