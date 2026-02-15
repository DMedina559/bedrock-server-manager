import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { get, post, del } from "../api";
import { Trash2, Plus, RefreshCw, ArrowRight } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

const AccessControl = () => {
  const { selectedServer } = useServer();
  const [activeTab, setActiveTab] = useState("allowlist");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newItemName, setNewItemName] = useState("");
  const [permissionLevel, setPermissionLevel] = useState("member");
  const [ignoresPlayerLimit, setIgnoresPlayerLimit] = useState(false);
  const { addToast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const setupFlow = location.state?.setupFlow;

  useEffect(() => {
    if (location.state?.tab) {
        setActiveTab(location.state.tab);
    }
  }, [location.state]);

  useEffect(() => {
    if (selectedServer) {
      fetchItems();
    }
  }, [selectedServer, activeTab]);

  const fetchItems = async () => {
    if (!selectedServer) return;
    setLoading(true);
    try {
      const endpoint = activeTab === "allowlist"
        ? `/api/server/${selectedServer}/allowlist/get`
        : `/api/server/${selectedServer}/permissions/get`;

      const data = await get(endpoint);
      if (data && data.status === "success") {
        if (activeTab === "allowlist") {
            setItems(data.players || []);
        } else {
            // Permissions data is nested in data.data.permissions
            setItems(data.data?.permissions || []);
        }
      } else {
        addToast(`Failed to load ${activeTab}: ${data?.message || "Unknown error"}`, "error");
        setItems([]);
      }
    } catch (error) {
      console.error(`Error fetching ${activeTab}:`, error);
      addToast(error.message || `Error fetching ${activeTab}`, "error");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const handleNextStep = () => {
      if (activeTab === "allowlist") {
          setActiveTab("permissions");
      } else {
          navigate("/server-config", { state: { setupFlow: true } });
      }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!selectedServer || !newItemName) return;

    try {
      if (activeTab === "allowlist") {
        await post(`/api/server/${selectedServer}/allowlist/add`, {
          players: [newItemName],
          ignoresPlayerLimit: ignoresPlayerLimit,
        });
      } else {

        await post(`/api/server/${selectedServer}/permissions/set`, {
          permissions: [{ xuid: "", name: newItemName, permission_level: permissionLevel }],
        });
      }

      addToast("Item added successfully.", "success");
      setNewItemName("");
      setIgnoresPlayerLimit(false);
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
        <div style={{ display: "flex", gap: "10px" }}>
            {!setupFlow && (
                <button
                  className="action-button secondary"
                  onClick={fetchItems}
                  disabled={loading}
                  title="Reload current list"
                >
                    <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
                </button>
            )}
            {setupFlow && (
                <button className="action-button" onClick={handleNextStep}>
                    Next Step <ArrowRight size={16} style={{ marginLeft: "5px" }} />
                </button>
            )}
        </div>
      </div>

      {setupFlow && (
          <div className="message-box message-info" style={{ marginBottom: "20px" }}>
              <strong>Setup Wizard (Step {activeTab === 'allowlist' ? '2' : '3'}/4):</strong> Configure {activeTab}.
          </div>
      )}

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

      <div className="tab-content" style={{ background: "var(--container-background-color, #333)", padding: "20px", border: "1px solid var(--border-color, #555)", borderTop: "none", minHeight: "200px" }}>

        {/* Add Form */}
        <form onSubmit={handleAdd} className="form-group" style={{ display: "flex", gap: "10px", alignItems: "flex-end", marginBottom: "20px", flexWrap: "wrap" }}>
          <div style={{ flexGrow: 1, minWidth: "200px" }}>
            <label className="form-label">Player Name (Gamertag)</label>
            <input
              type="text"
              className="form-input"
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
              required
              style={{ width: "100%" }}
              placeholder={activeTab === "allowlist" ? "Enter Gamertag to allow" : "Enter Gamertag for permissions"}
            />
          </div>

          {activeTab === "permissions" && (
            <div style={{ minWidth: "150px" }}>
              <label className="form-label">Level</label>
              <select
                className="form-input"
                value={permissionLevel}
                onChange={(e) => setPermissionLevel(e.target.value)}
                style={{ width: "100%" }}
              >
                <option value="visitor">Visitor</option>
                <option value="member">Member</option>
                <option value="operator">Operator</option>
              </select>
            </div>
          )}

          {activeTab === "allowlist" && (
             <div style={{ display: "flex", alignItems: "center", marginBottom: "10px", minWidth: "150px" }}>
                 <input
                     type="checkbox"
                     id="ignoreLimit"
                     checked={ignoresPlayerLimit}
                     onChange={(e) => setIgnoresPlayerLimit(e.target.checked)}
                     style={{ marginRight: "10px" }}
                 />
                 <label htmlFor="ignoreLimit" className="form-label" style={{ marginBottom: 0, cursor: "pointer" }}>Ignore Limit</label>
             </div>
          )}

          <button type="submit" className="action-button" disabled={loading || !newItemName}>
            <Plus size={16} style={{ marginRight: "5px" }} /> Add
          </button>
        </form>

        {/* List */}
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
                <th>XUID</th>
                {activeTab === "allowlist" && <th>Ignores Limit</th>}
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
                    {activeTab === "allowlist" && (
                        <td>
                            {item.ignoresPlayerLimit ? (
                                <span style={{ color: "var(--success-color, #4CAF50)" }}>Yes</span>
                            ) : "No"}
                        </td>
                    )}
                    {activeTab === "permissions" && <td>{item.permission_level || item.permission}</td>}
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
                <tr className="no-servers-row">
                  <td colSpan={activeTab === "permissions" ? 4 : (activeTab === "allowlist" ? 4 : 3)} className="no-servers" style={{ textAlign: "center", color: "#888", fontStyle: "italic", padding: "15px" }}>
                    No entries found in {activeTab}. Use the form above to add one.
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

export default AccessControl;
