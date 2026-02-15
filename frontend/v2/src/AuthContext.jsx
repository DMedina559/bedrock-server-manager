import React, { createContext, useContext, useState, useEffect } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [needsSetup, setNeedsSetup] = useState(false);

    const checkUser = async () => {
        try {
            const response = await fetch("/api/account");

            // If the response URL is /setup, we need setup.
            // Note: response.url might be absolute, so we check inclusion.
            if (response.url && response.url.includes("/setup")) {
                setNeedsSetup(true);
                setLoading(false);
                return;
            }

            if (response.ok) {
                const userData = await response.json();
                setUser(userData);
                setNeedsSetup(false);
            } else {
                setUser(null);
                setNeedsSetup(false);
            }
        } catch (error) {
            console.error("Failed to check user status", error);
            // In case of error, assume no user logged in.
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
        await fetch("/auth/logout");
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
