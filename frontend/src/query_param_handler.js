// frontend/src/query_param_handler.js
/**
 * @fileoverview Handles reading URL query parameters and displaying status messages.
 */

import { showStatusMessage } from './utils.js';

export function handleQueryParameters() {
  const urlParams = new URLSearchParams(window.location.search);
  const message = urlParams.get('message');
  const category = urlParams.get('category');

  if (message) {
    if (typeof showStatusMessage === 'function') {
      showStatusMessage(message, category);
    } else {
      console.warn('showStatusMessage function not found. Cannot display message from URL.');
    }
    // Clean the URL
    const newUrl = new URL(window.location.href);
    newUrl.searchParams.delete('message');
    newUrl.searchParams.delete('category');
    window.history.replaceState({}, document.title, newUrl.toString());
  }
}
