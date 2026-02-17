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

  const flattenObject = (obj, prefix = "") => {
    return Object.keys(obj).reduce((acc, k) => {
      const pre = prefix.length ? prefix + "." : "";
      if (
        typeof obj[k] === "object" &&
        obj[k] !== null &&
        !Array.isArray(obj[k])
      ) {
        Object.assign(acc, flattenObject(obj[k], pre + k));
      } else {
        acc[pre + k] = obj[k];
      }
      return acc;
    }, {});
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const flattened = flattenObject(settings);

      // Iterate through keys and save each one individually as the API expects
      // POST /api/settings with body { key: "...", value: ... }
      for (const [key, value] of Object.entries(flattened)) {
        try {
          await post("/api/settings", { key: key, value: value });
        } catch (err) {
          console.error(`Failed to save setting ${key}:`, err);
          throw err; // Re-throw to be caught by outer block
        }
      }

      addToast("Settings saved successfully.", "success");
    } catch (error) {
      console.error("Save settings error:", error);
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
    setSettings((prev) => {
      const newSettings = JSON.parse(JSON.stringify(prev)); // Deep copy
      const keys = path.split(".");
      let current = newSettings;

      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) current[keys[i]] = {};
        current = current[keys[i]];
      }

      current[keys[keys.length - 1]] = value;
      return newSettings;
    });
  };

  const renderField = (key, value, fullPath) => {
    const label = key.replace(/_/g, " ");

    if (typeof value === "boolean") {
      return (
        <div key={fullPath} className="setting-item">
          <label htmlFor={fullPath} className="form-label">
            {label}
          </label>
          <select
            id={fullPath}
            className="form-input"
            value={value.toString()}
            onChange={(e) => handleChange(fullPath, e.target.value === "true")}
          >
            <option value="true">True</option>
            <option value="false">False</option>
          </select>
        </div>
      );
    } else if (Array.isArray(value)) {
      return (
        <div key={fullPath} className="setting-item">
          <label htmlFor={fullPath} className="form-label">
            {label}
          </label>
          <input
            type="text"
            id={fullPath}
            className="form-input"
            value={value.join(", ")}
            onChange={(e) =>
              handleChange(
                fullPath,
                e.target.value.split(",").map((s) => s.trim()),
              )
            }
          />
          <small className="form-text text-muted">Comma-separated values</small>
        </div>
      );
    } else {
      return (
        <div key={fullPath} className="setting-item">
          <label htmlFor={fullPath} className="form-label">
            {label}
          </label>
          <input
            type="text"
            id={fullPath}
            className="form-input"
            value={value || ""}
            onChange={(e) => handleChange(fullPath, e.target.value)}
          />
        </div>
      );
    }
  };

  const renderGroup = (groupName, data, prefix = "") => {
    return (
      <div
        key={prefix ? `${prefix}.${groupName}` : groupName}
        className="settings-group"
      >
        <h3 className="settings-group-title">{groupName.replace(/_/g, " ")}</h3>
        <div className="settings-grid">
          {Object.entries(data).map(([key, value]) => {
            const currentPath = prefix
              ? `${prefix}.${groupName}.${key}`
              : `${groupName}.${key}`;
            // Check if value is nested object (and not array)
            if (
              typeof value === "object" &&
              value !== null &&
              !Array.isArray(value)
            ) {
              return renderGroup(
                key,
                value,
                prefix ? `${prefix}.${groupName}` : groupName,
              );
            }
            return renderField(key, value, currentPath);
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="container">
      <div
        className="header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1>Global Settings</h1>
        <button
          className="action-button secondary"
          onClick={handleReload}
          disabled={loading}
        >
          <RefreshCw
            size={16}
            style={{ marginRight: "5px" }}
            className={loading ? "spin" : ""}
          />{" "}
          Reload
        </button>
      </div>

      {loading && Object.keys(settings).length === 0 ? (
        <div style={{ textAlign: "center", padding: "40px" }}>
          <div className="spinner"></div> Loading settings...
        </div>
      ) : (
        <form onSubmit={handleSave} className="settings-form">
          <div className="settings-container">
            {Object.entries(settings).map(([group, groupData]) => {
              if (
                typeof groupData === "object" &&
                groupData !== null &&
                !Array.isArray(groupData)
              ) {
                return renderGroup(group, groupData);
              }
              return null;
            })}
          </div>

          <div
            className="form-actions"
            style={{
              marginTop: "20px",
              borderTop: "1px solid var(--border-color)",
              paddingTop: "20px",
            }}
          >
            <button type="submit" className="action-button" disabled={loading}>
              <Save size={16} style={{ marginRight: "5px" }} /> Save Changes
            </button>
          </div>
        </form>
      )}

      <style>{`
        .settings-container {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .settings-group {
            background: var(--input-background-color);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }
        .settings-group-title {
            margin-top: 0;
            margin-bottom: 15px;
            text-transform: capitalize;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            font-size: 1.2rem;
            color: var(--text-color);
        }
        .settings-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .setting-item {
            display: flex;
            flex-direction: column;
        }
        .setting-item label {
            margin-bottom: 5px;
            font-weight: 500;
            text-transform: capitalize;
        }
      `}</style>
    </div>
  );
};

export default BSMSettings;
