// frontend/src/server_settings.js
/**
 * @fileoverview Frontend JavaScript for the server-specific settings management page.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

export function initializeServerSettingsPage() {
  const settingsFormContainer = document.getElementById('settings-form-container');
  const settingsSidebar = document.getElementById('settings-sidebar');
  const loader = document.getElementById('settings-loader');
  const settingsFormSection = document.getElementById('settings-form-section');

  if (!settingsFormSection || !settingsFormContainer || !settingsSidebar || !loader) {
    console.error('server_settings.js: Critical elements not found.');
    return;
  }

  const getServerNameFromPath = () => {
    const pathParts = window.location.pathname.split('/');
    // Expected URL: /servers/{server_name}/settings
    const serverNameIndex = pathParts.indexOf('servers') + 1;
    return pathParts.length > serverNameIndex ? pathParts[serverNameIndex] : null;
  };

  const serverName = getServerNameFromPath();
  if (!serverName) {
    showError('Could not determine server name from URL.');
    return;
  }

  const showLoader = (isLoading) => {
    loader.style.display = isLoading ? 'block' : 'none';
    settingsFormSection.style.display = isLoading ? 'none' : 'block';
    if (isLoading) {
        settingsFormContainer.innerHTML = '';
        settingsSidebar.innerHTML = '';
    }
  };

  const showError = (message) => {
    showLoader(false);
    settingsFormSection.style.display = 'none';
    showStatusMessage(message, 'error');
  };

  const renderSettings = (data) => {
    settingsFormContainer.innerHTML = '';
    settingsSidebar.innerHTML = '';
    let totalFieldsRendered = 0;

    // Define the order of categories
    const categoryOrder = ['server_info', 'settings', 'custom'];

    categoryOrder.forEach((categoryKey) => {
        if (!data.hasOwnProperty(categoryKey) || typeof data[categoryKey] !== 'object' || data[categoryKey] === null) return;

        const fieldset = document.createElement('fieldset');
        fieldset.id = `category-${categoryKey}`;
        const legend = document.createElement('legend');
        legend.textContent = categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1);
        fieldset.appendChild(legend);

        const link = document.createElement('a');
        link.href = `#category-${categoryKey}`;
        link.className = 'nav-link';
        link.textContent = legend.textContent;
        link.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.sidebar-nav .nav-link').forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            fieldset.scrollIntoView({ behavior: 'smooth' });
        });
        settingsSidebar.appendChild(link);

        let categoryFieldsAdded = 0;
        Object.keys(data[categoryKey])
          .sort()
          .forEach((settingKey) => {
            const formGroup = createFormElement(
              `${categoryKey}.${settingKey}`,
              settingKey,
              data[categoryKey][settingKey],
            );
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


    if (totalFieldsRendered === 0) showError('No configurable settings found for this server.');
  };

  const createFormElement = (fullKey, labelText, value) => {
    const formGroup = document.createElement('div');
    formGroup.className = 'form-group';
    const label = document.createElement('label');
    label.htmlFor = fullKey;
    label.textContent = (labelText.charAt(0).toUpperCase() + labelText.slice(1)).replace(/_/g, ' ');
    let inputElement;

    if (typeof value === 'boolean') {
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
    let value =
      input.type === 'checkbox' ? input.checked : input.type === 'number' ? parseFloat(input.value) : input.value;
    if (input.placeholder === 'comma, separated, list') {
      value = value
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    }
    await sendServerActionRequest(null, `/api/servers/${serverName}/settings`, 'POST', { key: input.name, value }, null);
  }

  const loadAndRenderSettings = async () => {
    showLoader(true);
    try {
      const result = await sendServerActionRequest(null, `/api/servers/${serverName}/settings`, 'GET', null, null, true);
      if (result && result.status === 'success' && result.settings) {
        renderSettings(result.settings);
      } else {
        showError(result?.message || 'Error loading server settings.');
      }
    } catch (error) {
      showError(`Client-side error: ${error.message}`);
    } finally {
      showLoader(false);
    }
  };

  loadAndRenderSettings();
}
