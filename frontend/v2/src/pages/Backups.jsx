import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { post, get } from "../api";
import { Archive, Trash2, RotateCcw, Plus, RefreshCw } from "lucide-react";

const Backups = () => {
  const { selectedServer } = useServer();
  const [backups, setBackups] = useState({});
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (selectedServer) {
      fetchBackups();
    }
  }, [selectedServer]);

  const fetchBackups = async () => {
    setLoading(true);
    try {
      const data = await get(`/api/server/${selectedServer}/backup/list/all`);
      if (data && data.status === "success" && data.details?.all_backups) {
        setBackups(data.details.all_backups);
      } else {
        addToast("Failed to fetch backups list", "error");
        setBackups({});
      }
    } catch (error) {
      addToast(error.message || "Error fetching backups", "error");
    } finally {
      setLoading(false);
    }
  };

  const getBackupFilename = (type) => {
    switch (type) {
      case "properties": return "server.properties";
      case "allowlist": return "allowlist.json";
      case "permissions": return "permissions.json";
      default: return null;
    }
  };

  const handleCreateBackup = async (type) => {
    if (!selectedServer) return;

    // Map internal type to API expected type/filename
    let backupType = "world";
    let fileToBackup = null;

    if (type !== "world") {
      backupType = "config";
      fileToBackup = getBackupFilename(type);
      if (!fileToBackup) {
          addToast("Invalid backup type selected", "error");
          return;
      }
    }

    addToast(`Starting ${type} backup...`, "info");
    try {
      const payload = { backup_type: backupType };
      if (fileToBackup) payload.file_to_backup = fileToBackup;

      await post(`/api/server/${selectedServer}/backup/action`, payload);
      addToast("Backup task started. Check logs for completion.", "success");
    } catch (error) {
      addToast(error.message || "Failed to start backup.", "error");
    }
  };

  const handleRestore = async (type, filename) => {
    if (!selectedServer) return;
    if (
      !confirm(
        `WARNING: This will overwrite your current ${type} with backup '${filename}'.\nThe server may restart. Are you sure?`,
      )
    )
      return;

    addToast("Restoring backup...", "info");
    try {
      await post(`/api/server/${selectedServer}/restore/action`, {
        restore_type: type,
        backup_file: filename,
      });
      addToast("Restore task started.", "success");
    } catch (error) {
      addToast(error.message || "Failed to start restore.", "error");
    }
  };

  const handlePrune = async () => {
      if (!selectedServer) return;
      if (!confirm("Prune old backups based on retention policy?")) return;

      try {
          await post(`/api/server/${selectedServer}/backups/prune`, {});
          addToast("Pruning task started.", "success");
      } catch (error) {
          addToast(error.message || "Failed to prune backups.", "error");
      }
  };

  if (!selectedServer) {
    return (
      <div className="container">
        <div className="message-box message-warning" style={{ textAlign: "center", marginTop: "50px", padding: "20px", border: "1px solid orange", color: "orange" }}>
          Please select a server to manage backups.
        </div>
      </div>
    );
  }

  // Helper to render a table for a specific backup category
  const renderBackupTable = (title, type, files) => (
    <div style={{ marginBottom: "30px", background: "var(--container-background-color)", padding: "15px", border: "1px solid var(--border-color)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", borderBottom: "1px solid var(--border-color)", paddingBottom: "10px" }}>
        <h3 style={{ margin: 0 }}>{title} Backups</h3>
        <button className="action-button" onClick={() => handleCreateBackup(type)}>
            <Plus size={16} style={{ marginRight: "5px" }} /> New {title} Backup
        </button>
      </div>

      <table className="table" style={{ width: "100%" }}>
        <thead>
          <tr>
            <th>Filename</th>
            <th style={{ width: "100px", textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {files && files.length > 0 ? (
            files.map((file) => (
              <tr key={file}>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Archive size={16} /> {file}
                  </div>
                </td>
                <td style={{ textAlign: "right" }}>
                  <button
                    className="action-button warning-button"
                    onClick={() => handleRestore(type, file)}
                    title="Restore"
                    style={{ padding: "5px 10px", fontSize: "0.8em" }}
                  >
                    <RotateCcw size={14} style={{ marginRight: "5px" }} /> Restore
                  </button>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="2" style={{ textAlign: "center", color: "#888", fontStyle: "italic", padding: "15px" }}>
                No backups found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Backups: {selectedServer}</h1>
        <div style={{ display: "flex", gap: "10px" }}>
             <button className="action-button danger-button" onClick={handlePrune} title="Prune old backups">
                 <Trash2 size={16} style={{ marginRight: "5px" }} /> Prune Old
             </button>
             <button className="action-button secondary" onClick={fetchBackups} title="Refresh List">
                 <RefreshCw size={16} style={{ marginRight: "5px" }} /> Refresh
             </button>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: "20px", textAlign: "center" }}>Loading backups...</div>
      ) : (
        <>
          {renderBackupTable("World", "world", backups.world)}
          {renderBackupTable("Properties", "properties", backups.properties)}
          {renderBackupTable("Allowlist", "allowlist", backups.allowlist)}
          {renderBackupTable("Permissions", "permissions", backups.permissions)}
        </>
      )}
    </div>
  );
};

export default Backups;
