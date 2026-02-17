import React, { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";
import { useTheme } from "../ThemeContext";
import { useToast } from "../ToastContext";
import { get, post } from "../api";
import { Save, User } from "lucide-react";

const Account = () => {
  const { user } = useAuth();
  const { theme, changeTheme } = useTheme();
  const { addToast } = useToast();

  const [passwords, setPasswords] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });

  const [availableThemes, setAvailableThemes] = useState([]);

  useEffect(() => {
    const fetchThemes = async () => {
      try {
        const response = await get("/api/info/themes");
        if (
          response &&
          response.status === "success" &&
          Array.isArray(response.themes)
        ) {
          setAvailableThemes(response.themes);
        } else {
          // Fallback if API fails or returns unexpected format
          setAvailableThemes(["default"]);
        }
      } catch (error) {
        console.warn("Failed to fetch themes", error);
        setAvailableThemes(["default"]);
      }
    };
    fetchThemes();
  }, []);

  const handleThemeChange = (newTheme) => {
    changeTheme(newTheme);
    try {
      post("/api/account/theme", { theme: newTheme });
    } catch {
      console.error("Failed to save theme preference");
    }
    addToast(`Theme changed to ${newTheme}`, "info");
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (passwords.newPassword !== passwords.confirmPassword) {
      addToast("New passwords do not match", "error");
      return;
    }

    try {
      await post("/api/account/change-password", {
        current_password: passwords.currentPassword,
        new_password: passwords.newPassword,
      });

      addToast("Password updated successfully.", "success");
      setPasswords({
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      });
    } catch (error) {
      addToast(error.message || "Failed to update password.", "error");
    }
  };

  return (
    <div className="container" style={{ padding: "20px", maxWidth: "800px" }}>
      <div className="header">
        <h1>My Account</h1>
      </div>

      <div
        className="grid"
        style={{ display: "grid", gap: "20px", gridTemplateColumns: "1fr" }}
      >
        {/* Profile Info */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h2
            style={{
              marginTop: 0,
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <User /> Profile
          </h2>
          <div style={{ marginLeft: "10px" }}>
            <p>
              <strong>Username:</strong> {user?.username}
            </p>
            <p>
              <strong>Role:</strong> {user?.role}
            </p>
          </div>
        </div>

        {/* Theme Selection */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Theme</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
            {availableThemes.length > 0 ? (
              availableThemes.map((t) => (
                <button
                  key={t}
                  className={`action-button ${theme === t ? "" : "secondary"}`}
                  onClick={() => handleThemeChange(t)}
                  style={{ textTransform: "capitalize" }}
                >
                  {t.replace(/_/g, " ")}
                </button>
              ))
            ) : (
              <p>Loading themes...</p>
            )}
          </div>
        </div>

        {/* Password Change */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Change Password</h2>
          <form
            onSubmit={handlePasswordChange}
            className="form-group"
            style={{ maxWidth: "400px" }}
          >
            <div>
              <label className="form-label">Current Password</label>
              <input
                type="password"
                name="current-password"
                className="form-input"
                value={passwords.currentPassword}
                onChange={(e) =>
                  setPasswords({
                    ...passwords,
                    currentPassword: e.target.value,
                  })
                }
                required
                autoComplete="current-password"
                style={{ width: "100%" }}
              />
            </div>
            <div>
              <label className="form-label">New Password</label>
              <input
                type="password"
                name="new-password"
                className="form-input"
                value={passwords.newPassword}
                onChange={(e) =>
                  setPasswords({ ...passwords, newPassword: e.target.value })
                }
                required
                autoComplete="new-password"
                style={{ width: "100%" }}
              />
            </div>
            <div>
              <label className="form-label">Confirm New Password</label>
              <input
                type="password"
                name="confirm-password"
                className="form-input"
                value={passwords.confirmPassword}
                onChange={(e) =>
                  setPasswords({
                    ...passwords,
                    confirmPassword: e.target.value,
                  })
                }
                required
                autoComplete="new-password"
                style={{ width: "100%" }}
              />
            </div>
            <div style={{ marginTop: "15px" }}>
              <button type="submit" className="action-button">
                <Save size={16} style={{ marginRight: "5px" }} /> Update
                Password
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Account;
