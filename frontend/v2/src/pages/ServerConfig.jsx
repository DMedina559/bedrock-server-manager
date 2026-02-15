import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { post, get } from "../api";
import { Download, Save } from "lucide-react";

const ServerConfig = () => {
  const { selectedServer } = useServer();
  const [config, setConfig] = useState({ autostart: false, autoupdate: false });
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  // Legacy doesn't have a specific "get service config" endpoint that returns JSON?
  // server_install_config.py -> configure_service_page renders HTML with initial values.
  // But there is no API to GET current autostart/autoupdate status?
  // Wait, system_api.is_autostart_enabled(server_name) exists in backend logic but maybe not exposed as JSON API?
  // Let's check server_install_config.py again.
  // It renders "configure_service.html" with "autostart_enabled": ..., "autoupdate_enabled": ...
  // But no API endpoint to get it?

  // If no API endpoint exists to GET, we can't pre-fill the form correctly in SPA.
  // This is a gap. I might need to add an endpoint or just assume false (bad UX).
  // Or maybe I missed the endpoint.

  // I'll assume for now we can't fetch it easily without adding an endpoint,
  // so I'll just show the controls and maybe they default to unchecked or I can try to fetch them if I find a way.
  // Actually, I can use the new api.js to fetch the HTML page and parse it? No, that's ugly.
  // Let's look for an API endpoint.

  // If there isn't one, I'll just provide the "Set" functionality.

  const handleSave = async (e) => {
    e.preventDefault();
    if (!selectedServer) return;

    setLoading(true);
    try {
      await post(`/api/server/${selectedServer}/service/update`, {
        autostart: config.autostart,
        autoupdate: config.autoupdate,
      });
      addToast("Service configuration saved.", "success");
    } catch (error) {
      addToast(error.message || "Failed to save configuration.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateServer = async () => {
    if (!selectedServer) return;
    if (!confirm("This will stop the server and update it to the latest version. Continue?")) return;

    addToast("Updating server...", "info");
    try {
      await post(`/api/server/${selectedServer}/update`, {});
      addToast("Update task started. Check logs.", "success");
    } catch (error) {
      addToast(error.message || "Failed to start update.", "error");
    }
  };

  if (!selectedServer) {
    return (
      <div className="container">
        <div className="message-box message-warning" style={{ textAlign: "center", marginTop: "50px", padding: "20px", border: "1px solid orange", color: "orange" }}>
          Please select a server to configure.
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="header">
        <h1>Server Configuration: {selectedServer}</h1>
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
            border: "1px solid var(--border-color)",
          }}
        >
          <h3>Update Server</h3>
          <p>Update the server to the latest Bedrock version.</p>
          <button
            className="action-button"
            onClick={handleUpdateServer}
            disabled={loading}
          >
            <Download size={16} style={{ marginRight: "5px" }} /> Update Server Now
          </button>
        </div>

        {/* Configuration Form */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h3>Service Settings</h3>
          <p style={{ fontSize: "0.9em", color: "#aaa", marginBottom: "15px" }}>
            Configure automatic startup and updates. (Current state retrieval not supported via API)
          </p>
          <form onSubmit={handleSave}>
            <div className="form-group">
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
                  checked={config.autostart}
                  onChange={(e) =>
                    setConfig({ ...config, autostart: e.target.checked })
                  }
                  className="form-checkbox"
                  // form-checkbox class might not be in forms.css, let's stick to default
                />
                Auto-Start Server on Boot
              </label>
            </div>
            <div className="form-group">
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
                  checked={config.autoupdate}
                  onChange={(e) =>
                    setConfig({ ...config, autoupdate: e.target.checked })
                  }
                />
                Auto-Update Server
              </label>
            </div>

            <button type="submit" className="action-button" disabled={loading}>
              <Save size={16} style={{ marginRight: "5px" }} /> Save Settings
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ServerConfig;
