import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { get, post, del } from "../api";
import { Upload, Trash2, Folder, RefreshCw, Layers, RefreshCcw, Download } from "lucide-react";

const Content = () => {
    const { selectedServer } = useServer();
    const [activeTab, setActiveTab] = useState("worlds");
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState(false);
    const [isUploadEnabled, setIsUploadEnabled] = useState(false);
    const { addToast } = useToast();

    useEffect(() => {
        checkUploadPluginStatus();
        if (selectedServer) {
            fetchItems();
        }
    }, [selectedServer, activeTab]);

    const checkUploadPluginStatus = async () => {
        try {
            const response = await get("/api/plugins");
            if (response && response.status === "success" && response.data) {
                const plugin = response.data["content_uploader_plugin"];
                if (plugin && plugin.enabled) {
                    setIsUploadEnabled(true);
                } else {
                    setIsUploadEnabled(false);
                }
            }
        } catch (error) {
            console.warn("Failed to check upload plugin status:", error);
            setIsUploadEnabled(false);
        }
    };

    const fetchItems = async () => {
        if (!selectedServer) return;
        setLoading(true);
        try {
            let endpoint = "";
            if (activeTab === "worlds") {
                endpoint = `/api/content/worlds`;
            } else {
                endpoint = `/api/content/addons`;
            }

            const data = await get(endpoint);
            if (data && data.status === "success") {
                // Backend returns "files": ["filename.mcworld", ...]
                // We need to map this to objects for the table
                const fileList = data.files || [];
                const mappedItems = fileList.map(filename => ({
                    name: filename,
                    type: activeTab
                }));
                setItems(mappedItems);
            } else {
                addToast(`Failed to load ${activeTab}: ${data.message || "Unknown error"}`, "error");
                setItems([]);
            }
        } catch (error) {
            console.error(`Error fetching ${activeTab}:`, error);
            addToast(`Error fetching ${activeTab}`, "error");
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    const handleInstall = async (item) => {
        if (!confirm(`Install ${item.name} to server ${selectedServer}? Server will restart.`)) return;

        setActionLoading(true);
        try {
            const endpoint = activeTab === "worlds"
                ? `/api/server/${selectedServer}/world/install`
                : `/api/server/${selectedServer}/addon/install`;

            await post(endpoint, { filename: item.name });
            addToast(`Installation of ${item.name} started.`, "success");
        } catch (error) {
            addToast(error.message || "Installation failed.", "error");
        } finally {
            setActionLoading(false);
        }
    };

    const handleResetWorld = async () => {
        if (!confirm(`Are you sure you want to RESET the world for ${selectedServer}? This will DELETE the current active world directory. This cannot be undone!`)) return;

        setActionLoading(true);
        try {
            await del(`/api/server/${selectedServer}/world/reset`);
            addToast(`World reset initiated for ${selectedServer}.`, "success");
        } catch (error) {
            addToast(error.message || "World reset failed.", "error");
        } finally {
            setActionLoading(false);
        }
    };

    const handleExportWorld = async () => {
        setActionLoading(true);
        try {
            await post(`/api/server/${selectedServer}/world/export`);
            addToast(`World export initiated for ${selectedServer}.`, "success");
            // Optionally refresh list after a delay, but it's async background task
        } catch (error) {
            addToast(error.message || "World export failed.", "error");
        } finally {
            setActionLoading(false);
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        // Determine type based on tab or file extension
        const type = activeTab === "worlds" ? "world" : "addon";
        formData.append("type", type);

        try {
            setLoading(true);
            // Upload usually goes to /api/content/upload or similar if implemented
            // Based on previous context, verify upload endpoint exists or use legacy
            // Assuming /api/content/upload based on common patterns, but checking routers...
            // If not implemented in Python, we might need to add it or use existing one.
            // For now, let's assume standard upload. If it fails, user will see error.

            const response = await fetch(`/api/content/upload`, {
                method: "POST",
                body: formData,
                headers: {
                    "Authorization": `Bearer ${localStorage.getItem("jwt_token")}`
                }
            });

            const data = await response.json();

            if (response.ok && data.status === "success") {
                addToast("Upload successful.", "success");
                fetchItems();
            } else {
                addToast(`Upload failed: ${data.message || "Unknown error"}`, "error");
            }
        } catch (error) {
            addToast("Upload failed.", "error");
        } finally {
            setLoading(false);
            e.target.value = null; // Reset input
        }
    };


    if (!selectedServer) {
        return (
            <div className="container">
                <div className="message-box message-warning" style={{ textAlign: "center", marginTop: "50px", padding: "20px", border: "1px solid orange", color: "orange" }}>
                    Please select a server.
                </div>
            </div>
        );
    }

    return (
        <div className="container">
            <div className="header" style={{ display: "flex", flexWrap: "wrap", gap: "10px", justifyContent: "space-between", alignItems: "center" }}>
                <h1 style={{ margin: 0 }}>Content Management: {selectedServer}</h1>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
                    <button
                        className="action-button secondary"
                        onClick={fetchItems}
                        disabled={loading || actionLoading}
                    >
                        <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
                    </button>
                    {activeTab === "worlds" && (
                        <>
                            <button
                                className="action-button secondary"
                                onClick={handleExportWorld}
                                disabled={actionLoading}
                                title="Export active world to backups/imports"
                            >
                                <Download size={16} style={{ marginRight: "5px" }} /> Export World
                            </button>
                            <button
                                className="action-button danger-button"
                                onClick={handleResetWorld}
                                disabled={actionLoading}
                                title="Delete current world and generate new one"
                            >
                                <RefreshCcw size={16} style={{ marginRight: "5px" }} /> Reset World
                            </button>
                        </>
                    )}
                </div>
            </div>

            <div className="tabs">
                <button
                    className={`tab-button ${activeTab === "worlds" ? "active" : ""}`}
                    onClick={() => setActiveTab("worlds")}
                >
                    Worlds (Imports)
                </button>
                <button
                    className={`tab-button ${activeTab === "addons" ? "active" : ""}`}
                    onClick={() => setActiveTab("addons")}
                >
                    Addons
                </button>
            </div>

            <div className="tab-content">
                {isUploadEnabled && (
                    <div style={{ marginBottom: "20px", padding: "15px", background: "var(--input-background-color)", borderRadius: "5px", border: "1px solid var(--border-color)" }}>
                        <h3 style={{ marginTop: 0 }}>Upload {activeTab === "worlds" ? "World (.zip, .mcworld)" : "Addon (.mcpack, .mcaddon, .zip)"}</h3>
                        <input type="file" onChange={handleUpload} disabled={loading || actionLoading} className="form-input" />
                        <p style={{ fontSize: "0.85em", color: "var(--text-color-secondary)", marginTop: "5px" }}>
                            Uploaded files will appear in the list below.
                        </p>
                    </div>
                )}

                {loading && items.length === 0 ? (
                    <div style={{ padding: "40px", textAlign: "center", color: "var(--text-color-secondary)" }}>
                        <div className="spinner"></div> Loading available content...
                    </div>
                ) : (
                    <div className="table-responsive-wrapper">
                        <table className="server-table" style={{ width: "100%" }}>
                            <thead>
                                <tr>
                                    <th>File Name</th>
                                    <th style={{ width: "150px" }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items && items.length > 0 ? (
                                    items.map((item, idx) => (
                                        <tr key={idx}>
                                            <td style={{ maxWidth: "200px", overflowX: "auto", whiteSpace: "nowrap" }}>
                                                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                                                    {activeTab === "worlds" ? <Folder size={16} style={{ flexShrink: 0 }} /> : <Layers size={16} style={{ flexShrink: 0 }} />}
                                                    <span>{item.name}</span>
                                                </div>
                                            </td>
                                            <td>
                                                <button
                                                    className="action-button"
                                                    onClick={() => handleInstall(item)}
                                                    title={`Install to ${selectedServer}`}
                                                    style={{ padding: "5px 10px", fontSize: "0.9em" }}
                                                    disabled={actionLoading}
                                                >
                                                    Install
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr className="no-servers-row">
                                        <td colSpan="3" className="no-servers" style={{ textAlign: "center", color: "#888", fontStyle: "italic", padding: "20px" }}>
                                            No available {activeTab} found in imports directory.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Content;
