import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { get } from "../api";
import { RefreshCw } from "lucide-react";

const AuditLog = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      // Small delay to ensure the spinner is visible
      await new Promise(resolve => setTimeout(resolve, 300));
      const data = await get("/audit-log/list");
      if (Array.isArray(data)) {
        setLogs(data);
        return true;
      } else {
        addToast("Failed to fetch audit logs", "error");
        setLogs([]);
        return false;
      }
    } catch (error) {
      addToast(error.message || "Error fetching audit logs", "error");
      return false;
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
      const success = await fetchLogs();
      if (success) {
          addToast("Audit logs refreshed", "success");
      }
  };

  const formatDate = (dateString) => {
      try {
          return new Date(dateString).toLocaleString();
      } catch (e) {
          return dateString;
      }
  };

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Audit Log</h1>
        <button className="action-button secondary" onClick={handleRefresh} disabled={loading}>
            <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
        </button>
      </div>

      {loading && logs.length === 0 ? (
          <div className="container" style={{ textAlign: "center", padding: "20px" }}>Loading logs...</div>
      ) : (
      <div style={{ overflowX: "auto" }}>
        <table className="table" style={{ width: "100%", fontSize: "0.9em" }}>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>User ID</th>
              <th>Action</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>{formatDate(log.timestamp)}</td>
                <td>{log.user_id}</td>
                <td>{log.action}</td>
                <td>
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap", maxHeight: "100px", overflowY: "auto", background: "rgba(0,0,0,0.2)", padding: "5px", borderRadius: "4px" }}>
                      {JSON.stringify(log.details, null, 2)}
                  </pre>
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
                <tr><td colSpan="4" style={{ textAlign: "center", padding: "20px", color: "#888" }}>No audit logs found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
};

export default AuditLog;
