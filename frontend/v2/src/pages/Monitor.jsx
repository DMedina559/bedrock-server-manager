import React, { useState, useEffect, useCallback } from "react";
import useWebSocket from "../hooks/useWebSocket";
import { useAuth } from "../AuthContext";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { post, get } from "../api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Play, Square, RotateCcw, Terminal } from "lucide-react";

const Monitor = () => {
  const { isConnected, lastMessage, subscribe, unsubscribe } = useWebSocket();
  const { user } = useAuth();
  const { selectedServer } = useServer();
  const { addToast } = useToast();

  const [processInfo, setProcessInfo] = useState(null);
  const [usageHistory, setUsageHistory] = useState([]);
  const [command, setCommand] = useState("");
  const [loadingAction, setLoadingAction] = useState(false);

  const fetchStatus = useCallback(async () => {
      if (!selectedServer) return;
      try {
          const data = await get(`/api/server/${selectedServer}/process_info`);
          if (data && data.status === "success" && data.data?.process_info) {
              setProcessInfo(data.data.process_info);
          } else {
              setProcessInfo(null);
          }
      } catch (error) {
          console.warn("Failed to fetch initial status", error);
          // Don't clear processInfo on error to avoid flickering, unless 404
          if (error.status === 404) setProcessInfo(null);
      }
  }, [selectedServer]);

  // Subscribe to resource usage updates
  useEffect(() => {
    if (isConnected && selectedServer) {
      const topic = `resource-monitor:${selectedServer}`;
      subscribe(topic);

      fetchStatus();

      return () => {
        unsubscribe(topic);
      };
    }
  }, [isConnected, selectedServer, subscribe, unsubscribe, fetchStatus]);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (lastMessage && selectedServer) {
      const topic = `resource-monitor:${selectedServer}`;
      if (lastMessage.topic === topic && lastMessage.type === "resource_update") {
        const info = lastMessage.data?.process_info;
        if (info) {
          setProcessInfo(info);
          setUsageHistory((prev) => {
            const newPoint = {
              time: new Date().toLocaleTimeString(),
              cpu: info.cpu_percent || 0,
              memory: info.memory_mb || 0,
            };
            // Limit history
            const newData = [...prev, newPoint];
            if (newData.length > 20) newData.shift();
            return newData;
          });
        } else {
            setProcessInfo(null);
        }
      }
    }
  }, [lastMessage, selectedServer]);


  const handleCommand = async (e) => {
    e.preventDefault();
    if (!command.trim()) return;
    if (!selectedServer) return;

    setLoadingAction(true);
    try {
      await post(`/api/server/${selectedServer}/send_command`, { command: command.trim() });
      addToast("Command sent successfully.", "success");
      setCommand("");
    } catch (error) {
      addToast(error.message || "Failed to send command.", "error");
    } finally {
      setLoadingAction(false);
    }
  };

  const sendAction = async (action) => {
    if (loadingAction || !selectedServer) return;

    setLoadingAction(true);
    addToast(`Sending ${action} signal...`, "info");

    try {
      await post(`/api/server/${selectedServer}/${action}`);
      addToast(`Server ${action} signal sent.`, "success");
    } catch (error) {
      addToast(error.message || `Failed to ${action} server.`, "error");
    } finally {
      setLoadingAction(false);
    }
  };

  if (!selectedServer) {
    return (
      <div className="container">
        <div className="message-box message-warning" style={{ textAlign: "center", marginTop: "50px", padding: "20px", border: "1px solid orange", color: "orange" }}>
          Please select a server from the sidebar to view its monitor.
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Server Monitor: {selectedServer}</h1>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
             <span
            className={`status-text ${isConnected ? "status-running" : "status-stopped"}`}
            style={{ fontWeight: "bold", color: isConnected ? "lightgreen" : "red" }}
          >
            {isConnected ? "• Live" : "• Disconnected"}
          </span>
        </div>
      </div>

      <div className="grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(350px, 1fr))", gap: "20px", marginBottom: "20px" }}>

        {/* Status Panel */}
        <div style={{ background: "var(--container-background-color, #444)", padding: "20px", border: "1px solid var(--border-color, #555)" }}>
          <h3>Process Status</h3>
          {processInfo ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", fontSize: "0.9em" }}>
              <div><strong>PID:</strong> {processInfo.pid ?? "N/A"}</div>
              <div><strong>Uptime:</strong> {processInfo.uptime ?? "N/A"}</div>
              <div><strong>CPU:</strong> {processInfo.cpu_percent != null ? processInfo.cpu_percent.toFixed(1) + "%" : "N/A"}</div>
              <div><strong>Memory:</strong> {processInfo.memory_mb != null ? processInfo.memory_mb.toFixed(1) + " MB" : "N/A"}</div>
              <div style={{ gridColumn: "1 / -1", marginTop: "10px" }}>
                  <strong>Status:</strong> <span style={{ color: processInfo.pid ? "lightgreen" : "red", fontWeight: "bold" }}>{processInfo.pid ? "RUNNING" : "STOPPED"}</span>
              </div>
            </div>
          ) : (
            <div style={{ color: "#aaa", fontStyle: "italic" }}>Server process not running or status unavailable.</div>
          )}
        </div>

        {/* Chart Panel */}
        <div style={{ background: "var(--container-background-color, #444)", padding: "20px", border: "1px solid var(--border-color, #555)", minHeight: "250px" }}>
          <h3>Resource Usage</h3>
          <div style={{ height: "200px", width: "100%" }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={usageHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="time" hide />
                <YAxis yAxisId="left" domain={[0, 100]} stroke="#888" width={40} />
                <YAxis yAxisId="right" orientation="right" stroke="#82ca9d" width={40} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#333", border: "1px solid #555" }}
                  labelStyle={{ color: "#ccc" }}
                />
                <Line yAxisId="left" type="monotone" dataKey="cpu" stroke="#8884d8" name="CPU %" dot={false} isAnimationActive={false} />
                <Line yAxisId="right" type="monotone" dataKey="memory" stroke="#82ca9d" name="RAM (MB)" dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="controls-section" style={{ background: "var(--container-background-color, #444)", padding: "20px", border: "1px solid var(--border-color, #555)", marginBottom: "20px" }}>
        <h3>Lifecycle Controls</h3>
        <div className="button-group" style={{ display: "flex", gap: "10px" }}>
          <button className="action-button start-button" onClick={() => sendAction("start")} disabled={loadingAction || (processInfo && processInfo.pid)}>
             <Play size={16} style={{ marginRight: "5px" }} /> Start
          </button>
          <button className="action-button danger-button" onClick={() => sendAction("stop")} disabled={loadingAction || !(processInfo && processInfo.pid)}>
             <Square size={16} style={{ marginRight: "5px" }} /> Stop
          </button>
          <button className="action-button warning-button" onClick={() => sendAction("restart")} disabled={loadingAction || !(processInfo && processInfo.pid)}>
             <RotateCcw size={16} style={{ marginRight: "5px" }} /> Restart
          </button>
        </div>
      </div>

      {/* Command Console */}
      <div className="console-section" style={{ background: "var(--container-background-color, #444)", padding: "20px", border: "1px solid var(--border-color, #555)" }}>
        <h3>Send Command</h3>
        <form onSubmit={handleCommand} style={{ display: "flex", gap: "10px" }}>
            <div style={{ flexGrow: 1, position: "relative" }}>
                <Terminal size={18} style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "#aaa" }} />
                <input
                    type="text"
                    className="form-input"
                    value={command}
                    onChange={(e) => setCommand(e.target.value)}
                    placeholder="Enter command..."
                    style={{ width: "100%", paddingLeft: "35px" }}
                    disabled={loadingAction || !(processInfo && processInfo.pid)}
                />
            </div>
            <button type="submit" className="action-button" disabled={loadingAction || !command || !(processInfo && processInfo.pid)}>Send</button>
        </form>
      </div>

    </div>
  );
};

export default Monitor;
