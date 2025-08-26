// frontend/src/install_config.js
/**
 * @fileoverview Frontend JavaScript for handling the multi-step server installation
 * and configuration process.
 */

import { sendServerActionRequest, showStatusMessage } from './utils.js';

function _clearValidationErrors() {
    const errorArea = document.getElementById('validation-error-area');
    if (errorArea) {
        errorArea.innerHTML = '';
        errorArea.style.display = 'none';
    }
    document.querySelectorAll('.validation-error').forEach(el => el.textContent = '');
}

function _handleInstallSuccessNavigation(apiResponseData) {
    const nextUrl = apiResponseData?.next_step_url;
    const message = apiResponseData?.message || "Server installed successfully!";
    if (nextUrl) {
        showStatusMessage(`${message} Proceeding to configuration...`, "success");
        setTimeout(() => window.location.href = nextUrl, 1500);
    } else {
        showStatusMessage("Server installed, but next step URL is missing.", "warning");
    }
}

function pollTaskStatus(taskId, successCallback) {
    const intervalId = setInterval(async () => {
        try {
            const response = await fetch(`/api/tasks/status/${taskId}`);
            if (!response.ok) {
                clearInterval(intervalId);
                showStatusMessage(`Error checking task status: ${response.statusText}`, 'error');
                return;
            }
            const data = await response.json();
            if (data.status === 'success') {
                clearInterval(intervalId);
                if (successCallback) successCallback(data.result);
                else showStatusMessage(data.message || 'Task completed successfully.', 'success');
            } else if (data.status === 'error') {
                clearInterval(intervalId);
                showStatusMessage(`Task failed: ${data.message}`, 'error');
            } else if (data.message) {
                showStatusMessage(`Task in progress: ${data.message}`, 'info');
            }
        } catch (error) {
            clearInterval(intervalId);
            showStatusMessage(`Error polling task status: ${error.message}`, 'error');
        }
    }, 2000);
}

export async function triggerInstallServer(buttonElement) {
    const serverNameInput = document.getElementById('install-server-name');
    const serverVersionInput = document.getElementById('install-server-version');
    const serverName = serverNameInput.value.trim();
    const serverVersion = serverVersionInput.value.trim() || 'LATEST';

    if (!serverName) return showStatusMessage('Server name cannot be empty.', 'warning');
    if (!/^[a-zA-Z0-9_-]+$/.test(serverName)) return showStatusMessage('Server name has invalid characters.', 'error');

    _clearValidationErrors();

    const requestBody = { server_name: serverName, server_version: serverVersion, overwrite: false };
    if (serverVersion.toUpperCase() === 'CUSTOM') {
        requestBody.server_zip_path = document.getElementById('custom-zip-selector').value;
    }

    const initialResponse = await sendServerActionRequest(null, '/api/server/install', 'POST', requestBody, buttonElement);

    if (initialResponse) {
        if (initialResponse.status === 'confirm_needed') {
            if (confirm(initialResponse.message)) {
                const finalResponse = await sendServerActionRequest(null, '/api/server/install', 'POST', { ...requestBody, overwrite: true }, buttonElement);
                if (finalResponse && finalResponse.status === 'pending') {
                    pollTaskStatus(finalResponse.task_id, _handleInstallSuccessNavigation);
                }
            } else {
                showStatusMessage("Installation cancelled.", "info");
                if (buttonElement) buttonElement.disabled = false;
            }
        } else if (initialResponse.status === 'pending') {
            pollTaskStatus(initialResponse.task_id, _handleInstallSuccessNavigation);
        }
    }
}

export async function saveProperties(buttonElement, serverName, isNewInstall) {
    const propertiesData = {};
    const formElements = document.querySelectorAll('.properties-config-section .form-input, .properties-config-section .toggle-input, .properties-config-section input[type="hidden"]');
    formElements.forEach(el => {
        if (!el.name) return;
        if (el.type === 'checkbox' && el.classList.contains('toggle-input')) {
            if (el.checked) propertiesData[el.name.replace('-cb', '')] = 'true';
        } else if (el.type === 'hidden') {
            if (!el.disabled) propertiesData[el.name] = el.value;
        } else if (!el.classList.contains('toggle-input')) {
            propertiesData[el.name] = el.value;
        }
    });

    _clearValidationErrors();
    const response = await sendServerActionRequest(null, `/api/server/${serverName}/properties/set`, 'POST', { properties: propertiesData }, buttonElement);

    if (response && response.status === 'success') {
        const message = response.message || "Properties saved.";
        if (isNewInstall) {
            showStatusMessage(`${message} Proceeding to Allowlist...`, "success");
            setTimeout(() => window.location.href = `/server/${encodeURIComponent(serverName)}/configure_allowlist?new_install=True`, 1500);
        } else {
            showStatusMessage(message, "success");
        }
    }
}

