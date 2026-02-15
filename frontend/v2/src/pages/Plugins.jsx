import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { get, post, put } from "../api";
import { RefreshCw, Plug, ToggleLeft, ToggleRight } from "lucide-react";

const Plugins = () => {
  const [plugins, setPlugins] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    fetchPlugins();
  }, []);

  const fetchPlugins = async () => {
    setLoading(true);
    try {
      const data = await get("/api/plugins");
      if (data && data.status === "success" && data.data) {
        const pluginsArray = Object.entries(data.data).map(([name, details]) => ({
          name,
          ...details,
        }));
        pluginsArray.sort((a, b) => a.name.localeCompare(b.name));
        setPlugins(pluginsArray);
      } else {
        addToast("Failed to fetch plugins", "error");
        setPlugins([]);
      }
    } catch (error) {
      addToast(error.message || "Error fetching plugins", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleReload = async () => {
    addToast("Reloading plugins...", "info");
    try {
      await put("/api/plugins/reload");

      addToast("Plugins reloaded successfully", "success");
      fetchPlugins();
    } catch (error) {
      addToast(error.message || "Failed to reload plugins", "error");
    }
  };

  const handleToggle = async (pluginName, currentEnabled) => {
    const newEnabled = !currentEnabled;
    try {
      await put(`/api/plugins/${pluginName}`, { enabled: newEnabled });
      addToast(`Plugin ${pluginName} ${newEnabled ? "enabled" : "disabled"}.`, "success");

      // Optimistic update or refetch
      setPlugins(prev => prev.map(p =>
        p.name === pluginName ? { ...p, enabled: newEnabled } : p
      ));
    } catch (error) {
      addToast(error.message || `Failed to toggle plugin ${pluginName}`, "error");
    }
  };

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Plugin Management</h1>
        <button
          className="action-button secondary"
          onClick={handleReload}
        >
          <RefreshCw size={16} style={{ marginRight: "5px" }} /> Reload Plugins
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "20px" }}>Loading...</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "20px", marginTop: "20px" }}>
          {plugins.length === 0 ? (
            <p style={{ color: "#aaa" }}>No plugins installed.</p>
          ) : (
            plugins.map((plugin) => (
              <div
                key={plugin.name}
                style={{
                  background: "var(--container-background-color)",
                  border: "1px solid var(--border-color)",
                  padding: "15px",
                  display: "flex",
                  flexDirection: "column"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Plug size={20} />
                    <h3 style={{ margin: 0, fontSize: "1.1em" }}>{plugin.name}</h3>
                  </div>

                  <button
                    onClick={() => handleToggle(plugin.name, plugin.enabled)}
                    style={{ background: "none", border: "none", cursor: "pointer", color: plugin.enabled ? "var(--primary-button-background-color)" : "#777" }}
                    title={plugin.enabled ? "Disable" : "Enable"}
                  >
                    {plugin.enabled ? <ToggleRight size={32} /> : <ToggleLeft size={32} />}
                  </button>
                </div>

                <p style={{ margin: "5px 0", color: "#ccc", fontSize: "0.9em", flexGrow: 1 }}>
                  {plugin.description || "No description provided."}
                </p>

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: "15px", fontSize: "0.85em", color: "#888", borderTop: "1px solid var(--border-color)", paddingTop: "10px" }}>
                  <span>v{plugin.version || "N/A"}</span>
                  <span>{plugin.author || "Unknown Author"}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default Plugins;
