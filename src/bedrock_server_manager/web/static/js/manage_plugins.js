// bedrock_server_manager/web/static/js/manage_plugins.js

document.addEventListener('DOMContentLoaded', () => {
    const functionName = 'PluginManagerUI';

    // --- DOM Elements ---
    const pluginList = document.getElementById('plugin-list');
    const pluginItemTemplate = document.getElementById('plugin-item-template');
    const noPluginsTemplate = document.getElementById('no-plugins-template');
    const loadErrorTemplate = document.getElementById('load-error-template');
    const pluginLoader = document.getElementById('plugin-loader');
    const reloadPluginsBtn = document.getElementById('reload-plugins-btn'); // Get the reload button

    if (!pluginList || !pluginItemTemplate || !noPluginsTemplate || !loadErrorTemplate || !pluginLoader || !reloadPluginsBtn) {
        console.error(`${functionName}: Critical template, container, or button element missing.`);
        if (pluginList) {
            pluginList.innerHTML = '<li class="list-item-error"><p>Page setup error. Required elements missing.</p></li>';
        }
        return;
    }

    // Attach event listener to the reload button
    reloadPluginsBtn.addEventListener('click', handleReloadClick);

    /**
     * Handles the click event for the Reload Plugins button.
     */
    async function handleReloadClick() {
        console.log(`${functionName}: Reloading plugins...`);
        reloadPluginsBtn.disabled = true;
        const originalButtonText = reloadPluginsBtn.innerHTML; // Store original content (including icon)
        reloadPluginsBtn.innerHTML = '<div class="spinner-small"></div> Reloading...'; // Show loading state

        // Using sendServerActionRequest which handles status messages and button disabling
        try {
            // serverName is null for global actions, actionPath is absolute
            const result = await sendServerActionRequest(null, '/api/plugins/reload', 'PUT', null, reloadPluginsBtn); // Updated path

            // sendServerActionRequest shows its own success/error messages based on result.status
            // It also re-enables the button in its finally block unless result.status is 'confirm_needed'
            // (which is not expected here).

            if (result && result.status === 'success') {
                // Refresh the plugin list on the page to reflect any changes
                await fetchAndRenderPlugins();
            } else {
                // Error message already shown by sendServerActionRequest if result exists and has status 'error'
                // If result is false, it means a fetch-level error occurred, also handled by sendServerActionRequest
                console.error(`${functionName}: Reload plugins API call failed or returned error. Result:`, result);
            }
        } catch (error) {
            // This catch is for unexpected errors in this function's logic,
            // not for API call failures handled by sendServerActionRequest.
            console.error(`${functionName}: Unexpected error during reload plugin process:`, error);
            if (typeof showStatusMessage === 'function') {
                showStatusMessage(`Unexpected error during plugin reload: ${error.message}`, 'error');
            }
            // Ensure button is re-enabled in case of an unexpected error here
            // reloadPluginsBtn.disabled = false; // Handled by finally
            // reloadPluginsBtn.innerHTML = originalButtonText; // Handled by finally
        } finally {
            // Always restore the original button text and ensure it's enabled.
            reloadPluginsBtn.innerHTML = originalButtonText;
            // sendServerActionRequest should also try to re-enable, but this is a safeguard.
            if (reloadPluginsBtn.disabled) {
                reloadPluginsBtn.disabled = false;
            }
        }
    }


    /**
     * Fetches plugin statuses from the API and renders them.
     */
    async function fetchAndRenderPlugins() {
        pluginLoader.style.display = 'flex';
        // Clear only plugin items, empty messages, or error messages, not the loader itself
        pluginList.querySelectorAll('li:not(#plugin-loader)').forEach(el => el.remove());

        try {
            // Use sendServerActionRequest for the GET request.
            // serverName is null for global actions, actionPath is absolute.
            // No body for GET. Button element can be the loader itself or null.
            const data = await sendServerActionRequest(null, '/api/plugins', 'GET', null, null); // Updated path, Pass null for button if loader handles its own state

            pluginLoader.style.display = 'none'; // Hide loader

            if (data && data.status === 'success') {
                const plugins = data.data; // Changed from data.plugins to data.data based on GeneralPluginApiResponse
                if (plugins && Object.keys(plugins).length > 0) {
                    const sortedPluginNames = Object.keys(plugins).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));

                    sortedPluginNames.forEach(pluginName => {
                        const pluginData = plugins[pluginName];
                        const isEnabled = pluginData.enabled;
                        const version = pluginData.version || 'N/A';

                        const itemClone = pluginItemTemplate.content.cloneNode(true);
                        const nameSpan = itemClone.querySelector('.plugin-name');
                        const versionSpan = itemClone.querySelector('.plugin-version');
                        const toggleSwitch = itemClone.querySelector('.plugin-toggle-switch');

                        nameSpan.textContent = pluginName;
                        versionSpan.textContent = `v${version}`;
                        toggleSwitch.checked = isEnabled;
                        toggleSwitch.dataset.pluginName = pluginName;

                        toggleSwitch.addEventListener('change', handlePluginToggle);
                        pluginList.appendChild(itemClone);
                    });
                } else {
                    pluginList.appendChild(noPluginsTemplate.content.cloneNode(true));
                }
            } else {
                // Error message already shown by sendServerActionRequest if data exists and has status 'error'
                // Or if data is false (fetch-level error)
                console.error(`${functionName}: Failed to fetch plugins. Data:`, data);
                if (loadErrorTemplate) {
                    pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
                }
                // sendServerActionRequest should have already shown a status message.
                // If data.message exists, it was an application error. Otherwise, a fetch error.
                if (data && data.message && typeof showStatusMessage === 'function') {
                    // showStatusMessage(data.message, 'error'); // This might be redundant
                } else if (data === false && typeof showStatusMessage === 'function') {
                    // showStatusMessage('Failed to load plugin data due to a network or server error.', 'error'); // Redundant
                }
            }
        } catch (error) {
            // This catch is for unexpected errors in this function's logic itself
            console.error(`${functionName}: Unexpected error fetching or rendering plugins:`, error);
            pluginLoader.style.display = 'none';
            if (loadErrorTemplate) {
                pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
            }
            if (typeof showStatusMessage === 'function') {
                showStatusMessage(`Unexpected error fetching plugin data: ${error.message}`, 'error');
            }
        }
    }

    /**
     * Handles the change event of a plugin toggle switch.
     */
    async function handlePluginToggle(event) {
        const toggleSwitch = event.target;
        const pluginName = toggleSwitch.dataset.pluginName;
        const isEnabled = toggleSwitch.checked;

        // Temporarily disable the switch to prevent rapid toggling - sendServerActionRequest will handle this
        // toggleSwitch.disabled = true; 

        try {
            // serverName is null for global actions, actionPath is absolute and constructed with pluginName
            const result = await sendServerActionRequest(null, `/api/plugins/${pluginName}`, 'POST', { enabled: isEnabled }, toggleSwitch); // Updated path

            // sendServerActionRequest shows status messages and handles button state.
            // We only need to revert the toggle if the API call was not successful.
            if (!result || result.status !== 'success') {
                console.error(`${functionName}: Failed to update plugin '${pluginName}' status. Result:`, result);
                toggleSwitch.checked = !isEnabled; // Revert UI change on error
                // Error message should have been shown by sendServerActionRequest
            } else {
                if (typeof showStatusMessage === 'function' && result.message) {
                    // showStatusMessage(result.message, 'success'); // Potentially redundant if sendServerActionRequest shows it
                } else if (typeof showStatusMessage === 'function') {
                    // showStatusMessage(`Plugin '${pluginName}' status updated. Reload plugins to apply changes.`, 'success');
                }
            }
        } catch (error) {
            // This catch is for unexpected errors in this function's logic
            console.error(`${functionName}: Unexpected error updating plugin '${pluginName}':`, error);
            if (typeof showStatusMessage === 'function') {
                showStatusMessage(`Unexpected error updating plugin '${pluginName}': ${error.message}`, 'error');
            }
            toggleSwitch.checked = !isEnabled; // Revert UI change
            toggleSwitch.disabled = false; // Ensure switch is re-enabled
        }
        // Note: sendServerActionRequest handles button (toggleSwitch in this case) re-enabling.
    }

    // --- Initial Load ---
    fetchAndRenderPlugins();

    console.log(`${functionName}: Plugin management page initialization complete.`);
});