export async function savePermissions(buttonElement, serverName, isNewInstall) {
    const permissions = Array.from(document.querySelectorAll('select.permission-select')).map(select => ({
        xuid: select.dataset.xuid,
        name: select.closest('tr').querySelector('.player-name').textContent.trim(),
        permission_level: select.value
    }));

    _clearValidationErrors();
    const response = await sendServerActionRequest(null, `/api/server/${serverName}/permissions/set`, 'PUT', { permissions }, buttonElement);

    if (response && response.status === 'success') {
        const message = response.message || "Permissions saved.";
        if (isNewInstall) {
            showStatusMessage(`${message} Proceeding to Service Config...`, "success");
            setTimeout(() => window.location.href = `/server/${encodeURIComponent(serverName)}/configure_service?new_install=True`, 1500);
        } else {
            showStatusMessage(message, "success");
        }
    }
}

export async function saveServiceSettings(buttonElement, serverName, currentOs, isNewInstall) {
    const settings = {
        autoupdate: document.getElementById('service-autoupdate-cb').checked,
        autostart: document.getElementById('service-autostart-cb').checked,
    };
    const startAfter = isNewInstall && document.getElementById('service-start-server').checked;

    _clearValidationErrors();
    const saveResponse = await sendServerActionRequest(null, `/api/server/${serverName}/service/update`, 'POST', settings, buttonElement);

    if (saveResponse && ['success', 'success_with_warning'].includes(saveResponse.status)) {
        const message = saveResponse.message || "Service settings saved.";
        if (startAfter) {
            showStatusMessage(`${message} Starting server...`, "info");
            const startResponse = await sendServerActionRequest(serverName, 'start', 'POST', null, buttonElement);
            if (startResponse && startResponse.status === 'success') {
                showStatusMessage("Server started! Installation complete. Redirecting...", "success");
                setTimeout(() => window.location.href = "/", 2000);
            } else {
                showStatusMessage(`Settings saved, but server failed to start: ${startResponse?.message || 'Unknown error'}`, "warning");
            }
        } else if (isNewInstall) {
            showStatusMessage(`${message} Installation complete! Redirecting...`, "success");
            setTimeout(() => window.location.href = "/", 1500);
        } else {
            showStatusMessage(message, "success");
        }
    }
}

export async function checkCustomVersion(version) {
    const customZipGroup = document.getElementById('custom-zip-selector-group');
    if (version.toUpperCase() === 'CUSTOM') {
        customZipGroup.style.display = 'block';
        const data = await sendServerActionRequest(null, '/api/downloads/list', 'GET', null, null, true);
        const selector = document.getElementById('custom-zip-selector');
        selector.innerHTML = '';
        if (data && data.custom_zips && data.custom_zips.length > 0) {
            data.custom_zips.forEach(zip => {
                const option = document.createElement('option');
                option.value = zip;
                option.textContent = zip;
                selector.appendChild(option);
            });
        } else {
            selector.innerHTML = '<option disabled>No custom zips found</option>';
        }
    } else {
        customZipGroup.style.display = 'none';
    }
}

