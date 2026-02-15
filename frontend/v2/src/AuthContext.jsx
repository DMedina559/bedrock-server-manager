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
        try {
            const userData = await request("/api/account", { method: "GET" });
            setUser(userData);
            setNeedsSetup(false);
        } catch (error) {
            console.error("Failed to check user status", error);

            if (error.status === 401) {
                setUser(null);
            }

            if (!user) {
                try {
                    const probe = await fetch("/api/account", { redirect: 'follow' });
                    if (probe.url && probe.url.includes("/setup")) {
                        setNeedsSetup(true);
                    }
                } catch (e) { /* ignore */ }
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
