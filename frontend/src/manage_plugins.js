// frontend/src/manage_plugins.js
import { getPlugins, reloadPlugins, setPluginState } from "./plugins_api.js";
import { showStatusMessage, handleApiAction } from "./ui_utils.js";

export function initializeManagePluginsPage() {
  const functionName = "PluginManagerUI";

  const pluginList = document.getElementById("plugin-list");
  const pluginItemTemplate = document.getElementById("plugin-item-template");
  const noPluginsTemplate = document.getElementById("no-plugins-template");
  const loadErrorTemplate = document.getElementById("load-error-template");
  const pluginLoader = document.getElementById("plugin-loader");
  const reloadPluginsBtn = document.getElementById("reload-plugins-btn");

  if (
    !pluginList ||
    !pluginItemTemplate ||
    !noPluginsTemplate ||
    !loadErrorTemplate ||
    !pluginLoader ||
    !reloadPluginsBtn
  ) {
    console.error(`${functionName}: Critical page elements missing.`);
    if (pluginList) pluginList.innerHTML = "<li>Page setup error.</li>";
    return;
  }

  // Banner Logic
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has("in_setup")) {
    const bannerContainer = document.getElementById("setup-banner-container");
    if (bannerContainer) {
      bannerContainer.innerHTML = `
        <div class="setup-banner">
            <h3>Step 2: Plugin Management</h3>
            <p>
                Here you can manage plugins. Reload plugins to apply any changes.<br>
                <strong>Note:</strong> Any plugins that add new FastAPI routes (such as the content_uploader_plugin) will require a server restart to take effect.
            </p>
            <a href="/install?in_setup=true" class="action-button">Continue to Server Installation</a>
        </div>
      `;
    }
  }

  reloadPluginsBtn.addEventListener("click", handleReloadClick);

  async function handleReloadClick() {
    await handleApiAction(
      reloadPluginsBtn,
      async () => {
        const result = await reloadPlugins();
        if (result && result.status === "success") {
          await fetchAndRenderPlugins();
        }
        return result;
      },
      "Reloading...",
    );
  }

  async function fetchAndRenderPlugins() {
    pluginLoader.style.display = "flex";
    pluginList
      .querySelectorAll("li:not(#plugin-loader)")
      .forEach((el) => el.remove());

    try {
      const data = await getPlugins();
      pluginLoader.style.display = "none";

      if (data && data.status === "success") {
        const plugins = data.data;
        if (plugins && Object.keys(plugins).length > 0) {
          Object.keys(plugins)
            .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
            .forEach((pluginName) => {
              const pluginData = plugins[pluginName];
              const itemClone = pluginItemTemplate.content.cloneNode(true);
              itemClone.querySelector(".plugin-name").textContent = pluginName;
              itemClone.querySelector(".plugin-version").textContent =
                `v${pluginData.version || "N/A"}`;
              const toggleSwitch = itemClone.querySelector(
                ".plugin-toggle-switch",
              );
              toggleSwitch.checked = pluginData.enabled;
              toggleSwitch.dataset.pluginName = pluginName;
              toggleSwitch.addEventListener("change", handlePluginToggle);
              pluginList.appendChild(itemClone);
            });
        } else {
          pluginList.appendChild(noPluginsTemplate.content.cloneNode(true));
        }
      } else {
        pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
      }
    } catch (error) {
      pluginLoader.style.display = "none";
      pluginList.appendChild(loadErrorTemplate.content.cloneNode(true));
      showStatusMessage(
        `Unexpected error fetching plugin data: ${error.message}`,
        "error",
      );
    }
  }

  async function handlePluginToggle(event) {
    const toggleSwitch = event.target;
    const pluginName = toggleSwitch.dataset.pluginName;
    const isEnabled = toggleSwitch.checked;

    // We can't use handleApiAction directly on a toggle switch because it's not a button (disabling it might look weird or interrupt interaction).
    // But we should handle the async nature and revert if it fails.
    toggleSwitch.disabled = true;

    try {
      const result = await setPluginState(pluginName, isEnabled);
      if (result && result.status === "success") {
        showStatusMessage(
          `Plugin '${pluginName}' ${isEnabled ? "enabled" : "disabled"}.`,
          "success",
        );
      } else {
        toggleSwitch.checked = !isEnabled; // Revert
        showStatusMessage(
          result?.message || "Failed to toggle plugin.",
          "error",
        );
      }
    } catch (error) {
      toggleSwitch.checked = !isEnabled; // Revert
      showStatusMessage(`Error: ${error.message}`, "error");
    } finally {
      toggleSwitch.disabled = false;
    }
  }

  fetchAndRenderPlugins();
  console.log(`${functionName}: Plugin management page initialized.`);
}
