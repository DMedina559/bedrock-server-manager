// frontend/src/manage_plugins.js
import { sendServerActionRequest, showStatusMessage } from './utils.js';

export function initializeManagePluginsPage() {
    const functionName = 'PluginManagerUI';

    const pluginList = document.getElementById('plugin-list');
    const pluginItemTemplate = document.getElementById('plugin-item-template');
    const noPluginsTemplate = document.getElementById('no-plugins-template');
    const loadErrorTemplate = document.getElementById('load-error-template');
    const pluginLoader = document.getElementById('plugin-loader');
    const reloadPluginsBtn = document.getElementById('reload-plugins-btn');

    if (!pluginList || !pluginItemTemplate || !noPluginsTemplate || !loadErrorTemplate || !pluginLoader || !reloadPluginsBtn) {
        console.error(`${functionName}: Critical page elements missing.`);
        if (pluginList) pluginList.innerHTML = '<li>Page setup error.</li>';
        return;
    }

    reloadPluginsBtn.addEventListener('click', handleReloadClick);

    async function handleReloadClick() {
        reloadPluginsBtn.disabled = true;
        const originalButtonText = reloadPluginsBtn.innerHTML;
        reloadPluginsBtn.innerHTML = '<div class="spinner-small"></div> Reloading...';

        try {
            const result = await sendServerActionRequest(null, '/api/plugins/reload', 'PUT', null, reloadPluginsBtn);
            if (result && result.status === 'success') {
                await fetchAndRenderPlugins();
            }
        } finally {
            reloadPluginsBtn.innerHTML = originalButtonText;
            if (reloadPluginsBtn.disabled) reloadPluginsBtn.disabled = false;
        }
    }

    async function fetchAndRenderPlugins() {
        pluginLoader.style.display = 'flex';
        pluginList.querySelectorAll('li:not(#plugin-loader)').forEach(el => el.remove());

        try {
            const data = await sendServerActionRequest(null, '/api/plugins', 'GET', null, null, true);
            pluginLoader.style.display = 'none';

            if (data && data.status === 'success') {
                const plugins = data.data;
                if (plugins && Object.keys(plugins).length > 0) {
                    Object.keys(plugins).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())).forEach(pluginName => {
                        const pluginData = plugins[pluginName];
                        const itemClone = pluginItemTemplate.content.cloneNode(true);
                        itemClone.querySelector('.plugin-name').textContent = pluginName;
                        itemClone.querySelector('.plugin-version').textContent = `v${pluginData.version || 'N/A'}`;
                        const toggleSwitch = itemClone.querySelector('.plugin-toggle-switch');
                        toggleSwitch.checked = pluginData.enabled;
                        toggleSwitch.dataset.pluginName = pluginName;
                        toggleSwitch.addEventListener('change', handlePluginToggle);
                        pluginList.appendChild(itemClone);
                    });
                } else {
                    pluginList.appendChild(noPluginsTemplate.content.cloneNode(true));
                }
            } else {
                pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
            }
        } catch (error) {
            pluginLoader.style.display = 'none';
            pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
            showStatusMessage(`Unexpected error fetching plugin data: ${error.message}`, 'error');
        }
    }

    async function handlePluginToggle(event) {
        const toggleSwitch = event.target;
        const pluginName = toggleSwitch.dataset.pluginName;
        const isEnabled = toggleSwitch.checked;

        const result = await sendServerActionRequest(null, `/api/plugins/${pluginName}`, 'POST', { enabled: isEnabled }, toggleSwitch);
        if (!result || result.status !== 'success') {
            toggleSwitch.checked = !isEnabled; // Revert on error
        }
    }

    fetchAndRenderPlugins();
    console.log(`${functionName}: Plugin management page initialized.`);
}
