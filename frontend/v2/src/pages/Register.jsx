import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useToast } from "../ToastContext";

const Register = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [searchParams] = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") || "");
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      addToast("Passwords do not match", "error");
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);
      formData.append("token", token);

      const response = await fetch("/api/register", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        addToast("Registration successful! Please login.", "success");
        navigate("/login");
      } else {
        const data = await response.json();
        addToast(data.detail || "Registration failed.", "error");
      }
    } catch (error) {
      addToast("Error during registration.", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: "400px", marginTop: "50px" }}>
      <div className="header" style={{ flexDirection: "column" }}>
        <h1>Register</h1>
        <p>Create a new account</p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="form-group"
        style={{ display: "flex", flexDirection: "column", gap: "15px" }}
      >
        <div>
          <label className="form-label">Registration Token</label>
          <input
            type="text"
            className="form-input"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
            placeholder="Enter invite token"
          />
        </div>
        <div>
          <label className="form-label">Username</label>
          <input
            type="text"
            className="form-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
          />
        </div>
        <div>
          <label className="form-label">Password</label>
          <input
            type="password"
            className="form-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>
        <div>
          <label className="form-label">Confirm Password</label>
          <input
            type="password"
            className="form-input"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>

        <button
          type="submit"
          className="button button-primary"
          disabled={loading}
        >
          {loading ? "Registering..." : "Register"}
        </button>
      </form>

      <div style={{ textAlign: "center", marginTop: "15px" }}>
        <a href="/login" style={{ color: "var(--text-color)" }}>
          Already have an account? Login
        </a>
      </div>
    </div>
  );
};

export default Register;
