import React, { useCallback, useEffect, useState } from "react";
import { useToast } from "../ToastContext";
import { get, post } from "../api";
import {
  Trash2,
  UserPlus,
  Shield,
  RefreshCw,
  Copy,
  Check,
  UserCog,
  Ban,
  Lock,
  Unlock,
} from "lucide-react";
import { useAuth } from "../AuthContext";

const Users = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);

  // Invite state
  const [inviteRole, setInviteRole] = useState("user");
  const [generatedLink, setGeneratedLink] = useState(null);
  const [copied, setCopied] = useState(false);

  // Edit state
  const [editRole, setEditRole] = useState("");
  const [editActive, setEditActive] = useState(true);

  const { addToast } = useToast();
  const { user: currentUser } = useAuth();

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      // Small delay to ensure the spinner is visible for feedback
      await new Promise((resolve) => setTimeout(resolve, 300));
      const data = await get("/users/list");
      if (Array.isArray(data)) {
        setUsers(data);
        return true;
      } else {
        addToast("Failed to fetch users", "error");
        setUsers([]);
        return false;
      }
    } catch (error) {
      console.error("Error fetching users:", error);
      addToast(error.message || "Error fetching users", "error");
      return false;
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleRefresh = async () => {
    const success = await fetchUsers();
    if (success) {
      addToast("Users list refreshed", "success");
    }
  };

  const handleDelete = async (userToDelete) => {
    if (userToDelete.role === "admin") {
      const adminCount = users.filter(
        (u) => u.role === "admin" && u.is_active,
      ).length;
      if (adminCount <= 1) {
        addToast(
          "Cannot delete the last active administrator account.",
          "error",
        );
        return;
      }
    }

    if (
      !confirm(`Are you sure you want to delete user ${userToDelete.username}?`)
    )
      return;

    setActionLoading(true);
    try {
      await post(`/users/${userToDelete.id}/delete`);
      addToast(`User ${userToDelete.username} deleted.`, "success");
      await fetchUsers();
    } catch (error) {
      console.error("Delete failed:", error);
      addToast(error.message || "Failed to delete user.", "error");
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateLink = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const response = await post("/register/generate-token", {
        role: inviteRole,
      });

      if (response && response.redirect_url) {
        const match = response.redirect_url.match(/register\/([a-zA-Z0-9_-]+)/);
        if (match && match[1]) {
          const token = match[1];
          const v2Link = `${window.location.origin}/app/register/${token}`;
          setGeneratedLink(v2Link);
          addToast("Invitation link generated.", "success");
        } else {
          // Fallback if parsing fails but backend returned success
          setGeneratedLink(response.redirect_url);
          addToast("Link generated.", "success");
        }
      } else {
        addToast("Failed to generate link.", "error");
      }
    } catch (error) {
      addToast(error.message || "Failed to generate invitation link.", "error");
    } finally {
      setActionLoading(false);
    }
  };

  const openEditModal = (user) => {
    if (user.id === currentUser?.id) {
      addToast(
        "You cannot edit your own role/status here. Go to 'Account' page.",
        "warning",
      );
      return;
    }
    setEditingUser(user);
    setEditRole(user.role);
    setEditActive(user.is_active);
    setShowEditModal(true);
  };

  const saveUserChanges = async () => {
    if (!editingUser) return;

    setActionLoading(true);
    try {
      let updated = false;

      // Update Role if changed
      if (editRole !== editingUser.role) {
        await post(`/users/${editingUser.id}/role`, { role: editRole });
        updated = true;
      }

      // Update Status if changed
      if (editActive !== editingUser.is_active) {
        const endpoint = editActive ? "enable" : "disable";
        await post(`/users/${editingUser.id}/${endpoint}`);
        updated = true;
      }

      if (updated) {
        addToast(
          `User ${editingUser.username} updated successfully.`,
          "success",
        );
        setShowEditModal(false);
        setEditingUser(null);
        await fetchUsers();
      } else {
        addToast("No changes made.", "info");
        setShowEditModal(false);
      }
    } catch (error) {
      console.error("Update failed:", error);
      addToast(error.message || "Failed to update user.", "error");
    } finally {
      setActionLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (generatedLink) {
      navigator.clipboard.writeText(generatedLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      addToast("Link copied to clipboard", "success");
    }
  };

  const closeInviteModal = () => {
    setShowInviteModal(false);
    setGeneratedLink(null);
    setInviteRole("user");
  };

  const isAdmin = currentUser?.role === "admin";

  return (
    <div className="container">
      <div
        className="header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>User Management</h1>
        <div style={{ display: "flex", gap: "10px" }}>
          <button
            className="action-button secondary"
            onClick={handleRefresh}
            disabled={loading || actionLoading}
          >
            <RefreshCw
              size={16}
              style={{ marginRight: "5px" }}
              className={loading ? "spin" : ""}
            />{" "}
            Refresh
          </button>
          {isAdmin && (
            <button
              className="action-button"
              onClick={() => setShowInviteModal(true)}
              disabled={actionLoading}
            >
              <UserPlus size={16} style={{ marginRight: "5px" }} /> Invite User
            </button>
          )}
        </div>
      </div>

      {loading && users.length === 0 ? (
        <div style={{ textAlign: "center", padding: "40px" }}>
          <div className="spinner"></div> Loading users...
        </div>
      ) : (
        <div className="table-responsive-wrapper">
          <table className="server-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th style={{ width: "150px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} style={{ opacity: user.is_active ? 1 : 0.6 }}>
                  <td>
                    <span style={{ fontWeight: "bold" }}>{user.username}</span>
                    {currentUser && currentUser.id === user.id && (
                      <span
                        style={{
                          marginLeft: "5px",
                          fontSize: "0.8em",
                          color: "var(--primary-color)",
                        }}
                      >
                        (You)
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`badge badge-${user.role}`}>
                      <Shield size={12} style={{ marginRight: "4px" }} />{" "}
                      {user.role}
                    </span>
                  </td>
                  <td>
                    {user.is_active ? (
                      <span
                        className="status-indicator status-running"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                      >
                        <Check size={14} /> Active
                      </span>
                    ) : (
                      <span
                        className="status-indicator status-stopped"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                      >
                        <Ban size={14} /> Disabled
                      </span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: "5px" }}>
                      {isAdmin && (
                        <>
                          <button
                            className="action-button secondary"
                            onClick={() => openEditModal(user)}
                            title="Edit User"
                            style={{ padding: "5px 10px" }}
                            disabled={
                              actionLoading || user.id === currentUser?.id
                            }
                          >
                            <UserCog size={14} />
                          </button>
                          <button
                            className="action-button danger-button"
                            onClick={() => handleDelete(user)}
                            title="Delete User"
                            style={{ padding: "5px 10px" }}
                            disabled={
                              actionLoading || user.id === currentUser?.id
                            }
                          >
                            <Trash2 size={14} />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td
                    colSpan="4"
                    style={{
                      textAlign: "center",
                      padding: "20px",
                      fontStyle: "italic",
                      color: "#888",
                    }}
                  >
                    No users found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "500px" }}>
            <h2>Invite New User</h2>
            {!generatedLink ? (
              <form onSubmit={handleGenerateLink}>
                <div style={{ marginBottom: "20px", textAlign: "left" }}>
                  <p
                    style={{
                      marginBottom: "15px",
                      color: "var(--text-color-secondary)",
                      lineHeight: "1.5",
                    }}
                  >
                    Generate a secure registration link to send to a new user.
                    This link will be valid for 24 hours.
                  </p>
                  <label
                    className="form-label"
                    style={{ display: "block", marginBottom: "5px" }}
                  >
                    Select Role
                  </label>
                  <select
                    className="form-input"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    style={{ width: "100%" }}
                  >
                    <option value="user">User (Read Only)</option>
                    <option value="moderator">Moderator</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div
                  className="modal-actions"
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: "10px",
                  }}
                >
                  <button
                    type="button"
                    className="action-button secondary"
                    onClick={closeInviteModal}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="action-button"
                    disabled={actionLoading}
                  >
                    Generate Link
                  </button>
                </div>
              </form>
            ) : (
              <div style={{ textAlign: "left" }}>
                <p
                  style={{
                    marginBottom: "10px",
                    color: "var(--success-color)",
                    fontWeight: "bold",
                  }}
                >
                  Link generated successfully!
                </p>
                <div
                  style={{ display: "flex", gap: "10px", marginBottom: "20px" }}
                >
                  <input
                    type="text"
                    className="form-input"
                    value={generatedLink}
                    readOnly
                    style={{ flexGrow: 1 }}
                  />
                  <button
                    className="action-button"
                    onClick={copyToClipboard}
                    title="Copy to clipboard"
                  >
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                </div>
                <div
                  className="modal-actions"
                  style={{ display: "flex", justifyContent: "flex-end" }}
                >
                  <button
                    type="button"
                    className="action-button secondary"
                    onClick={closeInviteModal}
                  >
                    Close
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditModal && editingUser && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "400px" }}>
            <h2>Edit User: {editingUser.username}</h2>
            <div style={{ marginBottom: "20px", textAlign: "left" }}>
              <div style={{ marginBottom: "15px" }}>
                <label
                  className="form-label"
                  style={{ display: "block", marginBottom: "5px" }}
                >
                  Role
                </label>
                <select
                  className="form-input"
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                  style={{ width: "100%" }}
                  disabled={editingUser.id === currentUser?.id || actionLoading}
                >
                  <option value="user">User (Read Only)</option>
                  <option value="moderator">Moderator</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div>
                <label
                  className="form-label"
                  style={{ display: "block", marginBottom: "5px" }}
                >
                  Account Status
                </label>
                <button
                  type="button"
                  className={`action-button ${editActive ? "success-button" : "danger-button"}`}
                  onClick={() => setEditActive(!editActive)}
                  style={{ width: "100%", justifyContent: "center" }}
                  disabled={editingUser.id === currentUser?.id || actionLoading}
                >
                  {editActive ? (
                    <>
                      <Unlock size={16} style={{ marginRight: "5px" }} />{" "}
                      Account Active
                    </>
                  ) : (
                    <>
                      <Lock size={16} style={{ marginRight: "5px" }} /> Account
                      Disabled
                    </>
                  )}
                </button>
                <small
                  style={{
                    display: "block",
                    marginTop: "5px",
                    color: "var(--text-color-secondary)",
                  }}
                >
                  {editActive ? "User can log in." : "User cannot log in."}
                </small>
              </div>
            </div>
            <div
              className="modal-actions"
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "10px",
              }}
            >
              <button
                type="button"
                className="action-button secondary"
                onClick={() => {
                  setShowEditModal(false);
                  setEditingUser(null);
                }}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="action-button"
                onClick={saveUserChanges}
                disabled={actionLoading}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }
        .badge-admin { background-color: rgba(255, 193, 7, 0.2); color: #ffc107; border: 1px solid rgba(255, 193, 7, 0.4); }
        .badge-moderator { background-color: rgba(33, 150, 243, 0.2); color: #2196f3; border: 1px solid rgba(33, 150, 243, 0.4); }
        .badge-user { background-color: rgba(158, 158, 158, 0.2); color: #9e9e9e; border: 1px solid rgba(158, 158, 158, 0.4); }

        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .modal-content {
            background: var(--container-background-color);
            padding: 25px;
            border-radius: 8px;
            width: 100%;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            text-align: center;
        }
        .success-button {
            background-color: var(--success-color);
            color: white;
            border: none;
        }
        .success-button:hover {
            background-color: #45a049;
        }
      `}</style>
    </div>
  );
};

export default Users;
