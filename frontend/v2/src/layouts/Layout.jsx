import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import "../styles/layout.css";

const Layout = () => {
  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <div
        className="main-content"
        style={{ flexGrow: 1, minHeight: "100vh", width: "100%" }}
      >
        <Outlet />
      </div>
    </div>
  );
};

export default Layout;
