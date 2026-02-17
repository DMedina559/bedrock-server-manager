import React, { useState, useEffect, useCallback } from "react";
import { useToast } from "../ToastContext";
import { post, get } from "../api";
import { useServer } from "../ServerContext";
import { useNavigate } from "react-router-dom";
import { PlusSquare, RefreshCw } from "lucide-react";
import useWebSocket from "../hooks/useWebSocket";

const ServerInstall = () => {
  const [formData, setFormData] = useState({
    server_name: "",
    server_version: "LATEST",
    server_zip_path: "",
    overwrite: false,
  });
  const [specificVersion, setSpecificVersion] = useState("");
  const [customZips, setCustomZips] = useState([]);
  const [loading, setLoading] = useState(false);
  const [installTaskId, setInstallTaskId] = useState(null);
  const { addToast } = useToast();
  const navigate = useNavigate();
  const { refreshServers, setSelectedServer } = useServer();
  const { lastMessage, subscribe, unsubscribe } = useWebSocket();

  const fetchCustomZips = async () => {
    try {
      const data = await get("/api/downloads/list");
      if (data && data.status === "success") {
        setCustomZips(data.custom_zips || []);
      }
    } catch (error) {
      console.warn("Failed to fetch custom zips", error);
    }
  };

  const handleInstallSuccess = useCallback(async () => {
    await refreshServers();
    setSelectedServer(formData.server_name);

    if (installTaskId) {
      unsubscribe(`task:${installTaskId}`);
    }

    setLoading(false);
    navigate("/server-properties", { state: { setupFlow: true } });
  }, [
    formData.server_name,
    installTaskId,
    navigate,
    refreshServers,
    setSelectedServer,
    unsubscribe,
  ]);

  useEffect(() => {
    fetchCustomZips();
  }, []);

  // Monitor WebSocket messages for task updates
  useEffect(() => {
    if (installTaskId && lastMessage) {
      const topic = `task:${installTaskId}`;
      if (lastMessage.topic === topic && lastMessage.type === "task_update") {
        const taskData = lastMessage.data;
        if (taskData.status === "success") {
          addToast("Installation completed successfully!", "success");
          handleInstallSuccess();
        } else if (taskData.status === "error") {
          addToast(`Installation failed: ${taskData.message}`, "error");
          setLoading(false);
          setInstallTaskId(null);
          unsubscribe(topic);
        } else if (taskData.message) {
          // Progress update or similar
        }
      }
    }
  }, [lastMessage, installTaskId, addToast, handleInstallSuccess, unsubscribe]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.server_name) {
      addToast("Server name is required", "error");
      return;
    }

    if (formData.server_version === "SPECIFIC" && !specificVersion) {
      addToast("Please enter a specific version number.", "error");
      return;
    }

    const payload = { ...formData };
    if (formData.server_version === "SPECIFIC") {
      payload.server_version = specificVersion.trim();
    }

    setLoading(true);
    try {
      const response = await post("/api/server/install", payload);

      const initiateMonitoring = (taskId) => {
        setInstallTaskId(taskId);
        subscribe(`task:${taskId}`);
        addToast("Installation started. Please wait...", "info");
      };

      if (response && response.status === "confirm_needed") {
        if (confirm(response.message)) {
          const confirmData = { ...payload, overwrite: true };
          const confirmResponse = await post(
            "/api/server/install",
            confirmData,
          );
          if (confirmResponse && confirmResponse.task_id) {
            initiateMonitoring(confirmResponse.task_id);
          }
        } else {
          setLoading(false);
        }
      } else if (response && response.task_id) {
        initiateMonitoring(response.task_id);
      } else {
        addToast("Failed to start installation task.", "error");
        setLoading(false);
      }
    } catch (error) {
      addToast(error.message || "Failed to install server.", "error");
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Install New Server</h1>
      </div>

      <div
        style={{
          maxWidth: "600px",
          margin: "0 auto",
          background: "var(--container-background-color)",
          padding: "30px",
          border: "1px solid var(--border-color)",
          borderRadius: "8px",
        }}
      >
        <form onSubmit={handleSubmit} className="form-group">
          <div style={{ marginBottom: "20px" }}>
            <label className="form-label" htmlFor="server_name">
              Server Name
            </label>
            <input
              type="text"
              id="server_name"
              name="server_name"
              className="form-input"
              value={formData.server_name}
              onChange={handleChange}
              placeholder="MyBedrockServer"
              required
              pattern="^[a-zA-Z0-9_\-]+$"
              title="Letters, numbers, underscores, and hyphens only."
              disabled={loading}
            />
            <small style={{ color: "#888" }}>
              Unique name for the server instance.
            </small>
          </div>

          <div style={{ marginBottom: "20px" }}>
            <label className="form-label" htmlFor="server_version">
              Server Version
            </label>
            <select
              id="server_version"
              name="server_version"
              className="form-input"
              value={formData.server_version}
              onChange={handleChange}
              disabled={loading}
            >
              <option value="LATEST">LATEST (Stable)</option>
              <option value="PREVIEW">PREVIEW (Beta)</option>
              <option value="CUSTOM">CUSTOM (Use uploaded ZIP)</option>
              <option value="SPECIFIC">
                SPECIFIC VERSION (Enter manually)
              </option>
            </select>
          </div>

          {formData.server_version === "SPECIFIC" && (
            <div
              style={{
                marginBottom: "20px",
                padding: "15px",
                background: "#f9f9f9",
                border: "1px solid #ddd",
                borderRadius: "5px",
              }}
            >
              <label className="form-label" htmlFor="specificVersion">
                Enter Version Number
              </label>
              <input
                type="text"
                id="specificVersion"
                className="form-input"
                value={specificVersion}
                onChange={(e) => setSpecificVersion(e.target.value)}
                placeholder="e.g., 1.21.114.1 or 1.21.130.22-preview"
                required
                disabled={loading}
              />
              <small style={{ color: "#666" }}>
                Must be a valid version number available from Mojang.
              </small>
            </div>
          )}

          {formData.server_version === "CUSTOM" && (
            <div
              style={{
                marginBottom: "20px",
                padding: "15px",
                background: "#f9f9f9",
                border: "1px solid #ddd",
                borderRadius: "5px",
              }}
            >
              <label className="form-label" htmlFor="server_zip_path">
                Select Custom ZIP
              </label>
              {customZips.length > 0 ? (
                <select
                  id="server_zip_path"
                  name="server_zip_path"
                  className="form-input"
                  value={formData.server_zip_path}
                  onChange={handleChange}
                  required
                  disabled={loading}
                >
                  <option value="">-- Select ZIP File --</option>
                  {customZips.map((zip) => (
                    <option key={zip} value={zip}>
                      {zip}
                    </option>
                  ))}
                </select>
              ) : (
                <div style={{ color: "red" }}>
                  No custom ZIP files found in <code>downloads/custom/</code>.
                  Please upload one first.
                </div>
              )}
            </div>
          )}

          <div style={{ marginBottom: "30px" }}>
            <label
              className="form-label"
              style={{
                display: "flex",
                alignItems: "center",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                name="overwrite"
                checked={formData.overwrite}
                onChange={handleChange}
                style={{ marginRight: "10px" }}
                disabled={loading}
              />
              Overwrite existing server if name conflicts?
            </label>
          </div>

          <button
            type="submit"
            className="action-button"
            disabled={loading}
            style={{ width: "100%", justifyContent: "center" }}
          >
            {loading ? (
              <RefreshCw
                className="spin"
                size={20}
                style={{ marginRight: "8px" }}
              />
            ) : (
              <PlusSquare size={20} style={{ marginRight: "8px" }} />
            )}
            {loading ? "Installing..." : "Install Server"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ServerInstall;
