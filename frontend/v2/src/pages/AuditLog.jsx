import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";

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
      const response = await fetch("/api/audit-log");
      if (response.ok) {
        const data = await response.json();
        // Check if data is array or object. Legacy might return list.
        setLogs(data);
      } else {
        addToast("Failed to fetch audit logs", "error");
      }
    } catch (error) {
      addToast("Error fetching audit logs", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ padding: "20px" }}>
      <div className="header">
        <h1>Audit Log</h1>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table
            className="table"
            style={{
              width: "100%",
              marginTop: "20px",
              borderCollapse: "collapse",
              fontSize: "0.9em",
            }}
          >
            <thead>
              <tr
                style={{
                  background: "var(--table-header-background-color)",
                  textAlign: "left",
                }}
              >
                <th style={{ padding: "10px" }}>Timestamp</th>
                <th style={{ padding: "10px" }}>User</th>
                <th style={{ padding: "10px" }}>Action</th>
                <th style={{ padding: "10px" }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, index) => (
                <tr
                  key={index}
                  style={{
                    borderBottom: "1px solid var(--table-border-color)",
                  }}
                >
                  <td style={{ padding: "10px", whiteSpace: "nowrap" }}>
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td style={{ padding: "10px" }}>{log.username}</td>
                  <td style={{ padding: "10px" }}>{log.action}</td>
                  <td style={{ padding: "10px" }}>{log.details}</td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td
                    colSpan="4"
                    style={{
                      textAlign: "center",
                      padding: "20px",
                      color: "#888",
                    }}
                  >
                    No audit logs found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AuditLog;
