import React, { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Footer from "../components/Footer";
import { Menu } from "lucide-react";

const Layout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="page-layout">
      {/* Mobile Toggle Button */}
      <button
        className="mobile-menu-toggle"
        onClick={() => setMobileOpen(true)}
        title="Open Menu"
      >
        <Menu size={24} />
      </button>

      {/* Overlay for mobile to close sidebar */}
      {mobileOpen && (
        <div
          className="sidebar-overlay"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.5)",
            zIndex: 950,
          }}
          onClick={() => setMobileOpen(false)}
        />
      )}

      <Sidebar mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} />
      <main className="main-content">
        <Outlet />
        <Footer />
      </main>
    </div>
  );
};

export default Layout;
