import React, { useState, useEffect } from "react";
import { NavLink, Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useServer } from "../ServerContext";
import { get } from "../api";
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
  PlusSquare,
  Gamepad2
} from "lucide-react";

const Sidebar = () => {
  const { logout, user } = useAuth();
  const {
    servers,
    selectedServer,
    setSelectedServer,
    fetchServers,
    loading,
  } = useServer();
  const [pluginPages, setPluginPages] = useState([]);

  useEffect(() => {
    fetchPluginPages();
  }, []);

  const fetchPluginPages = async () => {
    try {
      const response = await get("/api/plugins/pages");
      if (response && response.status === "success") {
        setPluginPages(response.data || []);
      }
    } catch (error) {
      console.warn("Failed to fetch plugin pages", error);
    }
  };

  const handleServerChange = (e) => {
    setSelectedServer(e.target.value);
  };

  const serverNavItems = [
    { path: "/", label: "Monitor", icon: <LayoutDashboard size={20} /> },
    {
      path: "/server-config",
      label: "Settings",
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
    { path: "/global-players", label: "Players", icon: <Gamepad2 size={20} /> },
    { path: "/plugins", label: "Plugins", icon: <Plug size={20} /> },
    { path: "/users", label: "Users", icon: <Users size={20} /> },
    { path: "/bsm-settings", label: "BSM Settings", icon: <Settings size={20} /> },
    { path: "/audit-log", label: "Audit Log", icon: <ScrollText size={20} /> },
  ];

  return (
    <aside className="sidebar-nav">
      <div className="sidebar-header" style={{ padding: "15px 0", textAlign: "center", borderBottom: "1px solid var(--sidebar-border-color)" }}>
        <h2 style={{ margin: 0, fontSize: "1.2em", color: "var(--header-text-color)" }}>BSM V2</h2>
      </div>

      <div style={{ padding: "15px 15px 10px" }}>
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
        <div style={{ display: "flex", gap: "5px", alignItems: "center" }}>
          <select
            id="server-select"
            value={selectedServer || ""}
            onChange={handleServerChange}
            disabled={loading}
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
            onClick={fetchServers}
            title="Refresh Server List"
            className="action-button secondary"
            style={{
              padding: "6px",
              margin: 0,
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div className="nav-group">
          <div className="nav-section-label">Server Management</div>
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
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </NavLink>
            );
          })}
      </div>

      <hr className="nav-separator" />

      <div className="nav-group">
          <div className="nav-section-label">Global</div>
          {globalNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}

          {user?.role === "admin" && (
             <NavLink
                to="/server-install"
                className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
             >
                <span className="nav-icon"><PlusSquare size={20} /></span>
                <span className="nav-label">Install Server</span>
             </NavLink>
          )}
      </div>

      {pluginPages.length > 0 && (
          <>
            <hr className="nav-separator" />
            <div className="nav-group">
                <div className="nav-section-label">From Plugins</div>
                {pluginPages.map((page) => (
                    <a
                        key={page.path}
                        href={page.path}
                        className="nav-link"
                    >
                         <span className="nav-icon"><Plug size={20} /></span>
                         <span className="nav-label">{page.name}</span>
                    </a>
                ))}
            </div>
          </>
      )}

      <hr className="nav-separator" />

      <div className="nav-group footer-nav">
          <NavLink
            to="/account"
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
          >
            <span className="nav-icon"><User size={20} /></span>
            <span className="nav-label">Account ({user?.username})</span>
          </NavLink>
          <button
            className="nav-link logout-button"
            onClick={logout}
            style={{ border: "none", background: "transparent", width: "100%", textAlign: "left", fontSize: "1em", color: "inherit" }}
          >
            <span className="nav-icon"><LogOut size={20} /></span>
            <span className="nav-label">Logout</span>
          </button>
      </div>
    </aside>
  );
};

export default Sidebar;
