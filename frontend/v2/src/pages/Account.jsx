import React, { useState } from "react";
import { useAuth } from "../AuthContext";
import { useTheme } from "../ThemeContext";
import { useToast } from "../ToastContext";

const Account = () => {
  const { user } = useAuth();
  const { theme, changeTheme } = useTheme();
  const { addToast } = useToast();

  const [passwords, setPasswords] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });

  const themes = [
    "default",
    "light",
    "gradient",
    "black",
    "red",
    "green",
    "blue",
    "yellow",
    "pink",
  ];

  const handleThemeChange = (newTheme) => {
    changeTheme(newTheme);
    addToast(`Theme changed to ${newTheme}`, "info");
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (passwords.newPassword !== passwords.confirmPassword) {
      addToast("New passwords do not match", "error");
      return;
    }

    try {

      const formData = new FormData();
      formData.append("current_password", passwords.currentPassword);
      formData.append("new_password", passwords.newPassword);
      formData.append("confirm_password", passwords.confirmPassword);

      const response = await fetch("/api/account/password", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        addToast("Password updated successfully.", "success");
        setPasswords({
          currentPassword: "",
          newPassword: "",
          confirmPassword: "",
        });
      } else {
        const data = await response.json();
        addToast(data.detail || "Failed to update password.", "error");
      }
    } catch (error) {
      addToast("Error updating password.", "error");
    }
  };

  return (
    <div className="container" style={{ padding: "20px", maxWidth: "800px" }}>
      <div className="header">
        <h1>My Account</h1>
      </div>

      <div
        className="grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "20px",
        }}
      >
        {/* Profile Info */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            borderRadius: "5px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h2>Profile</h2>
          <p>
            <strong>Username:</strong> {user?.username}
          </p>
          <p>
            <strong>Role:</strong> {user?.role}
          </p>
        </div>

        {/* Theme Selection */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            borderRadius: "5px",
            border: "1px solid var(--border-color)",
          }}
        >
          <h2>Theme</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
            {themes.map((t) => (
              <button
                key={t}
                className={`button ${theme === t ? "button-primary" : ""}`}
                onClick={() => handleThemeChange(t)}
                style={{ textTransform: "capitalize" }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Password Change */}
        <div
          style={{
            background: "var(--container-background-color)",
            padding: "20px",
            borderRadius: "5px",
            border: "1px solid var(--border-color)",
            gridColumn: "1 / -1",
          }}
        >
          <h2>Change Password</h2>
          <form
            onSubmit={handlePasswordChange}
            style={{ display: "grid", gap: "15px", maxWidth: "400px" }}
          >
            <div>
              <label className="form-label">Current Password</label>
              <input
                type="password"
                className="form-input"
                value={passwords.currentPassword}
                onChange={(e) =>
                  setPasswords({
                    ...passwords,
                    currentPassword: e.target.value,
                  })
                }
                required
                style={{ width: "100%" }}
              />
            </div>
            <div>
              <label className="form-label">New Password</label>
              <input
                type="password"
                className="form-input"
                value={passwords.newPassword}
                onChange={(e) =>
                  setPasswords({ ...passwords, newPassword: e.target.value })
                }
                required
                style={{ width: "100%" }}
              />
            </div>
            <div>
              <label className="form-label">Confirm New Password</label>
              <input
                type="password"
                className="form-input"
                value={passwords.confirmPassword}
                onChange={(e) =>
                  setPasswords({
                    ...passwords,
                    confirmPassword: e.target.value,
                  })
                }
                required
                style={{ width: "100%" }}
              />
            </div>
            <button type="submit" className="button button-primary">
              Update Password
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Account;
