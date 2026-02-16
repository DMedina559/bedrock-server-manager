import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { post, get } from "../api";
import { Archive, Trash2, RotateCcw, Plus, RefreshCw, Layers } from "lucide-react";

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
        // Map API keys to local keys
        const apiBackups = data.details.all_backups;
        setBackups({
            world: apiBackups.world_backups || [],
            properties: apiBackups.properties_backups || [],
            allowlist: apiBackups.allowlist_backups || [],
            permissions: apiBackups.permissions_backups || []
        });
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

  const handleRefresh = async () => {
    addToast("Refreshing backups...", "info");
    await fetchBackups();
    addToast("Backups refreshed.", "success");
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

    if (type === "all") {
        backupType = "all";
    } else if (type !== "world") {
      backupType = "config";
      fileToBackup = getBackupFilename(type);
      if (!fileToBackup) {
          addToast("Invalid backup type selected", "error");
          return;
      }
    }

    const confirmMsg = type === "all" ? "Create a FULL backup of world and all config files?" : `Create backup for ${type}?`;
    if (!confirm(confirmMsg)) return;

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

    let confirmMessage = "";
    if (type === "all") {
        confirmMessage = "WARNING: EXTREMELY DESTRUCTIVE ACTION!\n\nThis will OVERWRITE your current world and ALL configuration files with the LATEST available backups.\n\nAny unsaved progress since the last backup will be LOST FOREVER.\n\nThe server will be restarted if the restore is successful.\n\nAre you absolutely sure?";
    } else {
        confirmMessage = `WARNING: This will overwrite your current ${type} with backup '${filename}'.\nThe server may restart. Are you sure?`;
    }

    if (!confirm(confirmMessage)) return;

    addToast("Restoring backup...", "info");
    try {
      const payload = { restore_type: type };
      if (type !== "all") {
          payload.backup_file = filename;
      }

      await post(`/api/server/${selectedServer}/restore/action`, payload);
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
             <button className="action-button secondary" onClick={handleRefresh} title="Refresh List" disabled={loading}>
                 <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
             </button>
        </div>
      </div>

      {/* Global Backup/Restore Actions */}
      <div style={{ marginBottom: "20px", padding: "20px", background: "rgba(0,0,0,0.2)", border: "1px solid var(--border-color)" }}>
          <h3 style={{ marginTop: 0 }}>Global Actions</h3>
          <p style={{ fontSize: "0.9em", color: "#aaa" }}>Perform actions on all server components (World + Configs) simultaneously.</p>
          <div className="button-group" style={{ display: "flex", gap: "15px" }}>
              <button className="action-button" onClick={() => handleCreateBackup("all")}>
                  <Layers size={16} style={{ marginRight: "5px" }} /> Backup All
              </button>
              <button className="action-button danger-button" onClick={() => handleRestore("all", null)}>
                  <RotateCcw size={16} style={{ marginRight: "5px" }} /> Restore All (Latest)
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