export function initializeInstallConfigPage() {
    console.log("Install/config page script loaded.");

    const installConfigPage = document.getElementById('install-config-page');
    const serverName = installConfigPage?.dataset.serverName;
    const isNewInstall = installConfigPage?.dataset.isNewInstall === 'true';
    const os = installConfigPage?.dataset.os;

    document.getElementById('install-server-btn')?.addEventListener('click', (e) => triggerInstallServer(e.currentTarget));
    document.getElementById('save-permissions-btn')?.addEventListener('click', (e) => savePermissions(e.currentTarget, serverName, isNewInstall));
    document.getElementById('save-service-settings-btn')?.addEventListener('click', (e) => saveServiceSettings(e.currentTarget, serverName, os, isNewInstall));

    if (new URLSearchParams(window.location.search).has('in_setup')) {
        const bannerContainer = document.getElementById('setup-banner-container');
        if (bannerContainer) {
            bannerContainer.innerHTML = `
            <div class="setup-banner">
                <h3>Step 3: Install a Server</h3>
                <p>
                    Install and configure your first Bedrock Server. This will include setting server.properties, allowlist, and other files.
                </p>
                <a href="/" class="action-button">Skip</a>
            </div>
        `;
        }
    }

    // Custom controls initialization
    document.querySelectorAll('.segmented-control').forEach(control => {
        const input = document.getElementById(control.dataset.inputId);
        if (input) {
            control.querySelectorAll('.segment').forEach(segment => {
                segment.addEventListener('click', e => {
                    e.preventDefault();
                    input.value = segment.dataset.value;
                    control.querySelectorAll('.segment').forEach(s => s.classList.remove('active'));
                    segment.classList.add('active');
                });
            });
        }
    });

    document.querySelectorAll('.toggle-input').forEach(input => {
        const hidden = input.closest('.form-group-toggle-container')?.querySelector(`.toggle-hidden-false[name="${input.name.replace('-cb', '')}"]`);
        if (hidden) {
            const sync = () => hidden.disabled = input.checked;
            input.addEventListener('change', sync);
            sync();
        }
    });

    // Logic from configure_properties.html
    const setInputValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };

    const setToggleState = (id, value) => {
        const el = document.getElementById(id);
        if (el) {
            el.checked = (String(value).toLowerCase() === 'true');
            el.dispatchEvent(new Event('change'));
        }
    };

    const setSegmentedControlState = (hiddenInputId, value) => {
        const hiddenInput = document.getElementById(hiddenInputId);
        const controlWrapper = document.querySelector(`[data-input-id="${hiddenInputId}"]`);
        if (hiddenInput && controlWrapper) {
            hiddenInput.value = value;
            controlWrapper.querySelectorAll('.segment').forEach(s => s.classList.remove('active'));
            const activeSegment = controlWrapper.querySelector(`.segment[data-value="${value}"]`);
            if (activeSegment) activeSegment.classList.add('active');
        }
    };

    function populateForm(properties) {
        if (properties['server-name']) setInputValue('server-name', properties['server-name']);
        if (properties['level-name']) setInputValue('level-name', properties['level-name']);
        if (properties['gamemode']) setSegmentedControlState('gamemode-hidden', properties['gamemode']);
        if (properties['difficulty']) setSegmentedControlState('difficulty-hidden', properties['difficulty']);
        if (properties['allow-cheats'] !== undefined) setToggleState('allow-cheats-cb', properties['allow-cheats']);
        if (properties['max-players']) setInputValue('max-players', properties['max-players']);
        if (properties['level-seed']) setInputValue('level-seed', properties['level-seed']);
        if (properties['server-port']) setInputValue('server-port', properties['server-port']);
        if (properties['server-portv6']) setInputValue('server-portv6', properties['server-portv6']);
        if (properties['enable-lan-visibility'] !== undefined) setToggleState('enable-lan-visibility-cb', properties['enable-lan-visibility']);
        if (properties['allow-list'] !== undefined) setToggleState('allow-list-cb', properties['allow-list']);
        if (properties['default-player-permission-level']) setSegmentedControlState('default-player-permission-level-hidden', properties['default-player-permission-level']);
        if (properties['view-distance']) setInputValue('view-distance', properties['view-distance']);
        if (properties['tick-distance']) setInputValue('tick-distance', properties['tick-distance']);
        if (properties['online-mode'] !== undefined) setToggleState('online-mode-cb', properties['online-mode']);
        if (properties['texturepack-required'] !== undefined) setToggleState('texturepack-required-cb', properties['texturepack-required']);
    }

    async function loadProperties() {
        const loader = document.getElementById('properties-loader');
        const formContainer = document.getElementById('properties-form-container');
        try {
            const data = await sendServerActionRequest(serverName, 'properties/get', 'GET', null, null);
            if (data && data.status === 'success' && data.properties) {
                populateForm(data.properties);
            } else {
                showStatusMessage(data?.message || 'Failed to load server properties.', 'error');
            }
        } catch (error) {
            showStatusMessage(`Client-side error loading properties: ${error.message}`, 'error');
        } finally {
            if(loader) loader.style.display = 'none';
            if(formContainer) formContainer.style.display = 'block';
        }
    }

    if (document.getElementById('properties-form-container')) {
        loadProperties();
    }
}
