import React, { useState, useEffect } from "react";
import { useToast } from "../ToastContext";

const ServerProperties = () => {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    fetchProperties();
  }, []);

  const fetchProperties = async () => {
    try {
      const response = await fetch("/api/server/properties");
      if (response.ok) {
        const data = await response.json();
        // API returns { "server-name": "...", "gamemode": "..." }
        const propsArray = Object.entries(data).map(([key, value]) => ({
          key,
          value,
        }));
        // Sort properties alphabetically or by some order
        propsArray.sort((a, b) => a.key.localeCompare(b.key));
        setProperties(propsArray);
      } else {
        addToast("Failed to load server properties", "error");
      }
    } catch (error) {
      addToast("Error fetching server properties", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    const propsObj = properties.reduce((acc, curr) => {
      acc[curr.key] = curr.value;
      return acc;
    }, {});

    try {
      const response = await fetch("/api/server/properties", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(propsObj),
      });

      if (response.ok) {
        addToast("Server properties saved successfully.", "success");
      } else {
        addToast("Failed to save server properties.", "error");
      }
    } catch (error) {
      addToast("Error saving properties.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (index, newValue) => {
    const newProps = [...properties];
    newProps[index].value = newValue;
    setProperties(newProps);
  };

  if (loading && properties.length === 0)
    return (
      <div className="container" style={{ padding: "20px" }}>
        Loading...
      </div>
    );

  return (
    <div className="container" style={{ padding: "20px" }}>
      <div className="header" style={{ marginBottom: "20px" }}>
        <h1>Server Properties</h1>
      </div>

      <form onSubmit={handleSave} className="form-group">
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
          {properties.map((prop, index) => (
            <div
              key={prop.key}
              style={{ display: "flex", flexDirection: "column" }}
            >
              <label
                htmlFor={prop.key}
                className="form-label"
                style={{
                  marginBottom: "5px",
                  color: "var(--form-label-text-color)",
                  fontWeight: "bold",
                  fontSize: "0.9em",
                }}
              >
                {prop.key.replace(/-/g, " ")}
              </label>
              <input
                type="text"
                id={prop.key}
                className="form-input"
                value={prop.value}
                onChange={(e) => handleChange(index, e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: "4px",
                  border: "1px solid var(--form-input-border-color)",
                  background: "var(--form-input-background-color)",
                  color: "var(--form-input-text-color)",
                }}
              />
            </div>
          ))}
        </div>

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
            Save Changes
          </button>
        </div>
      </form>
    </div>
  );
};

export default ServerProperties;
