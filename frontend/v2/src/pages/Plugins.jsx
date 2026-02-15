import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { RefreshCw, Plug } from "lucide-react";

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
      const response = await fetch("/api/plugins");
      if (response.ok) {
        const data = await response.json();
        setPlugins(data);
      } else {
        addToast("Failed to fetch plugins", "error");
      }
    } catch (error) {
      addToast("Error fetching plugins", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleReload = async () => {
    addToast("Reloading plugins...", "info");
    try {
      const response = await fetch("/api/plugins/reload", { method: "POST" });
      if (response.ok) {
        addToast("Plugins reloaded successfully", "success");
        fetchPlugins();
      } else {
        addToast("Failed to reload plugins", "error");
      }
    } catch (error) {
      addToast("Error reloading plugins", "error");
    }
  };

  return (
    <div className="container" style={{ padding: "20px" }}>
      <div
        className="header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Plugin Management</h1>
        <button
          className="button"
          onClick={handleReload}
          style={{ display: "flex", alignItems: "center", gap: "5px" }}
        >
          <RefreshCw size={18} /> Reload Plugins
        </button>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <div style={{ marginTop: "20px" }}>
          {plugins.length === 0 ? (
            <p>No plugins installed.</p>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                gap: "20px",
              }}
            >
              {plugins.map((plugin, index) => (
                <div
                  key={index}
                  style={{
                    background: "var(--container-background-color)",
                    border: "1px solid var(--border-color)",
                    padding: "15px",
                    borderRadius: "5px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      marginBottom: "10px",
                    }}
                  >
                    <Plug size={24} />
                    <h3 style={{ margin: 0 }}>{plugin.name}</h3>
                  </div>
                  <p style={{ margin: "5px 0", color: "#ccc" }}>
                    {plugin.description || "No description"}
                  </p>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginTop: "10px",
                      fontSize: "0.9em",
                    }}
                  >
                    <span>Version: {plugin.version || "N/A"}</span>
                    <span
                      style={{ color: plugin.enabled ? "lightgreen" : "gray" }}
                    >
                      {plugin.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Plugins;
