import React, { useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";
import {
  LayoutDashboard,
  Users,
  Settings,
  Database,
  Server,
  ScrollText,
  LogOut,
  Package,
  Menu,
  User,
  Plug,
  Wrench,
  Shield,
} from "lucide-react";
import "../styles/layout.css";

const Sidebar = () => {
  const { logout, user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  const toggleSidebar = () => {
    setIsOpen(!isOpen);
  };

  const navItems = [
    { path: "/", label: "Dashboard", icon: <LayoutDashboard size={20} /> },
    { path: "/backups", label: "Backups", icon: <Database size={20} /> },
    {
      path: "/server-properties",
      label: "Server Properties",
      icon: <Server size={20} />,
    },
    {
      path: "/server-config",
      label: "Server Config",
      icon: <Wrench size={20} />,
    },
    {
      path: "/access-control",
      label: "Access Control",
      icon: <Shield size={20} />,
    },
    {
      path: "/bsm-settings",
      label: "BSM Settings",
      icon: <Settings size={20} />,
    },
    { path: "/content", label: "Content", icon: <Package size={20} /> },
    { path: "/plugins", label: "Plugins", icon: <Plug size={20} /> },
    { path: "/users", label: "Users", icon: <Users size={20} /> },
    { path: "/audit-log", label: "Audit Log", icon: <ScrollText size={20} /> },
  ];

  return (
    <>
      <button className="menu-toggle" onClick={toggleSidebar}>
        <Menu />
      </button>
      <div className={`sidebar ${isOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <h2>BSM V2</h2>
        </div>
        <div className="nav-links">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
              onClick={() => setIsOpen(false)}
              style={{ display: "flex", alignItems: "center", gap: "10px" }}
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}

          <div
            style={{
              marginTop: "auto",
              borderTop: "1px solid var(--sidebar-border-color)",
            }}
          >
            <NavLink
              to="/account"
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
              onClick={() => setIsOpen(false)}
              style={{ display: "flex", alignItems: "center", gap: "10px" }}
            >
              <User size={20} />
              Account ({user?.username})
            </NavLink>
            <a
              href="#"
              className="nav-link"
              onClick={(e) => {
                e.preventDefault();
                logout();
              }}
              style={{ display: "flex", alignItems: "center", gap: "10px" }}
            >
              <LogOut size={20} />
              Logout
            </a>
          </div>
        </div>
        <div className="sidebar-footer">
          <p>Bedrock Server Manager</p>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
