import React from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useServer } from "../ServerContext";
import {
  LayoutDashboard,
  Users,
  Settings,
  Database,
  Server,
  ScrollText,
  LogOut,
  Package,
  User,
  Plug,
  Wrench,
  Shield,
  RefreshCw,
} from "lucide-react";
// Styles are global

const Sidebar = () => {
  const { logout, user } = useAuth();
  const {
    servers,
    selectedServer,
    setSelectedServer,
    refreshServers,
    loading,
  } = useServer();

  const handleServerChange = (e) => {
    setSelectedServer(e.target.value);
  };

  // Grouped Navigation Items
  const serverNavItems = [
    { path: "/", label: "Monitor", icon: <LayoutDashboard size={20} /> },
    {
      path: "/server-config",
      label: "Config",
      icon: <Wrench size={20} />,
    },
    {
      path: "/server-properties",
      label: "Properties",
      icon: <Server size={20} />,
    },
    {
      path: "/access-control",
      label: "Access Control",
      icon: <Shield size={20} />,
    },
    { path: "/backups", label: "Backups", icon: <Database size={20} /> },
    { path: "/content", label: "Content", icon: <Package size={20} /> },
  ];

  const globalNavItems = [
    { path: "/plugins", label: "Plugins", icon: <Plug size={20} /> },
    { path: "/users", label: "Users", icon: <Users size={20} /> },
    { path: "/bsm-settings", label: "Settings", icon: <Settings size={20} /> },
    { path: "/audit-log", label: "Audit Log", icon: <ScrollText size={20} /> },
  ];

  return (
    <aside className="sidebar-nav">
      <div className="sidebar-header" style={{ padding: "15px 0", textAlign: "center", borderBottom: "1px solid var(--sidebar-border-color)" }}>
        <h2 style={{ margin: 0, fontSize: "1.2em", color: "var(--header-text-color)" }}>BSM V2</h2>
      </div>

      {/* Server Selector Section */}
      <div style={{ padding: "15px 15px 5px" }}>
        <label
          htmlFor="server-select"
          style={{
            display: "block",
            marginBottom: "5px",
            color: "#aaa",
            fontSize: "0.85em",
          }}
        >
          Selected Server:
        </label>
        <div style={{ display: "flex", gap: "5px" }}>
          <select
            id="server-select"
            value={selectedServer || ""}
            onChange={handleServerChange}
            disabled={loading || servers.length === 0}
            className="form-input"
            style={{
              width: "100%",
              padding: "6px",
              fontSize: "0.9em"
            }}
          >
            {loading ? (
              <option value="">Loading...</option>
            ) : servers.length === 0 ? (
              <option value="">No Servers</option>
            ) : (
              <>
                <option value="" disabled>
                  -- Select --
                </option>
                {servers.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </>
            )}
          </select>
          <button
            onClick={refreshServers}
            title="Refresh Server List"
            className="action-button secondary"
            style={{
              padding: "5px 8px",
              margin: 0
            }}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

        {/* Server Management Section */}
          <div
            style={{
              padding: "10px 20px 5px",
              textTransform: "uppercase",
              fontSize: "0.75em",
              color: "#666",
              fontWeight: "bold",
            }}
            className="nav-section-label"
          >
            Server Management
          </div>
          {serverNavItems.map((item) => {
            const isDisabled = !selectedServer;
            return (
              <NavLink
                key={item.path}
                to={isDisabled ? "#" : item.path}
                className={({ isActive }) =>
                  `nav-link ${isActive && !isDisabled ? "active" : ""} ${isDisabled ? "disabled" : ""}`
                }
                onClick={(e) => {
                  if (isDisabled) e.preventDefault();
                }}
                style={{
                  opacity: isDisabled ? 0.5 : 1,
                  cursor: isDisabled ? "not-allowed" : "pointer",
                }}
              >
                {item.icon}
                <span style={{ marginLeft: "10px" }}>{item.label}</span>
              </NavLink>
            );
          })}

        {/* Global Management Section */}
          <hr className="nav-separator" />
          <div
            style={{
              padding: "5px 20px 5px",
              textTransform: "uppercase",
              fontSize: "0.75em",
              color: "#666",
              fontWeight: "bold",
            }}
            className="nav-section-label"
          >
            Global
          </div>
          {globalNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
            >
              {item.icon}
              <span style={{ marginLeft: "10px" }}>{item.label}</span>
            </NavLink>
          ))}

        <hr className="nav-separator" />

          <NavLink
            to="/account"
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
          >
            <User size={20} />
            <span style={{ marginLeft: "10px" }}>Account ({user?.username})</span>
          </NavLink>
          <a
            href="#"
            className="nav-link"
            onClick={(e) => {
              e.preventDefault();
              logout();
            }}
          >
            <LogOut size={20} />
            <span style={{ marginLeft: "10px" }}>Logout</span>
          </a>
    </aside>
  );
};

export default Sidebar;
