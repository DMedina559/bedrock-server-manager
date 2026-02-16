import React, { useState, useEffect } from "react";
import { get, post } from "../api";
import { useToast } from "../ToastContext";
import { RefreshCw, Plus, Scan } from "lucide-react";

const GlobalPlayers = () => {
    const [players, setPlayers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [scanLoading, setScanLoading] = useState(false);
    const [addLoading, setAddLoading] = useState(false);

    // Add form state
    const [newPlayerString, setNewPlayerString] = useState(""); // Format: Name:XUID

    const { addToast } = useToast();

    useEffect(() => {
        fetchPlayers();
    }, []);

    const fetchPlayers = async () => {
        setLoading(true);
        try {
            const response = await get("/api/players/get");
            if (response && response.status === "success") {
                setPlayers(response.players || []);
                return true;
            } else {
                addToast(response?.message || "Failed to fetch players.", "error");
                return false;
            }
        } catch (error) {
            console.error("Error fetching players:", error);
            addToast("Error fetching players.", "error");
            return false;
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = async () => {
        const success = await fetchPlayers();
        if (success) {
            addToast("Players list refreshed.", "success");
        }
    };

    const handleScan = async () => {
        setScanLoading(true);
        try {
            const response = await post("/api/players/scan");
            if (response && response.status === "success") {
                addToast(response.message || "Scan started.", "success");
                setTimeout(fetchPlayers, 2000);
            } else {
                addToast(response?.message || "Scan failed.", "error");
            }
        } catch (error) {
            addToast("Error triggering scan.", "error");
        } finally {
            setScanLoading(false);
        }
    };

    const handleAdd = async (e) => {
        e.preventDefault();
        if (!newPlayerString) return;

        // Split by comma if multiple
        const inputs = newPlayerString.split(",").map(s => s.trim()).filter(s => s);
        if (inputs.length === 0) return;

        setAddLoading(true);
        try {
            // payload expects { players: ["Name:XUID", ...] }
            const response = await post("/api/players/add", { players: inputs });
            if (response && response.status === "success") {
                addToast(response.message || "Players added/updated.", "success");
                setNewPlayerString("");
                fetchPlayers();
            } else {
                addToast(response?.message || "Failed to add players.", "error");
            }
        } catch (error) {
            addToast(error.message || "Error adding players.", "error");
        } finally {
            setAddLoading(false);
        }
    };

    return (
        <div className="container">
            <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h1>Global Player Database</h1>
                <div style={{ display: "flex", gap: "10px" }}>
                    <button
                        className="action-button secondary"
                        onClick={handleScan}
                        disabled={scanLoading}
                        title="Scan server logs for players"
                    >
                        <Scan size={16} style={{ marginRight: "5px" }} className={scanLoading ? "spin" : ""} />
                        {scanLoading ? "Scanning..." : "Scan Logs"}
                    </button>
                    <button
                        className="action-button secondary"
                        onClick={handleRefresh}
                        disabled={loading}
                    >
                        <RefreshCw size={16} style={{ marginRight: "5px" }} className={loading ? "spin" : ""} /> Refresh
                    </button>
                </div>
            </div>

            <div style={{ background: "var(--input-background-color)", padding: "20px", borderRadius: "5px", border: "1px solid var(--border-color)" }}>
                <p style={{ marginBottom: "20px", color: "var(--text-color-secondary)" }}>
                    This is the central database of all known players across all servers.
                    Adding players here makes them available for permissions management.
                </p>

                {/* Add Form */}
                <form onSubmit={handleAdd} className="form-group" style={{ display: "flex", gap: "10px", alignItems: "flex-end", marginBottom: "20px", background: "rgba(0,0,0,0.1)", padding: "15px", borderRadius: "5px" }}>
                    <div style={{ flexGrow: 1 }}>
                        <label className="form-label" style={{ display: "block", marginBottom: "5px" }}>Add Players (Format: <code>Gamertag:XUID</code>)</label>
                        <input
                            type="text"
                            className="form-input"
                            value={newPlayerString}
                            onChange={(e) => setNewPlayerString(e.target.value)}
                            placeholder="e.g. Steve:123456789, Alex:987654321"
                            style={{ width: "100%" }}
                        />
                    </div>
                    <button type="submit" className="action-button" disabled={addLoading || !newPlayerString}>
                        <Plus size={16} style={{ marginRight: "5px" }} /> Add / Update
                    </button>
                </form>

                {/* List */}
                {loading ? (
                    <div className="loader-container" style={{ textAlign: "center", padding: "40px" }}>
                        <div className="spinner"></div>
                        <p>Loading players...</p>
                    </div>
                ) : (
                    <div className="table-responsive-wrapper">
                        <table className="server-table" style={{ width: "100%" }}>
                            <thead>
                                <tr>
                                    <th>Gamertag</th>
                                    <th>XUID</th>
                                </tr>
                            </thead>
                            <tbody>
                                {players.length > 0 ? (
                                    players.map((p, idx) => (
                                        <tr key={idx}>
                                            <td style={{ fontWeight: "bold" }}>{p.name}</td>
                                            <td className="mono-text">{p.xuid}</td>
                                        </tr>
                                    ))
                                ) : (
                                    <tr className="no-servers-row">
                                        <td colSpan={2} className="no-servers" style={{ textAlign: "center", padding: "30px", fontStyle: "italic", color: "var(--text-color-secondary)" }}>No players found in database. Scan logs or add manually.</td>
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

export default GlobalPlayers;
