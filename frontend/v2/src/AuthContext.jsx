import React, { createContext, useContext, useState, useEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { request } from "./api";

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);

  const checkUser = async () => {
    // Always check setup status first if not logged in or to ensure correctness
    try {
      const setupRes = await fetch("/setup/status");
      if (setupRes.ok) {
        const setupData = await setupRes.json();
        setNeedsSetup(setupData.needs_setup);
        if (setupData.needs_setup) {
          setLoading(false);
          return; // Stop if setup is needed
        }
      }
    } catch (e) {
      console.warn("Failed to check setup status", e);
    }

    try {
      const userData = await request("/api/account", { method: "GET" });
      setUser(userData);
    } catch (error) {
      console.error("Failed to check user status", error);
      if (error.status === 401) {
        setUser(null);
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkUser();
  }, []);

  const login = async (username, password) => {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch("/auth/token", {
      method: "POST",
      body: formData,
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });

    if (!response.ok) {
      throw new Error("Login failed");
    }

    const data = await response.json();
    if (data.access_token) {
      localStorage.setItem("jwt_token", data.access_token);
    }

    await checkUser();
    return data;
  };

  const logout = async () => {
    try {
      await fetch("/auth/logout");
    } catch (e) {
      console.warn("Logout failed", e);
    }
    localStorage.removeItem("jwt_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, login, logout, loading, checkUser, needsSetup }}
    >
      {children}
    </AuthContext.Provider>
  );
};
