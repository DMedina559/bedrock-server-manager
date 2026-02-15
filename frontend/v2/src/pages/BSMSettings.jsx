import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";
import { useTheme } from "../ThemeContext";

const BSMSettings = () => {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();
  const { changeTheme } = useTheme();

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await fetch("/api/settings");
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      } else {
        addToast("Failed to load settings", "error");
      }
    } catch (error) {
      addToast("Error fetching settings", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(settings),
      });

      if (response.ok) {
        addToast("Settings saved successfully.", "success");
      } else {
        addToast("Failed to save settings.", "error");
      }
    } catch (error) {
      addToast("Error saving settings.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key, value) => {
    // Handle nested keys if necessary, but API likely returns flat or we flatten it.
    // The API returns a dict.
    setSettings((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  // Helper to categorize settings if possible, otherwise render list
  // Legacy UI groups them by prefixes like 'web.', 'backup.', etc.
  const groupedSettings = Object.entries(settings).reduce(
    (acc, [key, value]) => {
      const prefix = key.split(".")[0];
      if (!acc[prefix]) acc[prefix] = [];
      acc[prefix].push({ key, value });
      return acc;
    },
    {},
  );

  if (loading && Object.keys(settings).length === 0)
    return (
      <div className="container" style={{ padding: "20px" }}>
        Loading...
      </div>
    );

  return (
    <div className="container" style={{ padding: "20px" }}>
      <div className="header" style={{ marginBottom: "20px" }}>
        <h1>BSM Settings</h1>
      </div>

      <form onSubmit={handleSave} className="form-group">
        {Object.entries(groupedSettings).map(([group, items]) => (
          <div key={group} style={{ marginBottom: "30px" }}>
            <h2
              style={{
                textTransform: "capitalize",
                borderBottom: "1px solid var(--border-color)",
                paddingBottom: "10px",
                marginBottom: "15px",
              }}
            >
              {group} Settings
            </h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                gap: "20px",
                background: "var(--container-background-color)",
                padding: "20px",
                borderRadius: "8px",
                border: "1px solid var(--border-color)",
              }}
            >
              {items.map((item) => (
                <div
                  key={item.key}
                  style={{ display: "flex", flexDirection: "column" }}
                >
                  <label
                    htmlFor={item.key}
                    className="form-label"
                    style={{
                      marginBottom: "5px",
                      fontWeight: "bold",
                      fontSize: "0.9em",
                    }}
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
                      style={{ width: "100%", padding: "8px" }}
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
                      style={{ width: "100%", padding: "8px" }}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}

        <div
          style={{
            marginTop: "20px",
            display: "flex",
            justifyContent: "flex-end",
          }}
        >
          <button
            type="submit"
            className="button button-primary"
            disabled={loading}
            style={{ padding: "10px 20px", fontSize: "1em" }}
          >
            Save Settings
          </button>
        </div>
      </form>
    </div>
  );
};

export default BSMSettings;
