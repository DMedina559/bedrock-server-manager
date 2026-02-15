import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";

const Layout = () => {
  return (
    <div className="page-layout">
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
