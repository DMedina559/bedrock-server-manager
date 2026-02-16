import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { get, post, del } from "../api";
import { Upload, Trash2, Folder, RefreshCw, Layers } from "lucide-react";

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
      let endpoint = "";
      if (activeTab === "worlds") {
        endpoint = `/api/content/worlds`;
      } else {
        endpoint = `/api/content/addons`;
      }

      const data = await get(endpoint);
      if (data && data.status === "success") {
        if (activeTab === "worlds") {
             setItems(data.worlds || []);
        } else {
             setItems(data.addons || []);
        }
      } else {
        addToast(`Failed to load ${activeTab}`, "error");
        setItems([]);
      }
    } catch (error) {
      console.error(`Error fetching ${activeTab}:`, error);
      addToast(`Error fetching ${activeTab}`, "error");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (item) => {
    if (!confirm(`Delete ${item.name}? This cannot be undone.`)) return;

    try {
      const endpoint = activeTab === "worlds"
        ? `/api/server/${selectedServer}/world/delete` // This endpoint might need verification
        : `/api/addons/delete`; // Placeholder

      addToast("Delete functionality requires specific API endpoints.", "info");

    } catch (error) {
      addToast("Failed to delete item.", "error");
    }
  };

  const handleUpload = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      // Determine type based on tab or file extension
      const type = activeTab === "worlds" ? "world" : "addon";
      formData.append("type", type);

      try {
          setLoading(true);
          const response = await fetch(`/api/content/upload`, {
              method: "POST",
              body: formData,
              headers: {
                  "Authorization": `Bearer ${localStorage.getItem("jwt_token")}`
              }
          });

          const data = await response.json();

          if (response.ok && data.status === "success") {
              addToast("Upload successful.", "success");
              fetchItems();
          } else {
              addToast(`Upload failed: ${data.message || "Unknown error"}`, "error");
          }
      } catch (error) {
          addToast("Upload failed.", "error");
      } finally {
          setLoading(false);
          e.target.value = null; // Reset input
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
        <button
            className="action-button secondary"
            onClick={fetchItems}
            disabled={loading}
        >
            <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
        </button>
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

      <div className="tab-content">
        <div style={{ marginBottom: "20px", padding: "15px", background: "var(--input-background-color)", borderRadius: "5px" }}>
            <h3 style={{ marginTop: 0 }}>Upload {activeTab === "worlds" ? "World (.zip, .mcworld)" : "Addon (.mcpack, .mcaddon, .zip)"}</h3>
            <input type="file" onChange={handleUpload} disabled={loading} className="form-input" />
        </div>

        {loading ? (
             <div style={{ padding: "20px", textAlign: "center", color: "#ccc" }}>
                 <RefreshCw className="spin" style={{ display: "inline-block", marginRight: "10px" }} /> Loading data...
             </div>
        ) : (
            <div className="table-responsive-wrapper">
            <table className="server-table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Details</th>
                  <th style={{ width: "100px" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items && items.length > 0 ? (
                  items.map((item, idx) => (
                    <tr key={idx}>
                      <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              {activeTab === "worlds" ? <Folder size={16} /> : <Layers size={16} />}
                              {item.name}
                          </div>
                      </td>
                      <td>
                          {activeTab === "worlds" ? (
                              <span style={{ fontSize: "0.9em", color: "#aaa" }}>{item.level_name || "N/A"}</span>
                          ) : (
                              <span style={{ fontSize: "0.9em", color: "#aaa" }}>v{item.version || "N/A"}</span>
                          )}
                      </td>
                      <td>
                        <button
                          className="action-button danger-button"
                          onClick={() => handleDelete(item)}
                          title="Delete"
                          style={{ padding: "5px 10px" }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr className="no-servers-row">
                    <td colSpan="3" className="no-servers" style={{ textAlign: "center", color: "#888", fontStyle: "italic", padding: "15px" }}>
                      No {activeTab} found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            </div>
        )}
      </div>
    </div>
  );
};

export default Content;
