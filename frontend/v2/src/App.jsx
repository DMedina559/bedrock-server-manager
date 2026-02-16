import React from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuth, AuthProvider } from "./AuthContext";
import { ToastProvider } from "./ToastContext";
import { ServerProvider } from "./ServerContext";
import Layout from "./layouts/Layout";
import Login from "./pages/Login";
import Setup from "./pages/Setup";
import Register from "./pages/Register";
import Monitor from "./pages/Monitor";
import Overview from "./pages/Overview";
import Backups from "./pages/Backups";
import ServerProperties from "./pages/ServerProperties";
import BSMSettings from "./pages/BSMSettings";
import Content from "./pages/Content";
import Users from "./pages/Users";
import AuditLog from "./pages/AuditLog";
import Account from "./pages/Account";
import Plugins from "./pages/Plugins";
import ServerConfig from "./pages/ServerConfig";
import AccessControl from "./pages/AccessControl";
import ServerInstall from "./pages/ServerInstall";
import GlobalPlayers from "./pages/GlobalPlayers";

const PrivateRoute = ({ children }) => {
  const { user, loading, needsSetup } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (needsSetup) {
    return <Navigate to="/setup" replace />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

const AppRoutes = () => {
  const { needsSetup, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={needsSetup ? <Navigate to="/setup" /> : <Login />}
      />
      <Route
        path="/setup"
        element={needsSetup ? <Setup /> : <Navigate to="/" replace />}
      />
      <Route path="/register/:token" element={<Register />} /> {/* Public route with token */}
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Overview />} />
        <Route path="monitor" element={<Monitor />} />
        <Route path="backups" element={<Backups />} />
        <Route path="server-properties" element={<ServerProperties />} />
        <Route path="server-config" element={<ServerConfig />} />
        <Route path="access-control" element={<AccessControl />} />
        <Route path="bsm-settings" element={<BSMSettings />} />
        <Route path="content" element={<Content />} />
        <Route path="plugins" element={<Plugins />} />
        <Route path="users" element={<Users />} />
        <Route path="global-players" element={<GlobalPlayers />} />
        <Route path="audit-log" element={<AuditLog />} />
        <Route path="account" element={<Account />} />
        <Route path="server-install" element={<ServerInstall />} />
      </Route>
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
};

const App = () => {
  return (
    <AuthProvider>
      <ToastProvider>
        <ServerProvider>
          <AppRoutes />
        </ServerProvider>
      </ToastProvider>
    </AuthProvider>
  );
};

export default App;
