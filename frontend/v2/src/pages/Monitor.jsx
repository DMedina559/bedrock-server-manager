import React, { useState, useEffect, useRef } from "react";
import useWebSocket from "../hooks/useWebSocket";
import { useAuth } from "../AuthContext";
import { useToast } from "../ToastContext";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const Monitor = () => {
  const { isConnected, lastMessage, subscribe, unsubscribe, sendMessage } =
    useWebSocket();
  const { user } = useAuth();
  const { addToast } = useToast();
  const [logs, setLogs] = useState([]);
  const [serverStatus, setServerStatus] = useState(null);
  const [usageData, setUsageData] = useState([]);
  const [command, setCommand] = useState("");
  const logsEndRef = useRef(null);
  const [loadingAction, setLoadingAction] = useState(false);

  useEffect(() => {
    if (isConnected) {
      subscribe("server_log");
      subscribe("server_status");
      subscribe("server_usage")
    }

    return () => {
      if (isConnected) {
        unsubscribe("server_log");
        unsubscribe("server_status");
        unsubscribe("server_usage");
      }
    };
  }, [isConnected]);

  useEffect(() => {
    if (lastMessage) {
      if (lastMessage.topic === "server_log") {
        setLogs((prev) => [...prev, lastMessage.data]);
      } else if (lastMessage.topic === "server_status") {
        setServerStatus(lastMessage.data);
      } else if (lastMessage.topic === "server_usage") {
        setUsageData((prev) => {
          const newData = [
            ...prev,
            { ...lastMessage.data, time: new Date().toLocaleTimeString() },
          ];
          if (newData.length > 20) newData.shift(); // Keep last 20 points
          return newData;
        });
      }
    }
  }, [lastMessage]);

  // Auto-scroll
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  const handleCommand = (e) => {
    e.preventDefault();
    if (command.trim()) {
      sendMessage({ action: "command", command: command });
      setCommand("");
    }
  };

  const sendAction = async (action) => {
    if (loadingAction) return;
    setLoadingAction(true);
    addToast(`Sending ${action} command...`, "info");

    try {
      const response = await fetch(`/api/server/${action}`, { method: "POST" });
      if (response.ok) {
        addToast(`Server ${action} command sent successfully.`, "success");
      } else {
        const data = await response.json();
        addToast(
          `Failed to ${action} server: ${data.detail || "Unknown error"}`,
          "error",
        );
      }
    } catch (error) {
      addToast(`Error communicating with backend.`, "error");
    } finally {
      setLoadingAction(false);
    }
  };

  return (
    <div
      className="container"
      style={{ padding: "20px", maxWidth: "100%", margin: "0 auto" }}
    >
      <div
        className="header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <h1>Server Monitor</h1>
        <div style={{ display: "flex", gap: "15px", alignItems: "center" }}>
          <span
            style={{
              color: isConnected ? "lightgreen" : "red",
              fontWeight: "bold",
            }}
          >
            {isConnected ? "• Connected" : "• Disconnected"}
          </span>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: "20px",
          marginBottom: "20px",
        }}
      >
        <div
          className="status-panel"
          style={{
            background: "var(--container-background-color, #444)",
            border: "1px solid var(--border-color, #555)",
            padding: "20px",
            borderRadius: "5px",
            color: "#fff",
          }}
        >
          <h3 style={{ marginTop: 0 }}>Server Status</h3>
          {serverStatus ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: "15px",
              }}
            >
              <div>
                <strong>State:</strong> {serverStatus.status || "Unknown"}
              </div>
              <div>
                <strong>Players:</strong> {serverStatus.online_players || 0} /{" "}
                {serverStatus.max_players || "?"}
              </div>
              <div>
                <strong>Version:</strong> {serverStatus.version || "Unknown"}
              </div>
              <div>
                <strong>Level:</strong> {serverStatus.level_name || "Unknown"}
              </div>
            </div>
          ) : (
            <div>Waiting for server status...</div>
          )}
        </div>

        <div
          className="usage-panel"
          style={{
            background: "var(--container-background-color, #444)",
            border: "1px solid var(--border-color, #555)",
            padding: "20px",
            borderRadius: "5px",
            color: "#fff",
            minHeight: "200px",
          }}
        >
          <h3 style={{ marginTop: 0 }}>Resource Usage</h3>
          <div style={{ height: "150px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={usageData}>
                <XAxis dataKey="time" hide />
                <YAxis domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#333",
                    border: "1px solid #555",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="cpu"
                  stroke="#8884d8"
                  name="CPU %"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="ram"
                  stroke="#82ca9d"
                  name="RAM %"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="logs-panel">
        <h3 style={{ color: "#fff" }}>Console Output</h3>
        <div
          className="monitor-output"
          style={{
            height: "500px",
            overflowY: "auto",
            background: "#111",
            color: "#0f0",
            padding: "10px",
            fontFamily: "monospace",
            border: "1px solid #333",
            borderRadius: "4px",
            marginBottom: "20px",
          }}
        >
          {logs.map((log, index) => (
            <div
              key={index}
              style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}
            >
              {typeof log === "string" ? log : JSON.stringify(log)}
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      <div
        className="controls"
        style={{
          marginTop: "20px",
          display: "flex",
          gap: "10px",
          flexWrap: "wrap",
        }}
      >
        <button
          className="button button-success"
          disabled={loadingAction}
          onClick={() => sendAction("start")}
        >
          Start
        </button>
        <button
          className="button button-danger"
          disabled={loadingAction}
          onClick={() => sendAction("stop")}
        >
          Stop
        </button>
        <button
          className="button button-warning"
          disabled={loadingAction}
          onClick={() => sendAction("restart")}
        >
          Restart
        </button>

        <form
          onSubmit={handleCommand}
          style={{ flexGrow: 1, display: "flex", gap: "5px" }}
        >
          <input
            type="text"
            className="form-input"
            placeholder="Enter command..."
            style={{ flexGrow: 1 }}
            value={command}
            onChange={(e) => setCommand(e.target.value)}
          />
          <button type="submit" className="button button-primary">
            Send
          </button>
        </form>
      </div>
    </div>
  );
};

export default Monitor;
