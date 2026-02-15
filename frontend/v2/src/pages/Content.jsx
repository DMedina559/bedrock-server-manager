import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { get, post, del } from "../api";
import { Package, Globe, Upload, Download, RefreshCw, Trash2 } from "lucide-react";

const Content = () => {
  const { selectedServer } = useServer();
  const [activeTab, setActiveTab] = useState("worlds");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (selectedServer) {
      fetchItems();
    }
  }, [selectedServer, activeTab]);

  const fetchItems = async () => {
    if (!selectedServer) return;
    setLoading(true);
    try {
      const endpoint = activeTab === "worlds" ? "/api/content/worlds" : "/api/content/addons";
      const data = await get(endpoint);
      if (data && data.status === "success") {
        setItems(data.files || []);
      } else {
        addToast(`Failed to load ${activeTab}: ${data?.message || "Unknown error"}`, "error");
        setItems([]);
      }
    } catch (error) {
      addToast(error.message || `Error fetching ${activeTab}`, "error");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async (filename) => {
    if (!selectedServer) return;
    const type = activeTab === "worlds" ? "world" : "addon";
    if (!confirm(`Install ${type} '${filename}' to server '${selectedServer}'? Server will restart.`)) return;

    addToast(`Installing ${type}...`, "info");
    try {
      await post(`/api/server/${selectedServer}/${type}/install`, { filename });
      addToast("Installation task started.", "success");
    } catch (error) {
      addToast(error.message || `Failed to install ${type}.`, "error");
    }
  };

  const handleExportWorld = async () => {
    if (!selectedServer) return;
    if (!confirm("Export current world? Server will restart.")) return;

    addToast("Exporting world...", "info");
    try {
      await post(`/api/server/${selectedServer}/world/export`);
      addToast("Export task started.", "success");
    } catch (error) {
      addToast(error.message || "Failed to export world.", "error");
    }
  };

  const handleResetWorld = async () => {
    if (!selectedServer) return;
    if (!confirm("WARNING: This will DELETE the current world. Are you sure?")) return;

    addToast("Resetting world...", "info");
    try {
      await del(`/api/server/${selectedServer}/world/reset`);
      addToast("Reset task started.", "success");
    } catch (error) {
      addToast(error.message || "Failed to reset world.", "error");
    }
  };

  const handleUpload = async (e) => {
      e.preventDefault();
      // Upload is handled via FormData to /api/content/upload
      // This endpoint is provided by a plugin usually.
      const fileInput = e.target.files[0];
      if (!fileInput) return;

      const formData = new FormData();
      formData.append("files", fileInput); // Legacy uses 'files' field?
      // Need to verify upload endpoint signature.
      // Assuming standard upload.

      addToast("Uploading...", "info");
      try {
          const response = await fetch("/api/content/upload", {
              method: "POST",
              headers: {
                  "Authorization": `Bearer ${localStorage.getItem("jwt_token")}`
              },
              body: formData
          });

          if (response.ok) {
              addToast("Upload successful.", "success");
              fetchItems();
          } else {
              const resData = await response.json();
              addToast(resData.message || "Upload failed.", "error");
          }
      } catch (err) {
          addToast("Upload error.", "error");
      }
  };

  if (!selectedServer) {
    return (
      <div className="container">
        <div className="message-box message-warning" style={{ textAlign: "center", marginTop: "50px", padding: "20px", border: "1px solid orange", color: "orange" }}>
          Please select a server.
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Content Management: {selectedServer}</h1>
        <div style={{ display: "flex", gap: "10px" }}>
            <button className="action-button secondary" onClick={fetchItems} disabled={loading}>
                <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
            </button>
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab-button ${activeTab === "worlds" ? "active" : ""}`}
          onClick={() => setActiveTab("worlds")}
        >
          Worlds
        </button>
        <button
          className={`tab-button ${activeTab === "addons" ? "active" : ""}`}
          onClick={() => setActiveTab("addons")}
        >
          Addons
        </button>
      </div>

      {/* Explicitly using a div for tab content, ensuring styles are applied */}
      <div className="tab-content" style={{ background: "var(--container-background-color, #333)", padding: "20px", border: "1px solid var(--border-color, #555)", borderTop: "none", minHeight: "200px" }}>

        {/* Actions Area */}
        <div style={{ marginBottom: "20px", padding: "15px", background: "var(--server-card-background-color, #444)", borderRadius: "5px", display: "flex", gap: "15px", flexWrap: "wrap", alignItems: "center", border: "1px solid var(--border-color, #555)" }}>
            <div style={{ marginRight: "auto" }}>
                <label className="action-button secondary" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center" }}>
                    <Upload size={16} style={{ marginRight: "5px" }} /> Upload .mcworld/.mcaddon
                    <input type="file" style={{ display: "none" }} onChange={handleUpload} accept=".mcworld,.mcaddon,.mcpack,.zip" />
                </label>
            </div>

            {activeTab === "worlds" && (
                <>
                    <button className="action-button" onClick={handleExportWorld}>
                        <Download size={16} style={{ marginRight: "5px" }} /> Export Current World
                    </button>
                    <button className="action-button danger-button" onClick={handleResetWorld}>
                        <Trash2 size={16} style={{ marginRight: "5px" }} /> Reset World
                    </button>
                </>
            )}
        </div>

        {/* List */}
        {loading ? (
          <div style={{ padding: "20px", textAlign: "center" }}>
            <RefreshCw className="spin" style={{ display: "inline-block", marginRight: "10px" }} /> Loading content...
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "15px" }}>
            {items && items.length > 0 ? (
              items.map((filename) => (
                <div key={filename} style={{ background: "var(--server-card-background-color, #444)", border: "1px solid var(--server-card-border-color, #555)", padding: "15px", borderRadius: "5px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center" }}>
                    {activeTab === "worlds" ? <Globe size={32} style={{ marginBottom: "10px", color: "#4CAF50" }} /> : <Package size={32} style={{ marginBottom: "10px", color: "#2196F3" }} />}
                    <div style={{ fontWeight: "bold", marginBottom: "10px", wordBreak: "break-all" }}>{filename}</div>
                    <button className="action-button" style={{ marginTop: "auto", width: "100%" }} onClick={() => handleInstall(filename)}>
                        Install
                    </button>
                </div>
              ))
            ) : (
                <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: "30px", color: "#888", fontStyle: "italic" }}>
                    No {activeTab} available. Upload one or check the `downloads` folder.
                </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Content;
