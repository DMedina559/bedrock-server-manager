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
      // Flatten settings to get key-value pairs
      const flattened = flattenObject(settings);
      for (const [key, value] of Object.entries(flattened)) {
          await post("/api/settings/update", { key, value });
      }

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

  const handleChange = (path, value) => {
      // Update nested state
      setSettings(prev => {
          const newSettings = { ...prev };
          let current = newSettings;
          const keys = path.split('.');
          const lastKey = keys.pop();

          keys.forEach(key => {
              current[key] = { ...current[key] };
              current = current[key];
          });

          current[lastKey] = value;
          return newSettings;
      });
  };

  // Helper to flatten object for sending to API
  const flattenObject = (obj, prefix = '') => {
    return Object.keys(obj).reduce((acc, k) => {
      const pre = prefix.length ? prefix + '.' : '';
      if (typeof obj[k] === 'object' && obj[k] !== null && !Array.isArray(obj[k])) {
        Object.assign(acc, flattenObject(obj[k], pre + k));
      } else {
        acc[pre + k] = obj[k];
      }
      return acc;
    }, {});
  };

  const renderFields = (obj, prefix = '') => {
      return Object.entries(obj).map(([key, value]) => {
          const fullPath = prefix ? `${prefix}.${key}` : key;

          if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
              return (
                  <div key={fullPath} style={{ marginBottom: "20px", marginLeft: "10px", paddingLeft: "10px", borderLeft: "2px solid var(--border-color)" }}>
                      <h4 style={{ textTransform: "capitalize", margin: "10px 0" }}>{key.replace(/_/g, ' ')}</h4>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "15px" }}>
                        {renderFields(value, fullPath)}
                      </div>
                  </div>
              );
          }

          return (
            <div key={fullPath} style={{ display: "flex", flexDirection: "column" }}>
                <label
                    htmlFor={fullPath}
                    className="form-label"
                    style={{ marginBottom: "5px", fontWeight: "bold", fontSize: "0.9em" }}
                >
                    {key.replace(/_/g, " ")}
                </label>
                {typeof value === "boolean" ? (
                    <select
                        id={fullPath}
                        className="form-input"
                        value={value.toString()}
                        onChange={(e) => handleChange(fullPath, e.target.value === "true")}
                    >
                        <option value="true">True</option>
                        <option value="false">False</option>
                    </select>
                ) : (
                    <input
                        type="text"
                        id={fullPath}
                        className="form-input"
                        value={Array.isArray(value) ? value.join(", ") : value}
                        onChange={(e) => {
                            let val = e.target.value;
                            if (Array.isArray(value)) {
                                val = val.split(",").map(s => s.trim());
                            }
                            handleChange(fullPath, val);
                        }}
                    />
                )}
            </div>
          );
      });
  };


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
            <div style={{ background: "var(--container-background-color)", padding: "20px", border: "1px solid var(--border-color)" }}>
                {/* Recursively render settings */}
                {Object.entries(settings).map(([group, groupData]) => {
                    if (typeof groupData === 'object' && groupData !== null && !Array.isArray(groupData)) {
                        return (
                             <div key={group} style={{ marginBottom: "30px", borderBottom: "1px solid var(--border-color)", paddingBottom: "20px" }}>
                                <h3 style={{ textTransform: "capitalize", margin: "0 0 15px 0" }}>{group} Settings</h3>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "10px" }}>
                                    {renderFields(groupData, group)}
                                </div>
                             </div>
                        )
                    }
                    return null; // Top level primitives usually don't exist in BSM config structure (usually nested under 'web', 'logging', etc.)
                })}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
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
