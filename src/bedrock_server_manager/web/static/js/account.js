// bedrock_server_manager/web/static/js/account.js
/**
 * @fileoverview Frontend JavaScript for the account management page.
 * Handles theme selection and other account-related settings.
 * Depends on functions from utils.js (showStatusMessage, sendServerActionRequest).
 */

if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first in your base.html template.");
}

document.addEventListener('DOMContentLoaded', () => {
    // --- Theme Selector Logic ---
    const themeSelect = document.getElementById('theme-select');
    if (themeSelect) {
        // Populate theme options
        sendServerActionRequest(null, '/api/themes', 'GET', null, null, true).then(themes => {
            if (themes) {
                Object.keys(themes).forEach(themeName => {
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
                const themePath = await sendServerActionRequest(null, `/api/themes`, 'GET', null, null, true);
                themeStylesheet.href = themePath[newTheme];
            }

            // Save the new theme setting for the user
            await sendServerActionRequest(null, '/api/account/theme', 'POST', { theme: newTheme }, null);
        });
    }
});
