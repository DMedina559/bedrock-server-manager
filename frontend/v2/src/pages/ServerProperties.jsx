import React, { useState, useEffect } from "react";
import { useServer } from "../ServerContext";
import { useToast } from "../ToastContext";
import { get, post } from "../api";
import { Save, RefreshCw } from "lucide-react";

const ServerProperties = () => {
  const { selectedServer } = useServer();
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (selectedServer) {
      fetchProperties();
    }
  }, [selectedServer]);

  const fetchProperties = async () => {
    setLoading(true);
    try {
      const data = await get(`/api/server/${selectedServer}/properties/get`);
      if (data && data.status === "success" && data.properties) {
        // Convert object to array for mapping
        const propsArray = Object.entries(data.properties).map(([key, value]) => ({
          key,
          value: String(value), // Ensure string for inputs
        }));
        propsArray.sort((a, b) => a.key.localeCompare(b.key));
        setProperties(propsArray);
      } else {
        addToast("Failed to load server properties", "error");
        setProperties([]);
      }
    } catch (error) {
      addToast(error.message || "Error fetching properties", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!selectedServer) return;

    setLoading(true);
    const propsObj = properties.reduce((acc, curr) => {
      acc[curr.key] = curr.value;
      return acc;
    }, {});

    try {
      await post(`/api/server/${selectedServer}/properties/set`, {
        properties: propsObj,
      });
      addToast("Server properties saved successfully.", "success");
    } catch (error) {
      addToast(error.message || "Failed to save properties.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key, newValue) => {
    setProperties((prev) =>
      prev.map((p) => (p.key === key ? { ...p, value: newValue } : p))
    );
  };

  const renderInput = (prop) => {
    const key = prop.key;
    const value = prop.value;

    // Boolean fields
    if (["allow-cheats", "online-mode", "white-list", "texturepack-required", "content-log-file-enabled", "force-gamemode", "server-authoritative-movement", "player-movement-score-threshold", "player-movement-distance-threshold", "player-movement-duration-threshold-in-ms", "correct-player-movement", "server-authoritative-block-breaking"].includes(key) || value === "true" || value === "false") {
        return (
            <select
                id={key}
                className="form-input"
                value={value}
                onChange={(e) => handleChange(key, e.target.value)}
            >
                <option value="true">true</option>
                <option value="false">false</option>
            </select>
        );
    }

    // Gamemode
    if (key === "gamemode") {
        return (
            <select
                id={key}
                className="form-input"
                value={value}
                onChange={(e) => handleChange(key, e.target.value)}
            >
                <option value="survival">survival</option>
                <option value="creative">creative</option>
                <option value="adventure">adventure</option>
            </select>
        );
    }

    // Difficulty
    if (key === "difficulty") {
        return (
            <select
                id={key}
                className="form-input"
                value={value}
                onChange={(e) => handleChange(key, e.target.value)}
            >
                <option value="peaceful">peaceful</option>
                <option value="easy">easy</option>
                <option value="normal">normal</option>
                <option value="hard">hard</option>
            </select>
        );
    }

    // Default text input
    return (
        <input
            type="text"
            id={key}
            className="form-input"
            value={value}
            onChange={(e) => handleChange(key, e.target.value)}
        />
    );
  };

  if (!selectedServer) {
    return (
      <div className="container">
        <div className="message-box message-warning" style={{ textAlign: "center", marginTop: "50px", padding: "20px", border: "1px solid orange", color: "orange" }}>
          Please select a server to configure properties.
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Server Properties: {selectedServer}</h1>
        <button className="action-button secondary" onClick={fetchProperties} disabled={loading}>
            <RefreshCw size={16} style={{ marginRight: "5px" }} /> Refresh
        </button>
      </div>

      {loading && properties.length === 0 ? (
        <div style={{ textAlign: "center", padding: "20px" }}>Loading properties...</div>
      ) : (
        <form onSubmit={handleSave} className="form-group">
            <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                gap: "20px",
                background: "var(--container-background-color)",
                padding: "20px",
                border: "1px solid var(--border-color)",
                marginBottom: "20px"
            }}>
            {properties.map((prop) => (
                <div key={prop.key} style={{ display: "flex", flexDirection: "column" }}>
                <label
                    htmlFor={prop.key}
                    className="form-label"
                    style={{ marginBottom: "5px", fontWeight: "bold", fontSize: "0.9em" }}
                >
                    {prop.key.replace(/-/g, " ")}
                </label>
                {renderInput(prop)}
                </div>
            ))}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
                type="submit"
                className="action-button"
                disabled={loading}
            >
                <Save size={16} style={{ marginRight: "5px" }} /> Save Changes
            </button>
            </div>
        </form>
      )}
    </div>
  );
};

export default ServerProperties;
