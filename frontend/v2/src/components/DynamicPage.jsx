import React, { useState, useEffect } from "react";
import { get, post, getJwtToken } from "../api";
import { useToast } from "../ToastContext";
import { useSearchParams } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Info,
  Terminal,
  Save,
  Trash2,
  Plus,
  X,
  Upload,
  Download,
} from "lucide-react";

// --- Component Registry ---
const ComponentRegistry = {
  // Layout
  Container: ({ children, className = "" }) => (
    <div className={`container ${className}`}>{children}</div>
  ),
  Card: ({ title, children, className = "" }) => (
    <div className={`server-card ${className}`}>
      {title && (
        <div className="server-card-header">
          <h3>{title}</h3>
        </div>
      )}
      <div className="server-card-body">{children}</div>
    </div>
  ),
  Row: ({ children, gap = "10px", className = "" }) => (
    <div
      className={className}
      style={{ display: "flex", flexDirection: "row", gap, flexWrap: "wrap" }}
    >
      {children}
    </div>
  ),
  Column: ({ children, gap = "10px", className = "", flex = 1 }) => (
    <div
      className={className}
      style={{ display: "flex", flexDirection: "column", gap, flex }}
    >
      {children}
    </div>
  ),

  // Typography
  Text: ({ content, variant = "body", className = "" }) => {
    const Tag =
      variant === "h1"
        ? "h1"
        : variant === "h2"
          ? "h2"
          : variant === "h3"
            ? "h3"
            : "p";
    return <Tag className={className}>{content}</Tag>;
  },
  Label: ({ content, htmlFor, className = "" }) => (
    <label htmlFor={htmlFor} className={`form-label ${className}`}>
      {content}
    </label>
  ),

  // Basic Inputs
  Button: ({
    label,
    onClick,
    variant = "primary",
    icon,
    disabled = false,
    className = "",
  }) => {
    const Icon = icon ? ComponentRegistry.Icon({ name: icon, size: 16 }) : null;
    return (
      <button
        className={`action-button ${variant === "secondary" ? "secondary" : ""} ${variant === "danger" ? "danger" : ""} ${className}`}
        onClick={onClick}
        disabled={disabled}
        style={{ display: "flex", alignItems: "center", gap: "5px" }}
      >
        {Icon}
        {label}
      </button>
    );
  },
  Input: ({
    type = "text",
    value,
    onChange,
    placeholder,
    className = "",
    readOnly = false,
  }) => (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange && onChange(e.target.value)}
      placeholder={placeholder}
      className={`form-input ${className}`}
      readOnly={readOnly}
    />
  ),
  FileUpload: ({ id, accept, onChange, className = "" }) => (
    <input
      type="file"
      id={id}
      accept={accept}
      onChange={(e) => onChange && onChange(e.target.files[0])}
      className={`form-input ${className}`}
    />
  ),
  FileDownload: ({ label, onClick, variant = "primary", className = "" }) => (
    <button
      className={`action-button ${variant === "secondary" ? "secondary" : ""} ${className}`}
      onClick={onClick}
      style={{ display: "flex", alignItems: "center", gap: "5px" }}
    >
      <ComponentRegistry.Icon name="Download" size={16} />
      {label || "Download"}
    </button>
  ),

  // Icons
  Icon: ({ name, size = 20, className = "" }) => {
    const icons = {
      Activity,
      AlertCircle,
      CheckCircle2,
      Info,
      Terminal,
      Save,
      Trash2,
      Plus,
      X,
      Upload,
      Download,
    };
    const LucideIcon = icons[name] || Info;
    return <LucideIcon size={size} className={className} />;
  },

  // Advanced
  Table: ({ headers, rows, className = "" }) => (
    <div className="table-container">
      <table className={`data-table ${className}`}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ),
};

