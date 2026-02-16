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
  Gamepad2,
  List,
  ChevronLeft,
  ChevronRight,
  Palette,
  X
} from "lucide-react";
import "../styles/SidebarEnhanced.css"; // Import enhanced styles

const Sidebar = ({ mobileOpen, setMobileOpen }) => {
  const { logout, user } = useAuth();
  const {
    servers,
    selectedServer,
    setSelectedServer,
    fetchServers,
    loading,
  } = useServer();
  const [pluginPages, setPluginPages] = useState([]);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Customization State
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [sidebarColor, setSidebarColor] = useState(
      localStorage.getItem("sidebarColor") || "#3a3a3a"
  );
  const [sidebarOpacity, setSidebarOpacity] = useState(
      localStorage.getItem("sidebarOpacity") || "1"
  );

  useEffect(() => {
    fetchPluginPages();
    const storedCollapsed = localStorage.getItem("sidebarCollapsed");
    if (storedCollapsed === "true") {
      setIsCollapsed(true);
    }
  }, []);

  // Update CSS variable when color changes
  useEffect(() => {
      const r = parseInt(sidebarColor.slice(1, 3), 16);
      const g = parseInt(sidebarColor.slice(3, 5), 16);
      const b = parseInt(sidebarColor.slice(5, 7), 16);
      const rgba = `rgba(${r}, ${g}, ${b}, ${sidebarOpacity})`;
      document.documentElement.style.setProperty('--sidebar-bg-custom', rgba);
  }, [sidebarColor, sidebarOpacity]);

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

  const toggleSidebar = () => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    localStorage.setItem("sidebarCollapsed", newState);
  };

  const saveColorSettings = (color, opacity) => {
      setSidebarColor(color);
      setSidebarOpacity(opacity);
      localStorage.setItem("sidebarColor", color);
      localStorage.setItem("sidebarOpacity", opacity);
  };

  const serverNavItems = [
    { path: "/monitor", label: "Monitor", icon: <LayoutDashboard size={20} /> },
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
    <aside
      className={`sidebar-nav ${isCollapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}
      style={{
        // Width removed (handled by CSS)
        // transition: "width 0.2s ease-out", // Handled by CSS
        overflowX: "hidden",
        backgroundColor: "var(--sidebar-bg-custom)" // Apply custom color
      }}
    >
      {/* Close Button for Mobile */}
      <button className="sidebar-close-btn" onClick={() => setMobileOpen && setMobileOpen(false)}>
          <X size={24} />
      </button>

      <div className="sidebar-header" style={{
          padding: "15px 0",
          textAlign: "center",
          borderBottom: "1px solid var(--sidebar-border-color)",
          display: "flex",
          justifyContent: isCollapsed ? "center" : "space-between",
          alignItems: "center",
          paddingLeft: isCollapsed ? "0" : "15px",
          paddingRight: isCollapsed ? "0" : "15px",
          height: "60px"
      }}>
        {!isCollapsed && (
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                 <img src="/static/image/icon/favicon-96x96.png" alt="Icon" style={{ width: "96px", height: "96px" }} />
            </div>
        )}
        {isCollapsed && (
             <img src="/static/image/icon/favicon-96x96.png" alt="Icon" style={{ width: "30px", height: "30px" }} />
        )}
        <button onClick={toggleSidebar} style={{ background: "transparent", border: "none", color: "#ccc", cursor: "pointer", padding: "5px" }}>
            {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <div style={{ padding: isCollapsed ? "10px 5px" : "15px 15px 10px", display: "flex", flexDirection: "column", gap: "10px" }}>
        {!isCollapsed ? (
            <>
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
            </>
        ) : (
             <div style={{ textAlign: "center" }} title={selectedServer || "No Server Selected"}>
                 <div style={{
                     width: "32px", height: "32px", background: "rgba(0,0,0,0.3)", borderRadius: "4px", margin: "0 auto",
                     display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--border-color)",
                     fontSize: "0.9em", fontWeight: "bold", color: "#fff"
                 }}>
                     {selectedServer ? selectedServer.substring(0, 2).toUpperCase() : "-"}
                 </div>
             </div>
        )}
      </div>

      <div className="nav-group">
           <NavLink
                to="/"
                className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                title={isCollapsed ? "Overview" : ""}
           >
              <span className="nav-icon"><List size={20} /></span>
              {!isCollapsed && <span className="nav-label">Overview</span>}
           </NavLink>
      </div>

      <hr className="nav-separator" />

      <div className="nav-group">
          {!isCollapsed && <div className="nav-section-label">Server Management</div>}
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
                title={isCollapsed ? item.label : ""}
              >
                <span className="nav-icon">{item.icon}</span>
                {!isCollapsed && <span className="nav-label">{item.label}</span>}
              </NavLink>
            );
          })}
      </div>

      <hr className="nav-separator" />

      <div className="nav-group">
          {!isCollapsed && <div className="nav-section-label">Global</div>}
          {globalNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
              title={isCollapsed ? item.label : ""}
            >
              <span className="nav-icon">{item.icon}</span>
              {!isCollapsed && <span className="nav-label">{item.label}</span>}
            </NavLink>
          ))}

          {user?.role === "admin" && (
             <NavLink
                to="/server-install"
                className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                title={isCollapsed ? "Install Server" : ""}
             >
                <span className="nav-icon"><PlusSquare size={20} /></span>
                {!isCollapsed && <span className="nav-label">Install Server</span>}
             </NavLink>
          )}
      </div>

      {pluginPages.length > 0 && (
          <>
            <hr className="nav-separator" />
            <div className="nav-group">
                {!isCollapsed && <div className="nav-section-label">From Plugins</div>}
                {pluginPages.map((page) => (
                    <NavLink
                        key={page.path}
                        to={`/plugin-view?url=${encodeURIComponent(page.path)}`}
                        className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                        title={isCollapsed ? page.name : ""}
                    >
                         <span className="nav-icon"><Plug size={20} /></span>
                         {!isCollapsed && <span className="nav-label">{page.name}</span>}
                    </NavLink>
                ))}
            </div>
          </>
      )}

      <hr className="nav-separator" />

      {/* Settings Toggle */}
      <div className="nav-group">
          <button
            className="nav-link"
            onClick={() => setShowColorPicker(!showColorPicker)}
            style={{background: "transparent", border: "none", width: "100%", textAlign: "left", cursor: "pointer", color: "inherit"}}
            title={isCollapsed ? "Customize Sidebar" : ""}
          >
              <span className="nav-icon"><Palette size={20} /></span>
              {!isCollapsed && <span className="nav-label">Customize Appearance</span>}
          </button>

          {showColorPicker && !isCollapsed && (
              <div style={{padding: "10px 15px", background: "rgba(0,0,0,0.2)", margin: "0 10px 10px", borderRadius: "4px"}}>
                  <div style={{marginBottom: "5px"}}>
                      <label style={{fontSize: "0.8em", display: "block"}}>Background Color</label>
                      <input
                        type="color"
                        value={sidebarColor}
                        onChange={(e) => saveColorSettings(e.target.value, sidebarOpacity)}
                        style={{width: "100%", height: "30px", border: "none", cursor: "pointer"}}
                      />
                  </div>
                  <div>
                      <label style={{fontSize: "0.8em", display: "block"}}>Opacity ({Math.round(sidebarOpacity * 100)}%)</label>
                      <input
                        type="range"
                        min="0.5"
                        max="1"
                        step="0.05"
                        value={sidebarOpacity}
                        onChange={(e) => saveColorSettings(sidebarColor, e.target.value)}
                        style={{width: "100%"}}
                      />
                  </div>
              </div>
          )}
      </div>

      <div className="nav-group footer-nav">
          <NavLink
            to="/account"
            className={({ isActive }) =>
              `nav-link ${isActive ? "active" : ""}`
            }
            title={isCollapsed ? `Account (${user?.username})` : ""}
          >
            <span className="nav-icon"><User size={20} /></span>
            {!isCollapsed && <span className="nav-label">Account ({user?.username})</span>}
          </NavLink>
          <button
            className="nav-link logout-button"
            onClick={logout}
            style={{
                border: "none",
                background: "transparent",
                width: "100%",
                textAlign: isCollapsed ? "center" : "left",
                fontSize: "1em",
                color: "inherit",
                display: "flex",
                justifyContent: isCollapsed ? "center" : "flex-start",
                padding: "10px 20px"
            }}
            title={isCollapsed ? "Logout" : ""}
          >
            <span className="nav-icon"><LogOut size={20} /></span>
            {!isCollapsed && <span className="nav-label">Logout</span>}
          </button>
      </div>
    </aside>
  );
};

export default Sidebar;
