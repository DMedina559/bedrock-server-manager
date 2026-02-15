import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { get, post } from "../api";
import { Save, RefreshCw } from "lucide-react";

const BSMSettings = () => {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await get("/api/settings");
      if (data && data.settings) {
        setSettings(data.settings);
      } else {
        addToast("Failed to load settings", "error");
      }
    } catch (error) {
      addToast(error.message || "Error fetching settings", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await post("/api/settings", settings);
      addToast("Settings saved successfully.", "success");
    } catch (error) {
      addToast(error.message || "Failed to save settings.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleReload = async () => {
      setLoading(true);
      try {
          await post("/api/settings/reload");
          addToast("Settings reloaded from disk.", "success");
          fetchSettings();
      } catch (error) {
          addToast(error.message || "Failed to reload settings.", "error");
          setLoading(false);
      }
  };

  const handleChange = (key, value) => {
    setSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  // Group settings by prefix
  const groupedSettings = Object.entries(settings).reduce(
    (acc, [key, value]) => {
      const prefix = key.split(".")[0];
      if (!acc[prefix]) acc[prefix] = [];
      acc[prefix].push({ key, value });
      return acc;
    },
    {},
  );

  return (
    <div className="container">
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>BSM Settings</h1>
        <button className="action-button secondary" onClick={handleReload} disabled={loading}>
            <RefreshCw size={16} style={{ marginRight: "5px" }} /> Reload from Disk
        </button>
      </div>

      {loading && Object.keys(settings).length === 0 ? (
        <div style={{ textAlign: "center", padding: "20px" }}>Loading...</div>
      ) : (
        <form onSubmit={handleSave} className="form-group">
            {Object.entries(groupedSettings).map(([group, items]) => (
            <div key={group} style={{ marginBottom: "30px", background: "var(--container-background-color)", padding: "20px", border: "1px solid var(--border-color)" }}>
                <h3 style={{ textTransform: "capitalize", margin: "0 0 15px 0", paddingBottom: "10px", borderBottom: "1px solid var(--border-color)" }}>
                {group} Settings
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "20px" }}>
                {items.map((item) => (
                    <div key={item.key} style={{ display: "flex", flexDirection: "column" }}>
                    <label
                        htmlFor={item.key}
                        className="form-label"
                        style={{ marginBottom: "5px", fontWeight: "bold", fontSize: "0.9em" }}
                    >
                        {item.key}
                    </label>
                    {typeof item.value === "boolean" ? (
                        <select
                        id={item.key}
                        className="form-input"
                        value={item.value.toString()}
                        onChange={(e) =>
                            handleChange(item.key, e.target.value === "true")
                        }
                        >
                        <option value="true">True</option>
                        <option value="false">False</option>
                        </select>
                    ) : (
                        <input
                        type="text"
                        id={item.key}
                        className="form-input"
                        value={item.value}
                        onChange={(e) => handleChange(item.key, e.target.value)}
                        />
                    )}
                    </div>
                ))}
                </div>
            </div>
            ))}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button type="submit" className="action-button" disabled={loading}>
                <Save size={16} style={{ marginRight: "5px" }} /> Save Settings
            </button>
            </div>
        </form>
      )}
    </div>
  );
};

export default BSMSettings;
