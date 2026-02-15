import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { get, post } from "../api";
import { Trash2, UserPlus, Shield, RefreshCw } from "lucide-react";

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
    setLoading(true);
    try {
      const data = await get("/users/list");
      if (Array.isArray(data)) {
        setUsers(data);
      } else {
        addToast("Failed to fetch users", "error");
        setUsers([]);
      }
    } catch (error) {
      addToast(error.message || "Error fetching users", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (user) => {
    if (!confirm(`Are you sure you want to delete user ${user.username}?`)) return;

    try {
      await post(`/users/${user.id}/delete`);
      addToast(`User ${user.username} deleted.`, "success");
      fetchUsers();
    } catch (error) {
      addToast(error.message || "Failed to delete user.", "error");
    }
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    try {
      await post("/users/create", newUser);
      addToast("User created successfully.", "success");
      setShowModal(false);
      setNewUser({ username: "", password: "", role: "admin" });
      fetchUsers();
    } catch (error) {
      addToast(error.message || "Failed to create user.", "error");
    }
  };

  if (loading && users.length === 0) return (
      <div className="container" style={{ textAlign: "center", padding: "20px" }}>Loading users...</div>
  );

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>User Management</h1>
        <div style={{ display: "flex", gap: "10px" }}>
            <button
            className="action-button secondary"
            onClick={fetchUsers}
            >
            <RefreshCw size={16} style={{ marginRight: "5px" }} /> Refresh
            </button>
            <button
            className="action-button"
            onClick={() => setShowModal(true)}
            >
            <UserPlus size={16} style={{ marginRight: "5px" }} /> Add User
            </button>
        </div>
      </div>

      <table className="table" style={{ width: "100%" }}>
        <thead>
          <tr>
            <th>Username</th>
            <th>Role</th>
            <th style={{ width: "100px" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.username}</td>
              <td>
                <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                  <Shield size={14} /> {user.role}
                </span>
              </td>
              <td>
                <button
                  className="action-button danger-button"
                  onClick={() => handleDelete(user)}
                  title="Delete User"
                  style={{ padding: "5px 10px" }}
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div className="modal" style={{ display: "block" }}>
          <div className="modal-content">
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
                  className="action-button secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="action-button">
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
