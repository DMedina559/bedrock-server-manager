import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { Download, RefreshCw, Settings as SettingsIcon } from "lucide-react";

const ServerConfig = () => {
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await fetch("/api/server/install-config");
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (error) {
      addToast("Error fetching server config", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("/api/server/install-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (response.ok) {
        addToast("Configuration saved.", "success");
      } else {
        addToast("Failed to save configuration.", "error");
      }
    } catch (error) {
      addToast("Error saving configuration.", "error");
    }
  };

  const handleUpdateServer = async () => {
    if (!confirm("This will stop the server and update it. Continue?")) return;
    addToast("Updating server...", "info");
    try {
      const response = await fetch("/api/server/update", { method: "POST" });
      if (response.ok) {
        addToast("Update started.", "success");
      } else {
        addToast("Failed to start update.", "error");
      }
    } catch (error) {
      addToast("Error starting update.", "error");
    }
  };

  return (
    <div className="container" style={{ padding: "20px" }}>
      <div className="header">
        <h1>Server Configuration</h1>
      </div>

      <div
        className="grid"
        style={{
          display: "grid",
          gap: "30px",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
        }}
      >
        {/* Actions Panel */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            borderRadius: "5px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h2>Actions</h2>
          <p>Manage server version and installation.</p>
          <button
            className="button button-primary"
            onClick={handleUpdateServer}
            style={{ display: "flex", alignItems: "center", gap: "10px" }}
          >
            <Download size={18} /> Update Server Now
          </button>
        </div>

        {/* Configuration Form */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            borderRadius: "5px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h2>Settings</h2>
          <form onSubmit={handleSave}>
            <div style={{ marginBottom: "15px" }}>
              <label
                className="form-label"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={config.auto_start || false}
                  onChange={(e) =>
                    setConfig({ ...config, auto_start: e.target.checked })
                  }
                />
                Auto-Start Server on Boot
              </label>
            </div>
            <div style={{ marginBottom: "15px" }}>
              <label
                className="form-label"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={config.auto_update || false}
                  onChange={(e) =>
                    setConfig({ ...config, auto_update: e.target.checked })
                  }
                />
                Auto-Update Server
              </label>
            </div>
            <div style={{ marginBottom: "15px" }}>
              <label className="form-label">
                Target Version (leave empty for latest)
              </label>
              <input
                type="text"
                className="form-input"
                value={config.target_version || ""}
                onChange={(e) =>
                  setConfig({ ...config, target_version: e.target.value })
                }
                placeholder="e.g., 1.20.10.01"
                style={{ width: "100%" }}
              />
            </div>
            <button type="submit" className="button button-primary">
              Save Settings
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ServerConfig;
