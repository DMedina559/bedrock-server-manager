import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { get, post } from "../api";
import { Trash2, UserPlus, Shield, RefreshCw, Copy, Check, ToggleLeft, ToggleRight, UserCog } from "lucide-react";
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
  const [editActive, setEditActive] = useState(false);

  const { addToast } = useToast();
  const { user: currentUser } = useAuth();

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

  const handleDelete = async (userToDelete) => {
    if (userToDelete.role === 'admin') {
        const adminCount = users.filter(u => u.role === 'admin' && u.is_active).length;
        if (adminCount <= 1) {
            addToast("Cannot delete the last active administrator account.", "error");
            return;
        }
    }

    if (!confirm(`Are you sure you want to delete user ${userToDelete.username}?`)) return;

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
      const response = await post("/register/generate-token", { role: inviteRole });

      if (response && response.redirect_url) {
          // Extract token from "Registration link generated: http://.../register/<token>"
          const match = response.redirect_url.match(/register\/([a-zA-Z0-9_\-]+)/);
          if (match && match[1]) {
              const token = match[1];
              // Construct V2 link
              const v2Link = `${window.location.origin}/v2/register/${token}`;
              setGeneratedLink(v2Link);
              addToast("Invitation link generated.", "success");
          } else {
               addToast("Link generated but could not be parsed.", "warning");
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
          addToast("You cannot edit your own role/status here. Go to 'Account' page.", "warning");
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
              addToast(`User ${editingUser.username} updated.`, "success");
              setShowEditModal(false);
              setEditingUser(null);
              await fetchUsers();
          } else {
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

  if (loading && users.length === 0) return (
      <div className="container" style={{ textAlign: "center", padding: "20px" }}>Loading users...</div>
  );

  const isAdmin = currentUser?.role === 'admin';

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>User Management</h1>
        <div style={{ display: "flex", gap: "10px" }}>
            <button
            className="action-button secondary"
            onClick={fetchUsers}
            disabled={loading || actionLoading}
            >
            <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
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

      <table className="table" style={{ width: "100%" }}>
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
              <td>{user.username} {currentUser && currentUser.id === user.id && "(You)"}</td>
              <td>
                <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                  <Shield size={14} /> {user.role}
                </span>
              </td>
              <td>
                  {user.is_active ? (
                      <span style={{ color: "var(--success-color, #4CAF50)", display: "flex", alignItems: "center", gap: "5px" }}>
                          <Check size={14} /> Active
                      </span>
                  ) : (
                      <span style={{ color: "var(--error-color, #f44336)", display: "flex", alignItems: "center", gap: "5px" }}>
                           Disabled
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
                        disabled={actionLoading}
                        >
                        <UserCog size={14} />
                        </button>
                        <button
                        className="action-button danger-button"
                        onClick={() => handleDelete(user)}
                        title="Delete User"
                        style={{ padding: "5px 10px" }}
                        disabled={actionLoading}
                        >
                        <Trash2 size={14} />
                        </button>
                        </>
                    )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="modal" style={{ display: "block" }}>
          <div className="modal-content">
            <h2>Invite New User</h2>
            {!generatedLink ? (
                <form onSubmit={handleGenerateLink}>
                <div style={{ marginBottom: "15px", textAlign: "left" }}>
                    <p style={{marginBottom: "10px", color: "#ccc"}}>
                        Generate a registration link to send to a new user. This link will be valid for 24 hours.
                    </p>
                    <label className="form-label">Role</label>
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
                <div className="modal-actions">
                    <button
                    type="button"
                    className="action-button secondary"
                    onClick={closeInviteModal}
                    >
                    Cancel
                    </button>
                    <button type="submit" className="action-button" disabled={actionLoading}>
                    Generate Link
                    </button>
                </div>
                </form>
            ) : (
                <div style={{ textAlign: "left" }}>
                    <p style={{marginBottom: "10px", color: "#4CAF50"}}>Link generated successfully!</p>
                    <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
                        <input
                            type="text"
                            className="form-input"
                            value={generatedLink}
                            readOnly
                            style={{ flexGrow: 1 }}
                        />
                        <button className="action-button" onClick={copyToClipboard} title="Copy to clipboard">
                            {copied ? <Check size={16} /> : <Copy size={16} />}
                        </button>
                    </div>
                    <div className="modal-actions">
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
        <div className="modal" style={{ display: "block" }}>
            <div className="modal-content">
                <h2>Edit User: {editingUser.username}</h2>
                <div style={{ marginBottom: "15px", textAlign: "left" }}>
                    <label className="form-label">Role</label>
                    <select
                        className="form-input"
                        value={editRole}
                        onChange={(e) => setEditRole(e.target.value)}
                        style={{ width: "100%", marginBottom: "15px" }}
                        disabled={editingUser.id === currentUser?.id || actionLoading}
                    >
                        <option value="user">User (Read Only)</option>
                        <option value="moderator">Moderator</option>
                        <option value="admin">Admin</option>
                    </select>

                    <label className="form-label" style={{display: "block", marginBottom: "5px"}}>Status</label>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <button
                            type="button"
                            onClick={() => setEditActive(!editActive)}
                            style={{
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                color: editActive ? "var(--success-color, #4CAF50)" : "var(--error-color, #f44336)",
                                display: "flex",
                                alignItems: "center",
                                gap: "5px",
                                fontSize: "1rem"
                            }}
                            disabled={editingUser.id === currentUser?.id || actionLoading}
                        >
                            {editActive ? <ToggleRight size={32} /> : <ToggleLeft size={32} />}
                            {editActive ? "Active" : "Disabled"}
                        </button>
                    </div>
                </div>
                <div className="modal-actions">
                    <button
                        type="button"
                        className="action-button secondary"
                        onClick={() => { setShowEditModal(false); setEditingUser(null); }}
                        disabled={actionLoading}
                    >
                        Cancel
                    </button>
                    <button type="button" className="action-button" onClick={saveUserChanges} disabled={actionLoading}>
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
      )}
    </div>
  );
};

export default Users;
