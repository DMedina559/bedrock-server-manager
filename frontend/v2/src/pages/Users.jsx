import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { Trash2, UserPlus, Shield } from "lucide-react";

const Users = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newUser, setNewUser] = useState({
    username: "",
    password: "",
    role: "admin",
  });
  const { addToast } = useToast();

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await fetch("/api/users");
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      } else {
        addToast("Failed to fetch users", "error");
      }
    } catch (error) {
      addToast("Error fetching users", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (username) => {
    if (!confirm(`Are you sure you want to delete user ${username}?`)) return;

    try {
      const response = await fetch(`/api/users/${username}`, {
        method: "DELETE",
      });

      if (response.ok) {
        addToast(`User ${username} deleted.`, "success");
        fetchUsers();
      } else {
        const data = await response.json();
        addToast(data.detail || "Failed to delete user.", "error");
      }
    } catch (error) {
      addToast("Error deleting user.", "error");
    }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    try {
      // Check API expected format. Usually JSON for FastAPI.
      const response = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newUser),
      });

      if (response.ok) {
        addToast("User created successfully.", "success");
        setShowModal(false);
        setNewUser({ username: "", password: "", role: "admin" });
        fetchUsers();
      } else {
        const data = await response.json();
        addToast(data.detail || "Failed to create user.", "error");
      }
    } catch (error) {
      addToast("Error creating user.", "error");
    }
  };

  if (loading) return <div className="container">Loading users...</div>;

  return (
    <div className="container" style={{ padding: "20px" }}>
      <div
        className="header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>User Management</h1>
        <button
          className="button button-primary"
          onClick={() => setShowModal(true)}
          style={{ display: "flex", alignItems: "center", gap: "5px" }}
        >
          <UserPlus size={18} /> Add User
        </button>
      </div>

      <table
        className="table"
        style={{ width: "100%", borderCollapse: "collapse", marginTop: "20px" }}
      >
        <thead>
          <tr
            style={{
              background: "var(--table-header-background-color)",
              textAlign: "left",
            }}
          >
            <th style={{ padding: "10px" }}>Username</th>
            <th style={{ padding: "10px" }}>Role</th>
            <th style={{ padding: "10px" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr
              key={user.username}
              style={{ borderBottom: "1px solid var(--table-border-color)" }}
            >
              <td style={{ padding: "10px" }}>{user.username}</td>
              <td style={{ padding: "10px" }}>
                <span
                  style={{ display: "flex", alignItems: "center", gap: "5px" }}
                >
                  <Shield size={16} /> {user.role}
                </span>
              </td>
              <td style={{ padding: "10px" }}>
                <button
                  className="button button-danger"
                  onClick={() => handleDelete(user.username)}
                  title="Delete User"
                  style={{ padding: "5px 10px" }}
                >
                  <Trash2 size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div className="modal" style={{ display: "block" }}>
          <div className="modal-content">
            <span className="close-button" onClick={() => setShowModal(false)}>
              &times;
            </span>
            <h2>Add New User</h2>
            <form onSubmit={handleAddUser}>
              <div style={{ marginBottom: "15px", textAlign: "left" }}>
                <label className="form-label">Username</label>
                <input
                  type="text"
                  className="form-input"
                  value={newUser.username}
                  onChange={(e) =>
                    setNewUser({ ...newUser, username: e.target.value })
                  }
                  required
                  style={{ width: "100%" }}
                />
              </div>
              <div style={{ marginBottom: "15px", textAlign: "left" }}>
                <label className="form-label">Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={newUser.password}
                  onChange={(e) =>
                    setNewUser({ ...newUser, password: e.target.value })
                  }
                  required
                  style={{ width: "100%" }}
                />
              </div>
              <div style={{ marginBottom: "15px", textAlign: "left" }}>
                <label className="form-label">Role</label>
                <select
                  className="form-input"
                  value={newUser.role}
                  onChange={(e) =>
                    setNewUser({ ...newUser, role: e.target.value })
                  }
                  style={{ width: "100%" }}
                >
                  <option value="admin">Admin</option>
                  <option value="user">User (Read Only)</option>
                </select>
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="button"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="button button-primary">
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Users;
