import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { Archive, Trash2, RotateCcw, Plus, Upload } from "lucide-react";

const Backups = () => {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    fetchBackups();
  }, []);

  const fetchBackups = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/backups");
      if (response.ok) {
        const data = await response.json();
        // Sort by date desc
        data.sort((a, b) => new Date(b.date) - new Date(a.date));
        setBackups(data);
      } else {
        addToast("Failed to fetch backups", "error");
      }
    } catch (error) {
      addToast("Error fetching backups", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBackup = async () => {
    addToast("Starting backup...", "info");
    try {
      const response = await fetch("/api/backups", { method: "POST" });
      if (response.ok) {
        addToast("Backup created successfully.", "success");
        fetchBackups();
      } else {
        const data = await response.json();
        addToast(data.detail || "Failed to create backup.", "error");
      }
    } catch (error) {
      addToast("Error creating backup.", "error");
    }
  };

  const handleDelete = async (filename) => {
    if (!confirm(`Are you sure you want to delete backup ${filename}?`)) return;

    try {
      const response = await fetch(`/api/backups/${filename}`, {
        method: "DELETE",
      });
      if (response.ok) {
        addToast("Backup deleted.", "success");
        fetchBackups();
      } else {
        addToast("Failed to delete backup.", "error");
      }
    } catch (error) {
      addToast("Error deleting backup.", "error");
    }
  };

  const handleRestore = async (filename) => {
    if (
      !confirm(
        `WARNING: This will overwrite your current world with backup ${filename}. Are you sure?`,
      )
    )
      return;

    addToast("Restoring backup... Server will stop.", "info");
    try {
      const response = await fetch(`/api/backups/${filename}/restore`, {
        method: "POST",
      });
      if (response.ok) {
        addToast("Restore initiated. Check server logs.", "success");
      } else {
        addToast("Failed to initiate restore.", "error");
      }
    } catch (error) {
      addToast("Error restoring backup.", "error");
    }
  };

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
        <h1>Backups</h1>
        <button
          className="button button-primary"
          onClick={handleCreateBackup}
          style={{ display: "flex", alignItems: "center", gap: "5px" }}
        >
          <Plus size={18} /> Create Backup
        </button>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <table
          className="table"
          style={{
            width: "100%",
            marginTop: "20px",
            borderCollapse: "collapse",
          }}
        >
          <thead>
            <tr
              style={{
                background: "var(--table-header-background-color)",
                textAlign: "left",
              }}
            >
              <th style={{ padding: "10px" }}>Filename</th>
              <th style={{ padding: "10px" }}>Date</th>
              <th style={{ padding: "10px" }}>Size</th>
              <th style={{ padding: "10px" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {backups.map((backup) => (
              <tr
                key={backup.filename}
                style={{ borderBottom: "1px solid var(--table-border-color)" }}
              >
                <td style={{ padding: "10px" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <Archive size={18} /> {backup.filename}
                  </div>
                </td>
                <td style={{ padding: "10px" }}>
                  {new Date(backup.date).toLocaleString()}
                </td>
                <td style={{ padding: "10px" }}>
                  {backup.size_str || backup.size}
                </td>
                <td style={{ padding: "10px", display: "flex", gap: "10px" }}>
                  <button
                    className="button button-warning"
                    onClick={() => handleRestore(backup.filename)}
                    title="Restore"
                    style={{ padding: "5px" }}
                  >
                    <RotateCcw size={16} />
                  </button>
                  <button
                    className="button button-danger"
                    onClick={() => handleDelete(backup.filename)}
                    title="Delete"
                    style={{ padding: "5px" }}
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {backups.length === 0 && (
              <tr>
                <td
                  colSpan="4"
                  style={{
                    textAlign: "center",
                    padding: "20px",
                    color: "#888",
                  }}
                >
                  No backups found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default Backups;
