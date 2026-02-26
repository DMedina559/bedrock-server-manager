// frontend/src/setup.js
import { createFirstUser } from "./setup_api.js";
import { showStatusMessage, handleApiAction } from "./ui_utils.js";

function submitForm() {
  const form = document.getElementById("setup-form");
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  const confirm_password = document.getElementById("confirm_password").value;

  if (!username || !password || !confirm_password) {
    showStatusMessage("All fields are required.", "error");
    return;
  }

  if (password !== confirm_password) {
    showStatusMessage("Passwords do not match.", "error");
    return;
  }

  const submitButton = form.querySelector('button[type="submit"]');
  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());

  handleApiAction(submitButton, async () => {
    const response = await createFirstUser(data);
    if (response && response.status === "success") {
      window.location.href = response.redirect_url;
    }
    return response;
  });
}

export function initializeSetupPage() {
  const setupForm = document.getElementById("setup-form");
  if (setupForm) {
    setupForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submitForm();
    });
  }
}
