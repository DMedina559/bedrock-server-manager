import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const Setup = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("username", username);
      formData.append("password", password);

      const response = await fetch("/setup", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        // Setup successful, redirect to login
        navigate("/login");
      } else {
        setError("Setup failed. Please try again.");
      }
    } catch (err) {
      setError("An error occurred during setup.");
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="container" style={{ maxWidth: "500px", marginTop: "50px" }}>
      <div className="header" style={{ flexDirection: "column", gap: "10px" }}>
        <h1>Setup Bedrock Server Manager</h1>
        <p>Create your administrator account to get started.</p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="form-group"
        style={{ display: "flex", flexDirection: "column", gap: "15px" }}
      >
        <div>
          <label htmlFor="username" className="form-label">
            Username
          </label>
          <input
            type="text"
            id="username"
            className="form-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
          />
        </div>
        <div>
          <label htmlFor="password" className="form-label">
            Password
          </label>
          <input
            type="password"
            id="password"
            className="form-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>
        <div>
          <label htmlFor="confirmPassword" className="form-label">
            Confirm Password
          </label>
          <input
            type="password"
            id="confirmPassword"
            className="form-input"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>

        {error && <div className="message message-error">{error}</div>}

        <button type="submit" className="button button-primary">
          Create Account
        </button>
      </form>
    </div>
  );
};

export default Setup;
