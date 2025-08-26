// frontend/src/manage_settings.js
/**
 * @fileoverview Frontend JavaScript for the global settings management page.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

export function initializeManageSettingsPage() {
    const settingsFormContainer = document.getElementById('settings-form-container');
    const reloadButton = document.getElementById('reload-settings-btn');
    const loader = document.getElementById('settings-loader');
    const settingsFormSection = document.getElementById('settings-form-section');

    if (!settingsFormSection || !settingsFormContainer || !reloadButton || !loader) {
        console.error("manage_settings.js: Critical elements not found.");
        return;
    }

    const showLoader = (isLoading) => {
        loader.style.display = isLoading ? 'block' : 'none';
        settingsFormSection.style.display = isLoading ? 'none' : 'block';
        if (isLoading) settingsFormContainer.innerHTML = '';
    };

    const showError = (message) => {
        showLoader(false);
        settingsFormSection.style.display = 'none';
        showStatusMessage(message, 'error');
    };

    const renderSettings = (data) => {
        settingsFormContainer.innerHTML = '';
        let totalFieldsRendered = 0;

        Object.keys(data).sort().forEach(categoryKey => {
            if (typeof data[categoryKey] !== 'object' || data[categoryKey] === null) return;

            const fieldset = document.createElement('fieldset');
            const legend = document.createElement('legend');
            legend.textContent = categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1);
            fieldset.appendChild(legend);

            let categoryFieldsAdded = 0;
            Object.keys(data[categoryKey]).sort().forEach(settingKey => {
                const formGroup = createFormElement(`${categoryKey}.${settingKey}`, settingKey, data[categoryKey][settingKey]);
                if (formGroup) {
                    fieldset.appendChild(formGroup);
                    categoryFieldsAdded++;
                }
            });

            if (categoryFieldsAdded > 0) {
                settingsFormContainer.appendChild(fieldset);
                totalFieldsRendered += categoryFieldsAdded;
            }
        });

        if (totalFieldsRendered === 0) showError("No configurable settings.");
    };

    const createFormElement = (fullKey, labelText, value) => {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';
        const label = document.createElement('label');
        label.htmlFor = fullKey;
        label.textContent = (labelText.charAt(0).toUpperCase() + labelText.slice(1)).replace(/_/g, ' ');
        let inputElement;

        if (typeof value === 'boolean') {
            // simplified toggle creation
            formGroup.classList.add('form-group-toggle-container');
            inputElement = document.createElement('input');
            inputElement.type = 'checkbox';
            inputElement.checked = value;
            inputElement.className = 'toggle-input';
            const switchLabel = document.createElement('label');
            switchLabel.htmlFor = fullKey;
            switchLabel.className = 'toggle-switch';
            formGroup.append(label, inputElement, switchLabel);
        } else {
            formGroup.appendChild(label);
            inputElement = document.createElement('input');
            inputElement.className = 'form-input';
            if (Array.isArray(value)) {
                inputElement.type = 'text';
                inputElement.value = value.join(', ');
                inputElement.placeholder = 'comma, separated, list';
            } else {
                inputElement.type = typeof value === 'number' ? 'number' : 'text';
                inputElement.value = value;
            }
            formGroup.appendChild(inputElement);
        }
        
        inputElement.id = fullKey;
        inputElement.name = fullKey;
        inputElement.addEventListener('change', handleInputChange);
        return formGroup;
    };

    async function handleInputChange(event) {
        const input = event.target;
        let value = input.type === 'checkbox' ? input.checked : (input.type === 'number' ? parseFloat(input.value) : input.value);
        if (input.placeholder === 'comma, separated, list') {
            value = value.split(',').map(s => s.trim()).filter(Boolean);
        }
        await sendServerActionRequest(null, '/api/settings', 'POST', { key: input.name, value }, null);
    }

    reloadButton.addEventListener('click', async () => {
        if (confirm('Discard unsaved changes and reload from file?')) {
            const result = await sendServerActionRequest(null, '/api/settings/reload', 'POST', null, reloadButton);
            if (result && result.status === 'success') {
                await loadAndRenderSettings();
            }
        }
    });

    const loadAndRenderSettings = async () => {
        showLoader(true);
        try {
            const result = await sendServerActionRequest(null, '/api/settings', 'GET', null, null, true);
            if (result && result.status === 'success' && result.settings) {
                renderSettings(result.settings);
            } else {
                showError(result?.message || 'Error loading settings.');
            }
        } catch (error) {
            showError(`Client-side error: ${error.message}`);
        } finally {
            showLoader(false);
        }
    };

    loadAndRenderSettings();
}
