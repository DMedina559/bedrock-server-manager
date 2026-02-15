import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useToast } from "../ToastContext";

const Register = () => {
  const { token } = useParams();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [tokenValid, setTokenValid] = useState(null);
  const { addToast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    const validateToken = async () => {
        if (!token) return;
        try {
            const response = await fetch(`/register/validate/${token}`);
            if (response.ok) {
                setTokenValid(true);
            } else {
                setTokenValid(false);
            }
        } catch (e) {
            setTokenValid(false);
        }
    };
    validateToken();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password || !confirmPassword) {
      addToast("All fields are required", "error");
      return;
    }

    if (password !== confirmPassword) {
      addToast("Passwords do not match", "error");
      return;
    }

    if (!tokenValid) {
        addToast("Invalid registration link.", "error");
        return;
    }

    setLoading(true);
    try {

      const response = await fetch(`/register/${token}`, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
          },
          body: JSON.stringify({ username, password })
      });

      let data;
      try {
        data = await response.json();
      } catch (e) {
          data = null;
      }

      if (response.ok) {
          addToast("Registration successful! Please login.", "success");
          navigate("/login");
      } else {
          const msg = data?.detail?.message || data?.detail || "Registration failed.";
          addToast(msg, "error");
      }

    } catch (error) {
      addToast("Network error during registration.", "error");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
      return (
          <div className="container" style={{ marginTop: "100px", textAlign: "center" }}>
              <div className="message-box message-error">
                  Invalid registration link. Token is missing.
              </div>
          </div>
      );
  }

  if (tokenValid === false) {
      return (
          <div className="container" style={{ marginTop: "100px", textAlign: "center" }}>
              <div className="message-box message-error">
                  Invalid or expired registration link.
              </div>
          </div>
      );
  }

  if (tokenValid === null) {
      return (
          <div className="container" style={{ marginTop: "100px", textAlign: "center" }}>
              <div className="spinner" style={{display: 'inline-block', marginRight: '10px'}}></div> Checking registration link...
          </div>
      );
  }

  return (
    <div className="container" style={{ maxWidth: "400px", marginTop: "100px" }}>
      <div className="header">
        <h1>Register</h1>
      </div>

      <form onSubmit={handleSubmit} className="form-group">
        <div style={{ marginBottom: "15px" }}>
          <label className="form-label" htmlFor="username">Username</label>
          <input
            type="text"
            id="username"
            className="form-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="username"
          />
        </div>

        <div style={{ marginBottom: "15px" }}>
          <label className="form-label" htmlFor="password">Password</label>
          <input
            type="password"
            id="password"
            className="form-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />
        </div>

        <div style={{ marginBottom: "20px" }}>
          <label className="form-label" htmlFor="confirmPassword">Confirm Password</label>
          <input
            type="password"
            id="confirmPassword"
            className="form-input"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
          />
        </div>

        <button type="submit" className="action-button" disabled={loading} style={{ width: "100%", justifyContent: "center" }}>
          {loading ? "Registering..." : "Register"}
        </button>
      </form>
    </div>
  );
};

export default Register;
