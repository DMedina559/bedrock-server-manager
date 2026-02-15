import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { Package, Trash2, Upload } from "lucide-react";

const Content = () => {
  const [activeTab, setActiveTab] = useState("worlds");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    fetchContent();
  }, [activeTab]);

  const fetchContent = async () => {
    setLoading(true);
    try {

      const endpoint = `/api/content/${activeTab}`;
      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();
        setItems(data);
      } else {
        addToast(`Failed to fetch ${activeTab.replace("_", " ")}`, "error");
      }
    } catch (error) {
      addToast(`Error fetching content`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (name) => {
    if (!confirm(`Delete ${name}?`)) return;

    try {
      const endpoint = `/api/content/${activeTab}/${name}`;
      const response = await fetch(endpoint, { method: "DELETE" });
      if (response.ok) {
        addToast(`${name} deleted successfully`, "success");
        fetchContent();
      } else {
        addToast(`Failed to delete ${name}`, "error");
      }
    } catch (error) {
      addToast("Error deleting item", "error");
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    addToast("Uploading file...", "info");

    try {
      const response = await fetch("/api/content/upload", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        addToast("File uploaded and installed successfully", "success");
        fetchContent();
      } else {
        const data = await response.json();
        addToast(data.detail || "Upload failed", "error");
      }
    } catch (error) {
      addToast("Error uploading file", "error");
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
        <h1>Content Management</h1>
        <div style={{ position: "relative" }}>
          <input
            type="file"
            id="file-upload"
            style={{ display: "none" }}
            onChange={handleFileUpload}
            accept=".mcworld,.mcpack,.mcaddon,.zip"
          />
          <label
            htmlFor="file-upload"
            className="button button-primary"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "5px",
              cursor: "pointer",
            }}
          >
            <Upload size={18} /> Upload Content
          </label>
        </div>
      </div>

      <div
        className="tabs"
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-color)",
          marginBottom: "20px",
        }}
      >
        {["worlds", "behavior_packs", "resource_packs"].map((tab) => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? "active" : ""}`}
            onClick={() => setActiveTab(tab)}
            style={{
              background: "none",
              border: "none",
              borderBottom:
                activeTab === tab
                  ? "2px solid var(--primary-button-background-color)"
                  : "none",
              color:
                activeTab === tab
                  ? "var(--text-color)"
                  : "var(--text-color-muted, #888)",
              padding: "10px 20px",
              cursor: "pointer",
              fontSize: "1em",
              textTransform: "capitalize",
            }}
          >
            {tab.replace("_", " ")}
          </button>
        ))}
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
            gap: "20px",
          }}
        >
          {items.map((item, index) => (
            <div
              key={index}
              style={{
                background: "var(--container-background-color)",
                border: "1px solid var(--border-color)",
                padding: "15px",
                borderRadius: "5px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  overflow: "hidden",
                }}
              >
                <Package size={24} />
                <span
                  style={{
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={item.name || item}
                >
                  {item.name || item}
                </span>
              </div>
              <button
                className="button button-danger"
                onClick={() => handleDelete(item.name || item)}
                title="Delete"
                style={{ padding: "5px" }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {items.length === 0 && (
            <div
              style={{
                gridColumn: "1/-1",
                textAlign: "center",
                padding: "20px",
                color: "#888",
              }}
            >
              No items found.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Content;
