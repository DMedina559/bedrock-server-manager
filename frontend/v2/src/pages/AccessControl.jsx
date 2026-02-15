import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { List, Shield, Trash2, Plus } from "lucide-react";

const AccessControl = () => {
  const [activeTab, setActiveTab] = useState("allowlist");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newItem, setNewItem] = useState("");
  const [permissionLevel, setPermissionLevel] = useState("member"); // For permissions
  const { addToast } = useToast();

  useEffect(() => {
    fetchItems();
  }, [activeTab]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      // Endpoints: /api/allowlist, /api/permissions
      // Legacy uses similar.
      const endpoint = `/api/${activeTab}`;
      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();
        setItems(data);
      } else {
        addToast(`Failed to fetch ${activeTab}`, "error");
      }
    } catch (error) {
      addToast(`Error fetching ${activeTab}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newItem) return;

    try {
      const endpoint = `/api/${activeTab}`;
      let body;
      if (activeTab === "allowlist") {
        body = { name: newItem };
      } else {
        body = { name: newItem, permission: permissionLevel }; // 'xuid' usually handled by server
      }

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (response.ok) {
        addToast("Item added successfully.", "success");
        setNewItem("");
        fetchItems();
      } else {
        const data = await response.json();
        addToast(data.detail || "Failed to add item.", "error");
      }
    } catch (error) {
      addToast("Error adding item.", "error");
    }
  };

  const handleDelete = async (identifier) => {
    // identifier is name or xuid
    if (!confirm(`Remove ${identifier}?`)) return;

    try {
      const endpoint = `/api/${activeTab}/${identifier}`;
      const response = await fetch(endpoint, { method: "DELETE" });
      if (response.ok) {
        addToast("Item removed.", "success");
        fetchItems();
      } else {
        addToast("Failed to remove item.", "error");
      }
    } catch (error) {
      addToast("Error removing item.", "error");
    }
  };

  return (
    <div className="container" style={{ padding: "20px" }}>
      <div className="header">
        <h1>Access Control</h1>
      </div>

      <div
        className="tabs"
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-color)",
          marginBottom: "20px",
        }}
      >
        <button
          className={`tab ${activeTab === "allowlist" ? "active" : ""}`}
          onClick={() => setActiveTab("allowlist")}
          style={{
            background: "none",
            border: "none",
            borderBottom:
              activeTab === "allowlist"
                ? "2px solid var(--primary-button-background-color)"
                : "none",
            color:
              activeTab === "allowlist"
                ? "var(--text-color)"
                : "var(--text-color-muted, #888)",
            padding: "10px 20px",
            cursor: "pointer",
            fontSize: "1em",
          }}
        >
          Allowlist
        </button>
        <button
          className={`tab ${activeTab === "permissions" ? "active" : ""}`}
          onClick={() => setActiveTab("permissions")}
          style={{
            background: "none",
            border: "none",
            borderBottom:
              activeTab === "permissions"
                ? "2px solid var(--primary-button-background-color)"
                : "none",
            color:
              activeTab === "permissions"
                ? "var(--text-color)"
                : "var(--text-color-muted, #888)",
            padding: "10px 20px",
            cursor: "pointer",
            fontSize: "1em",
          }}
        >
          Permissions
        </button>
      </div>

      {/* Add Form */}
      <form
        onSubmit={handleAdd}
        style={{
          marginBottom: "20px",
          display: "flex",
          gap: "10px",
          alignItems: "flex-end",
        }}
      >
        <div style={{ flexGrow: 1 }}>
          <label className="form-label">Player Name (Gamertag)</label>
          <input
            type="text"
            className="form-input"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            required
            style={{ width: "100%" }}
          />
        </div>
        {activeTab === "permissions" && (
          <div>
            <label className="form-label">Permission Level</label>
            <select
              className="form-input"
              value={permissionLevel}
              onChange={(e) => setPermissionLevel(e.target.value)}
            >
              <option value="visitor">Visitor</option>
              <option value="member">Member</option>
              <option value="operator">Operator</option>
            </select>
          </div>
        )}
        <button
          type="submit"
          className="button button-primary"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "5px",
            marginBottom: "2px",
          }}
        >
          <Plus size={18} /> Add
        </button>
      </form>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <table
          className="table"
          style={{ width: "100%", borderCollapse: "collapse" }}
        >
          <thead>
            <tr
              style={{
                background: "var(--table-header-background-color)",
                textAlign: "left",
              }}
            >
              <th style={{ padding: "10px" }}>Name</th>
              <th style={{ padding: "10px" }}>XUID</th>
              {activeTab === "permissions" && (
                <th style={{ padding: "10px" }}>Permission</th>
              )}
              <th style={{ padding: "10px" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr
                key={index}
                style={{ borderBottom: "1px solid var(--table-border-color)" }}
              >
                <td style={{ padding: "10px" }}>{item.name}</td>
                <td style={{ padding: "10px" }}>{item.xuid}</td>
                {activeTab === "permissions" && (
                  <td style={{ padding: "10px" }}>{item.permission}</td>
                )}
                <td style={{ padding: "10px" }}>
                  <button
                    className="button button-danger"
                    onClick={() => handleDelete(item.name || item.xuid)} // API supports name deletion usually
                    title="Remove"
                    style={{ padding: "5px 10px" }}
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td
                  colSpan={activeTab === "permissions" ? 4 : 3}
                  style={{
                    textAlign: "center",
                    padding: "20px",
                    color: "#888",
                  }}
                >
                  No entries found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default AccessControl;
