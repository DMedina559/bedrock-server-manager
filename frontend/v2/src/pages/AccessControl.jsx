import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { get, post, del } from "../api";
import { Trash2, Plus, RefreshCw } from "lucide-react";

const AccessControl = () => {
  const { selectedServer } = useServer();
  const [activeTab, setActiveTab] = useState("allowlist");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newItemName, setNewItemName] = useState("");
  const [permissionLevel, setPermissionLevel] = useState("member");
  const { addToast } = useToast();

  useEffect(() => {
    if (selectedServer) {
      fetchItems();
    }
  }, [selectedServer, activeTab]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const endpoint = activeTab === "allowlist"
        ? `/api/server/${selectedServer}/allowlist/get`
        : `/api/server/${selectedServer}/permissions/get`;

      const data = await get(endpoint);
      if (data && data.status === "success") {
        setItems(data.data || []);
      } else {
        addToast(`Failed to load ${activeTab}`, "error");
        setItems([]);
      }
    } catch (error) {
      addToast(error.message || `Error fetching ${activeTab}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!selectedServer || !newItemName) return;

    try {
      if (activeTab === "allowlist") {
        await post(`/api/server/${selectedServer}/allowlist/add`, {
          players: [newItemName],
          ignoresPlayerLimit: false,
        });
      } else {

        await post(`/api/server/${selectedServer}/permissions/set`, {
          permissions: [{ xuid: "", name: newItemName, permission_level: permissionLevel }],
        });
      }

      addToast("Item added successfully.", "success");
      setNewItemName("");
      fetchItems();
    } catch (error) {
      addToast(error.message || "Failed to add item.", "error");
    }
  };

  const handleRemove = async (item) => {
    if (!selectedServer) return;
    if (!confirm(`Remove ${item.name || item.xuid}?`)) return;

    try {
      if (activeTab === "allowlist") {
        await del(`/api/server/${selectedServer}/allowlist/remove`, {
            body: { players: [item.name] }
        });
      } else {
        addToast("To remove permission, set level to default (Member/Visitor).", "info");
        return;
      }
      addToast("Item removed.", "success");
      fetchItems();
    } catch (error) {
      addToast(error.message || "Failed to remove item.", "error");
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
        <h1>Access Control: {selectedServer}</h1>
        <button className="action-button secondary" onClick={fetchItems} disabled={loading}>
            <RefreshCw size={16} style={{ marginRight: "5px" }} /> Refresh
        </button>
      </div>

      <div className="tabs">
        <button
          className={`tab-button ${activeTab === "allowlist" ? "active" : ""}`}
          onClick={() => setActiveTab("allowlist")}
        >
          Allowlist
        </button>
        <button
          className={`tab-button ${activeTab === "permissions" ? "active" : ""}`}
          onClick={() => setActiveTab("permissions")}
        >
          Permissions
        </button>
      </div>

      <div className="tab-content" style={{ background: "var(--container-background-color)", padding: "20px", border: "1px solid var(--border-color)", borderTop: "none" }}>

        {/* Add Form */}
        <form onSubmit={handleAdd} className="form-group" style={{ display: "flex", gap: "10px", alignItems: "flex-end", marginBottom: "20px" }}>
          <div style={{ flexGrow: 1 }}>
            <label className="form-label">Player Name (Gamertag)</label>
            <input
              type="text"
              className="form-input"
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
              required
              style={{ width: "100%" }}
            />
          </div>

          {activeTab === "permissions" && (
            <div>
              <label className="form-label">Level</label>
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

          <button type="submit" className="action-button">
            <Plus size={16} style={{ marginRight: "5px" }} /> Add
          </button>
        </form>

        {/* List */}
        {loading ? (
          <div>Loading...</div>
        ) : (
          <table className="table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>XUID</th>
                {activeTab === "permissions" && <th>Permission</th>}
                <th style={{ width: "100px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items && items.length > 0 ? (
                items.map((item, idx) => (
                  <tr key={idx}>
                    <td>{item.name || "Unknown"}</td>
                    <td>{item.xuid || "N/A"}</td>
                    {activeTab === "permissions" && <td>{item.permission}</td>}
                    <td>
                      {activeTab === "allowlist" && (
                        <button
                          className="action-button danger-button"
                          onClick={() => handleRemove(item)}
                          title="Remove"
                          style={{ padding: "5px 10px" }}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={activeTab === "permissions" ? 4 : 3} style={{ textAlign: "center", color: "#888", fontStyle: "italic", padding: "15px" }}>
                    No entries found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default AccessControl;
