import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Footer from "../components/Footer";

const Layout = () => {
  return (
    <div className="page-layout">
      <Sidebar />
      <main className="main-content">
        <Outlet />
        <Footer />
      </main>
    </div>
  );
};

export default Layout;
