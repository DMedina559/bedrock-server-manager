import React, { useState, useEffect, useRef } from "react";
import { useToast } from "../ToastContext";
import { get } from "../api";
import useWebSocket from "../hooks/useWebSocket";
import { RefreshCw, Terminal, List, Activity, User, FileText } from "lucide-react";

const AuditLog = () => {
    const [activeTab, setActiveTab] = useState("users");
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);

    // App Log State
    const [appLogLines, setAppLogLines] = useState([]);
    const appLogEndRef = useRef(null);

    // Tasks State
    const [tasks, setTasks] = useState([]);

    const { addToast } = useToast();
    const { isConnected, lastMessage, subscribe, unsubscribe } = useWebSocket();

    // App Log Subscription
    useEffect(() => {
        if (activeTab === "app_log" && isConnected) {
            subscribe("app_log");
            return () => unsubscribe("app_log");
        }
    }, [activeTab, isConnected, subscribe, unsubscribe]);

    // Handle WS Messages
    useEffect(() => {
        if (!lastMessage) return;

        if (lastMessage.topic === "app_log" && lastMessage.type === "log_update") {
            if (lastMessage.data) {
                setAppLogLines(prev => {
                    const newLines = lastMessage.data.split('\n');
                    if (newLines.length > 0 && newLines[newLines.length - 1] === "") {
                        newLines.pop();
                    }
                    return [...prev, ...newLines].slice(-1000);
                });
            }
        }
    }, [lastMessage]);

    // Auto-scroll App Log
    useEffect(() => {
        if (appLogEndRef.current && activeTab === "app_log") {
            const container = appLogEndRef.current.parentElement;
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }
    }, [appLogLines, activeTab]);


    const fetchLogs = async () => {
        setLoading(true);
        try {
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

    const fetchTasks = async () => {
        setLoading(true);
        try {
            const data = await get("/api/tasks/list");
            if (Array.isArray(data)) {
                setTasks(data);
                return true;
            } else {
                setTasks([]);
                return false;
            }
        } catch (error) {
            addToast("Error fetching tasks", "error");
            setTasks([]);
            return false;
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === "users") {
            fetchLogs();
        } else if (activeTab === "tasks") {
            fetchTasks();
        }
    }, [activeTab]);

    const handleRefresh = async () => {
        let success = false;
        if (activeTab === "users") {
            success = await fetchLogs();
            if (success) addToast("Audit logs refreshed", "success");
        } else if (activeTab === "tasks") {
            success = await fetchTasks();
            if (success) addToast("Tasks list refreshed", "success");
        } else if (activeTab === "app_log") {
            setAppLogLines([]); // Clear logs on refresh? Or maybe just re-subscribe?
            addToast("App log cleared", "info");
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
            <div className="header" style={{ display: "flex", flexWrap: "wrap", gap: "10px", justifyContent: "space-between", alignItems: "center" }}>
                <h1 style={{ margin: 0 }}>System Logs & Tasks</h1>
                <button className="action-button secondary" onClick={handleRefresh} disabled={loading && activeTab !== "app_log"}>
                    <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} />
                    {activeTab === "app_log" ? "Clear" : "Refresh"}
                </button>
            </div>

            <div className="tabs">
                <button className={`tab-button ${activeTab === "users" ? "active" : ""}`} onClick={() => setActiveTab("users")}>
                    <User size={16} style={{ marginRight: "5px" }} /> User Actions
                </button>
                <button className={`tab-button ${activeTab === "app_log" ? "active" : ""}`} onClick={() => setActiveTab("app_log")}>
                    <FileText size={16} style={{ marginRight: "5px" }} /> App Log
                </button>
                <button className={`tab-button ${activeTab === "tasks" ? "active" : ""}`} onClick={() => setActiveTab("tasks")}>
                    <Activity size={16} style={{ marginRight: "5px" }} /> Background Tasks
                </button>
            </div>

            <div className="tab-content">
                {activeTab === "users" && (
                    <>
                        {loading && logs.length === 0 ? (
                            <div className="container" style={{ textAlign: "center", padding: "20px" }}>Loading logs...</div>
                        ) : (
                            <div className="table-responsive-wrapper">
                                <table className="server-table" style={{ width: "100%" }}>
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
                                                <td>
                                                    <div className="scrollable-field">
                                                        {formatDate(log.timestamp)}
                                                    </div>
                                                </td>
                                                <td>
                                                    <div className="scrollable-field">
                                                        {log.user_id}
                                                    </div>
                                                </td>
                                                <td>
                                                    <div className="scrollable-field">
                                                        <span className="badge badge-user">{log.action}</span>
                                                    </div>
                                                </td>
                                                <td>
                                                    <pre style={{ margin: 0, whiteSpace: "pre-wrap", maxHeight: "100px", overflowY: "auto", background: "rgba(0,0,0,0.1)", padding: "5px", borderRadius: "4px", fontSize: "0.85em" }}>
                                                        {JSON.stringify(log.details, null, 2)}
                                                    </pre>
                                                </td>
                                            </tr>
                                        ))}
                                        {logs.length === 0 && (
                                            <tr><td colSpan="4" style={{ textAlign: "center", padding: "20px", color: "var(--text-color-secondary)" }}>No user audit logs found.</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </>
                )}

                {activeTab === "app_log" && (
                    <div style={{
                        background: "#1e1e1e",
                        color: "#d4d4d4",
                        padding: "15px",
                        fontFamily: "monospace",
                        fontSize: "0.9em",
                        overflowY: "auto",
                        height: "calc(100vh - 250px)",
                        minHeight: "400px",
                        borderRadius: "5px",
                        border: "1px solid var(--border-color)",
                        whiteSpace: "pre-wrap"
                    }}>
                        {appLogLines.length === 0 ? (
                            <div style={{ color: "#666", fontStyle: "italic" }}>Waiting for application logs...</div>
                        ) : (
                            appLogLines.map((line, idx) => (
                                <div key={idx} style={{ minHeight: "1.2em" }}>{line}</div>
                            ))
                        )}
                        <div ref={appLogEndRef} />
                    </div>
                )}

                {activeTab === "tasks" && (
                    <>
                        {loading && tasks.length === 0 ? (
                            <div className="container" style={{ textAlign: "center", padding: "20px" }}>Loading tasks...</div>
                        ) : (
                            <div className="table-responsive-wrapper">
                                <table className="server-table" style={{ width: "100%" }}>
                                    <thead>
                                        <tr>
                                            <th>Task ID</th>
                                            <th>Status</th>
                                            <th>User</th>
                                            <th>Message</th>
                                            <th>Result</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {tasks.map((task) => (
                                            <tr key={task.id}>
                                                <td style={{ fontSize: "0.85em", fontFamily: "monospace" }}>
                                                    <div className="scrollable-field">
                                                        {task.id}
                                                    </div>
                                                </td>
                                                <td>
                                                    <div className="scrollable-field">
                                                        <span className={`status-indicator ${task.status === "success" ? "status-running" : task.status === "error" ? "status-stopped" : "status-starting"}`}>
                                                            {task.status.toUpperCase()}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td>
                                                    <div className="scrollable-field">
                                                        {task.username || "-"}
                                                    </div>
                                                </td>
                                                <td>
                                                    <div className="scrollable-field">
                                                        {task.message}
                                                    </div>
                                                </td>
                                                <td>
                                                    {task.result ? (
                                                        <pre style={{ margin: 0, maxHeight: "50px", overflowY: "auto", fontSize: "0.85em" }}>{JSON.stringify(task.result)}</pre>
                                                    ) : "-"}
                                                </td>
                                            </tr>
                                        ))}
                                        {tasks.length === 0 && (
                                            <tr><td colSpan="5" style={{ textAlign: "center", padding: "20px", color: "var(--text-color-secondary)" }}>No background tasks found.</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default AuditLog;
