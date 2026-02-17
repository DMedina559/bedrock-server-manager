import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { get, post } from "../api";
import { Save, RefreshCw, Download, CheckCircle } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

const ServerConfig = () => {
  const { selectedServer } = useServer();
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const setupFlow = location.state?.setupFlow;

  useEffect(() => {
    if (selectedServer) {
      fetchSettings();
    }
  }, [selectedServer]);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await get(`/api/servers/${selectedServer}/settings`);
      if (data && data.status === "success" && data.settings) {
        setSettings(data.settings);
        return true;
      } else {
        addToast("Failed to load server settings", "error");
        setSettings({});
        return false;
      }
    } catch (error) {
      addToast(error.message || "Error fetching server settings", "error");
      return false;
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    const success = await fetchSettings();
    if (success) {
      addToast("Settings refreshed", "success");
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!selectedServer) return;

    setLoading(true);
    try {
      const flattened = flattenObject(settings);

      for (const [key, value] of Object.entries(flattened)) {
        if (key === "config_schema_version") continue;

        await post(`/api/servers/${selectedServer}/settings`, {
          key: key,
          value: value,
        });
      }

      addToast("Server settings saved successfully.", "success");
      fetchSettings();
    } catch (error) {
      addToast(error.message || "Failed to save settings.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleFinishSetup = async () => {
    if (confirm("Setup complete! Would you like to start the server now?")) {
      addToast("Starting server...", "info");
      try {
        await post(`/api/server/${selectedServer}/start`);
        addToast("Server start signal sent.", "success");
      } catch (error) {
        addToast("Failed to start server: " + error.message, "error");
      }
    }
    navigate("/");
    addToast("Server setup complete!", "success");
  };

  const handleUpdateServer = async () => {
    if (!selectedServer) return;
    if (
      !confirm(
        "This will stop the server and update it to the latest version. Continue?",
      )
    )
      return;

    addToast("Updating server...", "info");
    try {
      await post(`/api/server/${selectedServer}/update`, {});
      addToast("Update task started. Check logs.", "success");
    } catch (error) {
      addToast(error.message || "Failed to start update.", "error");
    }
  };

  const handleChange = (path, value) => {
    setSettings((prev) => {
      const newSettings = JSON.parse(JSON.stringify(prev));
      let current = newSettings;
      const keys = path.split(".");
      const lastKey = keys.pop();

      keys.forEach((key) => {
        if (!current[key]) current[key] = {};
        current = current[key];
      });

      current[lastKey] = value;
      return newSettings;
    });
  };

  const flattenObject = (obj, prefix = "") => {
    return Object.keys(obj).reduce((acc, k) => {
      const pre = prefix.length ? prefix + "." : "";
      if (
        typeof obj[k] === "object" &&
        obj[k] !== null &&
        !Array.isArray(obj[k])
      ) {
        Object.assign(acc, flattenObject(obj[k], pre + k));
      } else {
        acc[pre + k] = obj[k];
      }
      return acc;
    }, {});
  };

  const renderFields = (obj, prefix = "") => {
    return Object.entries(obj).map(([key, value]) => {
      const fullPath = prefix ? `${prefix}.${key}` : key;

      if (key === "config_schema_version") return null;

      if (
        typeof value === "object" &&
        value !== null &&
        !Array.isArray(value)
      ) {
        return (
          <div
            key={fullPath}
            style={{
              marginBottom: "20px",
              marginLeft: "10px",
              paddingLeft: "10px",
              borderLeft: "2px solid var(--border-color)",
            }}
          >
            <h4 style={{ textTransform: "capitalize", margin: "10px 0" }}>
              {key.replace(/_/g, " ")}
            </h4>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                gap: "15px",
              }}
            >
              {renderFields(value, fullPath)}
            </div>
          </div>
        );
      }

      return (
        <div
          key={fullPath}
          style={{ display: "flex", flexDirection: "column" }}
        >
          <label
            htmlFor={fullPath}
            className="form-label"
            style={{
              marginBottom: "5px",
              fontWeight: "bold",
              fontSize: "0.9em",
            }}
          >
            {key.replace(/_/g, " ")}
          </label>
          {typeof value === "boolean" ? (
            <select
              id={fullPath}
              className="form-input"
              value={value.toString()}
              onChange={(e) =>
                handleChange(fullPath, e.target.value === "true")
              }
            >
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          ) : (
            <input
              type="text"
              id={fullPath}
              className="form-input"
              value={value || ""}
              readOnly={
                prefix.includes("server_info") &&
                (key === "status" || key === "installed_version")
              }
              onChange={(e) => handleChange(fullPath, e.target.value)}
            />
          )}
        </div>
      );
    });
  };

  if (!selectedServer) {
    return (
      <div className="container">
        <div
          className="message-box message-warning"
          style={{
            textAlign: "center",
            marginTop: "50px",
            padding: "20px",
            border: "1px solid orange",
            color: "orange",
          }}
        >
          Please select a server to configure.
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div
        className="header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Server Settings: {selectedServer}</h1>
        <div style={{ display: "flex", gap: "10px" }}>
          {!setupFlow && (
            <button
              className="action-button secondary"
              onClick={handleRefresh}
              disabled={loading}
            >
              <RefreshCw size={16} style={{ marginRight: "5px" }} /> Refresh
            </button>
          )}
          {setupFlow && (
            <button
              className="action-button success-button"
              onClick={handleFinishSetup}
            >
              <CheckCircle size={16} style={{ marginRight: "5px" }} /> Finish
              Setup
            </button>
          )}
        </div>
      </div>

      {setupFlow && (
        <div
          className="message-box message-info"
          style={{ marginBottom: "20px" }}
        >
          <strong>Setup Wizard (Step 4/4):</strong> Configure BSM settings for
          this server.
        </div>
      )}

      {loading && Object.keys(settings).length === 0 ? (
        <div style={{ textAlign: "center", padding: "20px" }}>
          Loading settings...
        </div>
      ) : (
        <div
          className="grid"
          style={{ display: "flex", flexDirection: "column", gap: "20px" }}
        >
          {!setupFlow && (
            <div
              style={{
                padding: "15px",
                background: "#444",
                borderRadius: "5px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ color: "#eee" }}>
                <strong>Quick Actions:</strong>
              </div>
              <button className="action-button" onClick={handleUpdateServer}>
                <Download size={16} style={{ marginRight: "5px" }} /> Update
                Server Software
              </button>
            </div>
          )}

          <form onSubmit={handleSave} className="form-group">
            <div
              style={{
                background: "var(--container-background-color)",
                padding: "20px",
                border: "1px solid var(--border-color)",
              }}
            >
              {Object.entries(settings).map(([group, groupData]) => {
                if (
                  typeof groupData === "object" &&
                  groupData !== null &&
                  !Array.isArray(groupData)
                ) {
                  return (
                    <div
                      key={group}
                      style={{
                        marginBottom: "30px",
                        borderBottom: "1px solid var(--border-color)",
                        paddingBottom: "20px",
                      }}
                    >
                      <h3
                        style={{
                          textTransform: "capitalize",
                          margin: "0 0 15px 0",
                        }}
                      >
                        {group.replace(/_/g, " ")}
                      </h3>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr",
                          gap: "10px",
                        }}
                      >
                        {renderFields(groupData, group)}
                      </div>
                    </div>
                  );
                }
                return null;
              })}
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                marginTop: "20px",
              }}
            >
              <button
                type="submit"
                className="action-button"
                disabled={loading}
              >
                <Save size={16} style={{ marginRight: "5px" }} /> Save Settings
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default ServerConfig;
