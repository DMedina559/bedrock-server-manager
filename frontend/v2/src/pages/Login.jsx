import React, { useState } from "react";
import { useAuth } from "../AuthContext";
import { useNavigate, useLocation } from "react-router-dom";

const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Where to redirect after login
  const from = location.state?.from?.pathname || "/";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError("Invalid username or password");
    }
  };

  return (
    <div
      className="container"
      style={{ maxWidth: "400px", marginTop: "100px" }}
    >
      <div className="header" style={{ flexDirection: "column", gap: "10px" }}>
        <h1>Login</h1>
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
          />
        </div>

        {error && <div className="message message-error">{error}</div>}

        <button type="submit" className="button button-primary">
          Sign In
        </button>
      </form>
    </div>
  );
};

export default Login;
