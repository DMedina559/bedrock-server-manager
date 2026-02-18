/**
 * @fileoverview UI utility functions for managing status messages and interactive elements.
 * Separates DOM manipulation from business logic.
 */

/**
 * Displays a status message dynamically in a designated area on the page.
 * The message automatically fades out and clears after a set duration.
 * Handles cases where the status area element might be missing.
 *
 * @param {string} message - The text content of the message to display.
 * @param {string} [type='info'] - The type of message, influencing styling.
 *                                 Expected values: 'info', 'success', 'warning', 'error'.
 */
export function showStatusMessage(message, type = "info") {
  const functionName = "showStatusMessage";
  console.log(
    `${functionName}: Displaying message (Type: ${type}): "${message}"`,
  );

  const area = document.getElementById("status-message-area");
  if (!area) {
    console.warn(
      `${functionName}: Element '#status-message-area' not found. Falling back to standard alert.`,
    );
    alert(`${type.toUpperCase()}: ${message}`);
    return;
  }

  area.className = `message-box message-${type}`;
  area.textContent = message;
  area.style.transition = "";
  area.style.opacity = "1";

  const messageId = Date.now() + Math.random();
  area.dataset.currentMessageId = messageId;

  setTimeout(() => {
    if (area.dataset.currentMessageId === String(messageId)) {
      area.style.transition = "opacity 0.5s ease-out";
      area.style.opacity = "0";

      setTimeout(() => {
        if (
          area.dataset.currentMessageId === String(messageId) &&
          area.style.opacity === "0"
        ) {
          area.textContent = "";
          area.className = "message-box";
          area.style.transition = "";
          delete area.dataset.currentMessageId;
        }
      }, 500);
    }
  }, 5000);
}

/**
 * Wraps an asynchronous action (typically an API call) with UI feedback:
 * - Disables the trigger element (button/link) during execution.
 * - Shows a loading message (optional).
 * - Handles success/error messages automatically.
 *
 * @param {HTMLElement|null} element - The element to disable/enable.
 * @param {Function} asyncFn - The async function to execute. Must return a Promise.
 * @param {string} [loadingMessage] - Optional message to show while pending.
 * @returns {Promise<any>} The result of the async function, or null if it failed.
 */
export async function handleApiAction(
  element,
  asyncFn,
  loadingMessage = "Processing...",
) {
  if (element) {
    element.disabled = true;
    element.classList.add("disabled"); // for custom styling if needed
  }

  if (loadingMessage) {
    showStatusMessage(loadingMessage, "info");
  }

  try {
    const result = await asyncFn();

    // Check for "confirm_needed" status which is a special application flow
    if (
      result &&
      typeof result === "object" &&
      result.status === "confirm_needed"
    ) {
      return result;
    }

    // Success handling
    if (result && result.message && result.status !== "error") {
      showStatusMessage(result.message, "success");
    } else if (result && result.status === "success") {
      showStatusMessage("Action completed successfully.", "success");
    }

    return result;
  } catch (error) {
    console.error("Action failed:", error);
    let message = error.message || "An unexpected error occurred.";
    if (error.name === "ApiError") {
      message = error.message; // Use the specific API error message
    }
    showStatusMessage(message, "error");
    return null;
  } finally {
    if (element) {
      element.disabled = false;
      element.classList.remove("disabled");
    }
  }
}
