import React, { useState } from "react";
import { useServer } from "../ServerContext";
import { useAuth } from "../AuthContext";
import { useToast } from "../ToastContext";
import { useNavigate } from "react-router-dom";
import { post } from "../api";
import { Play, Square, RotateCcw, Users } from "lucide-react";

const Overview = () => {
    const { servers, setSelectedServer, refreshServers } = useServer();
    const { user } = useAuth();
    const { addToast } = useToast();
    const navigate = useNavigate();
    const [actionLoading, setActionLoading] = useState({});
    const [refreshing, setRefreshing] = useState(false);

    const handleServerClick = (serverName) => {
        setSelectedServer(serverName);
        navigate("/monitor");
    };

    const handleRefresh = async () => {
        if (refreshing) return;
        setRefreshing(true);
        addToast("Refreshing server list...", "info");
        try {
            await refreshServers();
            addToast("Server list refreshed.", "success");
        } catch (error) {
            addToast("Failed to refresh server list.", "error");
        } finally {
            setRefreshing(false);
        }
    };

    const handleAction = async (e, serverName, action) => {
        // Prevent click from bubbling up to the card click handler
        e.stopPropagation();

        if (actionLoading[serverName]) return;

        setActionLoading(prev => ({ ...prev, [serverName]: true }));
        addToast(`Sending ${action} signal to ${serverName}...`, "info");

        try {
            await post(`/api/server/${serverName}/${action}`);
            addToast(`Signal ${action} sent to ${serverName}.`, "success");
        } catch (error) {
            addToast(error.message || `Failed to ${action} server.`, "error");
        } finally {
            setActionLoading(prev => ({ ...prev, [serverName]: false }));
        }
    };

    const getStatusColor = (status) => {
        switch (status?.toLowerCase()) {
            case "running": return "#4CAF50";
            case "stopped": return "#D32F2F";
            case "starting":
            case "stopping":
            case "restarting": return "#FFA000";
            default: return "#777";
        }
    };

    return (
        <div className="container">
            <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h1>Server Overview</h1>
                <button className="action-button secondary" onClick={handleRefresh} disabled={refreshing}>
                    {refreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            {servers.length === 0 ? (
                <div className="message-box message-info" style={{ textAlign: "center", padding: "40px" }}>
                    <h3>No servers found.</h3>
                    {user?.role === 'admin' && (
                        <p>Go to "Install Server" in the sidebar to create one.</p>
                    )}
                </div>
            ) : (
                <div className="server-grid" style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                    gap: "20px"
                }}>
                    {servers.map(server => (
                        <div key={server.name}
                            className="server-card"
                            onClick={() => handleServerClick(server.name)}
                            style={{
                                background: "var(--container-background-color)",
                                border: "1px solid var(--border-color)",
                                cursor: "pointer",
                                transition: "transform 0.2s, box-shadow 0.2s",
                                position: "relative",
                                overflow: "hidden"
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.transform = "translateY(-2px)";
                                e.currentTarget.style.boxShadow = "0 4px 8px rgba(0,0,0,0.2)";
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.transform = "none";
                                e.currentTarget.style.boxShadow = "none";
                            }}
                        >
                            <div className="card-header" style={{ padding: "15px", display: "flex", gap: "15px", alignItems: "center", borderBottom: "1px solid var(--border-color)" }}>
                                <img
                                    src={`/api/server/${server.name}/world/icon`}
                                    alt={server.name}
                                    style={{ width: "48px", height: "48px", objectFit: "cover", borderRadius: "4px", background: "#333" }}
                                    onError={(e) => { e.target.src = "/static/image/icon/favicon-96x96.png"; }}
                                />
                                <div style={{ flexGrow: 1, overflow: "hidden" }}>
                                    <h3 style={{ margin: "0 0 5px 0", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{server.name}</h3>
                                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85em" }}>
                                        <span style={{
                                            display: "inline-block",
                                            width: "8px",
                                            height: "8px",
                                            borderRadius: "50%",
                                            backgroundColor: getStatusColor(server.status)
                                        }}></span>
                                        <span style={{ color: getStatusColor(server.status), fontWeight: "bold" }}>
                                            {(server.status || "UNKNOWN").toUpperCase()}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="card-body" style={{ padding: "15px", fontSize: "0.9em", color: "#ccc" }}>
                                <div style={{ marginBottom: "8px", display: "flex", justifyContent: "space-between" }}>
                                    <span>Version:</span>
                                    <span style={{ color: "#fff" }}>{server.version || "N/A"}</span>
                                </div>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                        <Users size={14} /> Players:
                                    </span>
                                    <span style={{ color: "#fff" }}>{server.player_count !== undefined ? server.player_count : "-"}</span>
                                </div>
                            </div>

                            {/* Move click handler to buttons explicitly to ensure stopPropagation works if it was an issue with bubbling order, though stopPropagation is already correct.
                                Also, sometimes a div click handler can interfere if not handled carefully.
                                The main issue reported "navigates to the monitor pages instead of performing the action" implies bubbling.
                                `e.stopPropagation()` was already there, but let's double check if there are other overlays or if the button itself is causing navigation.
                            */}
                            <div className="card-actions"
                                style={{ padding: "10px 15px", background: "rgba(0,0,0,0.2)", display: "flex", justifyContent: "space-around" }}
                                onClick={(e) => e.stopPropagation()} /* Extra safety: stop clicks in the action bar from bubbling to card */
                            >
                                <button
                                    className="action-button start-button"
                                    style={{ padding: "6px 12px", fontSize: "0.8em" }}
                                    onClick={(e) => handleAction(e, server.name, "start")}
                                    disabled={actionLoading[server.name] || server.status === "running"}
                                    title="Start Server"
                                >
                                    <Play size={14} />
                                </button>
                                <button
                                    className="action-button danger-button"
                                    style={{ padding: "6px 12px", fontSize: "0.8em" }}
                                    onClick={(e) => handleAction(e, server.name, "stop")}
                                    disabled={actionLoading[server.name] || server.status === "stopped"}
                                    title="Stop Server"
                                >
                                    <Square size={14} />
                                </button>
                                <button
                                    className="action-button warning-button"
                                    style={{ padding: "6px 12px", fontSize: "0.8em" }}
                                    onClick={(e) => handleAction(e, server.name, "restart")}
                                    disabled={actionLoading[server.name] || server.status === "stopped"}
                                    title="Restart Server"
                                >
                                    <RotateCcw size={14} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default Overview;
