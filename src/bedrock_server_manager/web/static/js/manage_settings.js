// bedrock_server_manager/web/static/js/manage_settings.js
/**
 * @fileoverview Frontend JavaScript for the global settings management page.
 * Dynamically builds a form from API data and handles saving changes.
 * Depends on functions from utils.js (showStatusMessage, sendServerActionRequest).
 */

if (typeof sendServerActionRequest === 'undefined' || typeof showStatusMessage === 'undefined') {
    console.error("Error: Missing required functions from utils.js. Ensure utils.js is loaded first in your base.html template.");
}

document.addEventListener('DOMContentLoaded', () => {
    const settingsFormContainer = document.getElementById('settings-form-container');
    const reloadButton = document.getElementById('reload-settings-btn');
    const loader = document.getElementById('settings-loader');
    const settingsFormSection = document.getElementById('settings-form-section');

    if (!settingsFormSection || !settingsFormContainer || !reloadButton || !loader) {
        console.error("manage_settings.js: Critical container, button, or loader element not found on the page.");
        return;
    }

    // --- Main Function to Fetch and Render Settings ---
    const loadAndRenderSettings = async () => {
        showLoader(true);
        try {
            // Refactored to use sendServerActionRequest
            const result = await sendServerActionRequest(null, '/api/settings', 'GET', null, null);

            if (result && result.status === 'success' && result.settings) { // Changed result.data to result.settings
                renderSettings(result.settings); // Changed result.data to result.settings
            } else {
                // Error message should be handled by sendServerActionRequest, 
                // but showError provides a fallback and specific UI handling.
                const errorMsg = (result && result.message) ? result.message : 'Unknown error loading settings.';
                showError('Failed to load settings: ' + errorMsg);
            }
        } catch (error) { // Catch errors from this script's logic, not from sendServerActionRequest's fetch
            console.error('Client-side error in loadAndRenderSettings:', error);
            showError(`An error occurred while fetching settings: ${error.message}`);
        } finally {
            showLoader(false);
        }
    };

    // --- UI Helper Functions ---
    const showLoader = (isLoading) => {
        loader.style.display = isLoading ? 'block' : 'none';
        settingsFormSection.style.display = isLoading ? 'none' : 'block';
        if (isLoading) {
            settingsFormContainer.innerHTML = '';
        }
    };

    const showError = (message) => {
        loader.style.display = 'none';
        settingsFormSection.style.display = 'none'; // Hide form section on error
        settingsFormContainer.innerHTML = ''; // Clear potentially partially rendered form
        showStatusMessage(message, 'error'); // Use the global status message display
    };

    // --- Rendering Logic ---
    const renderSettings = (data) => {
        settingsFormContainer.innerHTML = '';
        const excludedKeys = ['config_version'];
        let totalFieldsRendered = 0;

        Object.keys(data).sort().forEach(categoryKey => {
            if (excludedKeys.includes(categoryKey) || typeof data[categoryKey] !== 'object' || data[categoryKey] === null) return;

            const fieldset = document.createElement('fieldset');
            const legend = document.createElement('legend');
            legend.textContent = categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1);
            fieldset.appendChild(legend);

            const settingsObject = data[categoryKey];
            let categoryFieldsAdded = 0;

            Object.keys(settingsObject).sort().forEach(settingKey => {
                const fullKey = `${categoryKey}.${settingKey}`;
                const value = settingsObject[settingKey];
                const formGroup = createFormElement(fullKey, settingKey, value);

                if (formGroup) {
                    fieldset.appendChild(formGroup);
                    categoryFieldsAdded++;
                    totalFieldsRendered++;
                }
            });

            if (categoryFieldsAdded > 0) {
                settingsFormContainer.appendChild(fieldset);
            }
        });

        if (totalFieldsRendered === 0) {
            showError("No configurable settings available."); // Uses the updated showError
        }
    };

    const createFormElement = (fullKey, labelText, value) => {
        try {
            const formGroup = document.createElement('div');
            formGroup.className = 'form-group';

            const label = document.createElement('label');
            label.htmlFor = fullKey;
            label.className = 'form-label';
            label.textContent = (labelText.charAt(0).toUpperCase() + labelText.slice(1)).replace(/_/g, ' ');

            let inputElement = null;
            const inputType = typeof value;

            if (inputType === 'boolean') {
                formGroup.classList.add('form-group-toggle-container');
                const labelGroup = document.createElement('div');
                labelGroup.className = 'form-label-group';
                labelGroup.appendChild(label);

                const toggleSwitchContainer = document.createElement('div');
                toggleSwitchContainer.className = 'toggle-switch-container';

                const input = document.createElement('input');
                input.type = 'checkbox';
                input.checked = value;
                input.className = 'toggle-input';
                input.id = fullKey;
                input.name = fullKey;

                const switchVisualLabel = document.createElement('label');
                switchVisualLabel.htmlFor = fullKey;
                switchVisualLabel.className = 'toggle-switch';

                toggleSwitchContainer.appendChild(input);
                toggleSwitchContainer.appendChild(switchVisualLabel);

                formGroup.appendChild(labelGroup);
                formGroup.appendChild(toggleSwitchContainer);
                inputElement = input;
            } else {
                formGroup.appendChild(label);

                if (Array.isArray(value)) {
                    inputElement = document.createElement('input');
                    inputElement.type = 'text';
                    inputElement.value = value.join(', ');
                    inputElement.placeholder = 'comma, separated, list';
                } else if (inputType === 'number') {
                    inputElement = document.createElement('input');
                    inputElement.type = 'number';
                    inputElement.value = value;
                } else if (inputType === 'string') {
                    inputElement = document.createElement('input');
                    inputElement.type = 'text';
                    inputElement.value = value;
                }

                if (inputElement) {
                    inputElement.className = 'form-input';
                    inputElement.id = fullKey;
                    inputElement.name = fullKey;
                    formGroup.appendChild(inputElement);
                } else {
                    const span = document.createElement('span');
                    span.textContent = `[Value type "${inputType}" not supported]`;
                    formGroup.appendChild(span);
                }
            }

            if (inputElement) {
                inputElement.addEventListener('change', handleInputChange);
            }

            return formGroup;
        } catch (e) {
            console.error(`createFormElement: FATAL Error building element for key '${fullKey}':`, e);
            return null;
        }
    };

    // --- Event Handlers ---
    async function handleInputChange(event) {
        const input = event.target;
        const key = input.name;
        let value = input.value;
        if (input.type === 'checkbox') value = input.checked;
        else if (input.type === 'number') value = parseFloat(value);
        else if (input.placeholder === 'comma, separated, list') value = value.split(',').map(s => s.trim()).filter(Boolean);

        // Use sendServerActionRequest for POST
        await sendServerActionRequest(null, '/api/settings', 'POST', { key, value }, null); // No specific button to disable for individual field changes
    }

    reloadButton.addEventListener('click', async () => {
        if (!confirm('This will discard any unsaved changes and reload the settings from the configuration file. Are you sure?')) return;

        // Use sendServerActionRequest for POST
        const result = await sendServerActionRequest(null, '/api/settings/reload', 'POST', null, reloadButton);

        if (result && result.status === 'success') {
            await loadAndRenderSettings(); // Reload and render settings on success
        }
    });

    // --- Initial Load ---
    loadAndRenderSettings();
});