const DynamicPage = () => {
  const [searchParams] = useSearchParams();
  const dataUrl = searchParams.get("url");
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { addToast } = useToast();

  // State for inputs (basic form handling)
  // We'll store input values in a map: { [inputId]: value }
  const [formState, setFormState] = useState({});

  useEffect(() => {
    if (dataUrl) {
      setFormState({}); // Clear state on URL change
      fetchSchema(dataUrl);
    }
  }, [dataUrl]);

  const fetchSchema = async (url) => {
    setLoading(true);
    setError(null);
    try {
      const response = await get(url);
      // Verify if response is valid schema
      if (
        response &&
        (Array.isArray(response) || typeof response === "object")
      ) {
        setSchema(response);
      } else {
        setError("Invalid page definition.");
      }
    } catch (err) {
      console.error("DynamicPage Error:", err);
      setError(err.message || "Error loading page.");
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (actionDef) => {
    if (!actionDef) return;

    if (actionDef.type === "api_call") {
      try {
        // Merge formState into payload if configured
        let payload = actionDef.payload || {};
        if (actionDef.includeFormState) {
          payload = { ...payload, ...formState };
        }

        let res;
        // Check for File objects in payload -> use FormData
        const hasFile = Object.values(payload).some(
          (val) => val instanceof File,
        );

        if (hasFile) {
          const formData = new FormData();
          Object.entries(payload).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
              formData.append(key, value);
            }
          });
          // api.post handles FormData correctly (lets browser set Content-Type)
          res = await post(actionDef.endpoint, formData);
        } else {
          res = await post(actionDef.endpoint, payload);
        }

        if (res && res.status === "success") {
          addToast(res.message || "Action successful", "success");
          if (actionDef.refresh) fetchSchema(dataUrl);
        } else {
          addToast(res?.message || "Action failed", "error");
        }
      } catch (err) {
        addToast(err.message || "Action error", "error");
      }
    } else if (actionDef.type === "download_file") {
      try {
        const jwtToken = getJwtToken();
        const headers = jwtToken ? { Authorization: `Bearer ${jwtToken}` } : {};

        const response = await fetch(actionDef.endpoint, { headers });
        if (!response.ok) throw new Error("Download failed");

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        // Simple filename fallback
        a.download = actionDef.filename || "download";
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } catch (err) {
        addToast("Download failed: " + err.message, "error");
      }
    } else if (actionDef.type === "navigate") {
      // handle navigation if needed, or window.location
    }
  };

  const handleInputChange = (id, value) => {
    setFormState((prev) => ({ ...prev, [id]: value }));
  };

  const renderNode = (node, key) => {
    if (!node) return null;
    if (typeof node === "string") return node;

    const Component = ComponentRegistry[node.type];
    if (!Component) {
      console.warn(`Unknown component type: ${node.type}`);
      return (
        <div
          key={key}
          style={{ color: "red", border: "1px dashed red", padding: "5px" }}
        >
          Unknown component: {node.type}
        </div>
      );
    }

    const props = { ...node.props };

    // Handle input binding
    if (node.type === "Input") {
      if (props.id) {
        const stateValue = formState[props.id];
        props.value =
          stateValue !== undefined
            ? stateValue
            : props.value || props.defaultValue || "";
        props.onChange = (val) => handleInputChange(props.id, val);
      } else {
        props.readOnly = true;
      }
    }

    if (node.type === "FileUpload") {
      if (props.id) {
        props.onChange = (file) => handleInputChange(props.id, file);
      }
    }

    if (node.type === "FileDownload") {
      props.onClick = () =>
        handleAction({
          type: "download_file",
          endpoint: props.endpoint,
          filename: props.filename,
        });
    }

    // Handle actions
    if (props.onClickAction) {
      props.onClick = () => handleAction(props.onClickAction);
      // delete props.onClickAction; // keep it or remove it, doesn't matter much for HTML props unless it leaks
    }

    const children = node.children
      ? node.children.map((child, i) => renderNode(child, i))
      : null;

    return (
      <Component key={key} {...props}>
        {children}
      </Component>
    );
  };

  if (loading) return <div className="container">Loading...</div>;
  if (error)
    return (
      <div className="container">
        <div className="message error">Error: {error}</div>
      </div>
    );
  if (!schema) return <div className="container">No schema loaded.</div>;

  return (
    <div className="dynamic-page-wrapper">
      {/* If schema is an array, render root nodes, else render single root */}
      {Array.isArray(schema)
        ? schema.map((node, i) => renderNode(node, i))
        : renderNode(schema, 0)}
    </div>
  );
};

export default DynamicPage;
