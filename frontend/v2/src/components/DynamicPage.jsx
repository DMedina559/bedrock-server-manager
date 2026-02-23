import React, { useState, useEffect, useCallback, useRef } from "react";
import { get, post, getJwtToken } from "../api";
import { useToast } from "../ToastContext";
import { useSearchParams } from "react-router-dom";
import { useServer } from "../ServerContext";
import { useWebSocket } from "../WebSocketContext";
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
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  Play,
  Square,
  RotateCcw,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from "recharts";

import "../styles/DynamicPage.css";

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
  Divider: ({ className = "" }) => <hr className={`divider ${className}`} />,

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
  Badge: ({ content, variant = "primary", className = "" }) => (
    <span className={`badge ${variant} ${className}`}>{content}</span>
  ),
  CodeBlock: ({ content, title, className = "" }) => {
    const copyToClipboard = () => {
      navigator.clipboard.writeText(content);
    };
    return (
      <div className={`code-block ${className}`}>
        {(title || content) && (
          <div className="code-block-header">
            {title && <span>{title}</span>}
            <button
              onClick={copyToClipboard}
              style={{
                background: "none",
                border: "none",
                color: "inherit",
                cursor: "pointer",
              }}
              title="Copy"
            >
              <ComponentRegistry.Icon name="Copy" size={14} />
            </button>
          </div>
        )}
        <code>{content}</code>
      </div>
    );
  },

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
  Select: ({
    value,
    onChange,
    options,
    className = "",
    disabled = false,
    id,
  }) => (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange && onChange(e.target.value)}
      className={`form-input ${className}`}
      disabled={disabled}
    >
      {options &&
        options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
    </select>
  ),
  Switch: ({
    value,
    onChange,
    label,
    className = "",
    disabled = false,
    id,
  }) => (
    <div className={`switch-wrapper ${className}`}>
      <label className="switch" htmlFor={id}>
        <input
          type="checkbox"
          id={id}
          checked={!!value}
          onChange={(e) => onChange && onChange(e.target.checked)}
          disabled={disabled}
        />
        <span className="slider round"></span>
      </label>
      {label && (
        <label className="switch-label-text" htmlFor={id}>
          {label}
        </label>
      )}
    </div>
  ),
  Checkbox: ({
    value,
    onChange,
    label,
    className = "",
    disabled = false,
    id,
  }) => (
    <label className={`checkbox-wrapper ${className}`} htmlFor={id}>
      <input
        type="checkbox"
        id={id}
        checked={!!value}
        onChange={(e) => onChange && onChange(e.target.checked)}
        disabled={disabled}
      />
      {label && <span className="form-label-inline">{label}</span>}
    </label>
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
  FileDownload: ({
    label,
    onClick,
    variant = "primary",
    className = "",
    style = {},
  }) => (
    <button
      className={`action-button ${variant === "secondary" ? "secondary" : ""} ${className}`}
      onClick={onClick}
      style={{ ...style, display: "flex", alignItems: "center", gap: "5px" }}
    >
      <ComponentRegistry.Icon name="Download" size={16} />
      {label || "Download"}
    </button>
  ),

  // Media
  Image: ({ src, alt, width, height, className = "" }) => (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      className={`dynamic-image ${className}`}
    />
  ),
  iframe: ({ src, title, height = "400px", className = "" }) => (
    <iframe
      src={src}
      title={title}
      height={height}
      className={`dynamic-iframe ${className}`}
    />
  ),
  Link: ({ href, label, target = "_self", className = "", icon }) => {
    const Icon = icon
      ? ComponentRegistry.Icon({ name: icon, size: 14 })
      : target === "_blank"
        ? ComponentRegistry.Icon({ name: "ExternalLink", size: 14 })
        : null;
    return (
      <a
        href={href}
        target={target}
        className={`action-link ${className}`}
        style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}
      >
        {label}
        {Icon}
      </a>
    );
  },

  // Advanced Visualizations
  Chart: ({
    type = "line",
    data,
    xAxis,
    series,
    height = 300,
    className = "",
  }) => {
    const ChartComponent =
      type === "area" ? AreaChart : type === "bar" ? BarChart : LineChart;
    const DataComponent = type === "area" ? Area : type === "bar" ? Bar : Line;

    return (
      <div
        className={`chart-container ${className}`}
        style={{ width: "100%", height: height }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ChartComponent data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#444" />
            <XAxis dataKey={xAxis} stroke="#888" />
            <YAxis stroke="#888" />
            <Tooltip
              contentStyle={{
                backgroundColor: "#333",
                border: "1px solid #555",
              }}
              labelStyle={{ color: "#ccc" }}
            />
            {series &&
              series.map((s, idx) => (
                <DataComponent
                  key={idx}
                  type="monotone"
                  dataKey={s.dataKey}
                  stroke={s.color}
                  fill={s.color} // For Area/Bar
                  name={s.name}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
          </ChartComponent>
        </ResponsiveContainer>
      </div>
    );
  },
  LogViewer: ({ lines, height = 200, className = "" }) => {
    const logEndRef = useRef(null);
    useEffect(() => {
      if (logEndRef.current) {
        logEndRef.current.scrollIntoView({ behavior: "smooth" });
      }
    }, [lines]);

    return (
      <div className={`log-viewer ${className}`} style={{ height: height }}>
        {!lines || lines.length === 0 ? (
          <div className="log-placeholder">Waiting for logs...</div>
        ) : (
          lines.map((line, idx) => (
            <div key={idx} className="log-line">
              {line}
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    );
  },
  StatCard: ({ label, value, icon, trend, className = "" }) => (
    <div className={`stat-card ${className}`}>
      {icon && (
        <div className="stat-icon">
          <ComponentRegistry.Icon name={icon} size={24} />
        </div>
      )}
      <div className="stat-content">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {trend && (
          <div
            className={`stat-trend ${trend === "up" ? "trend-up" : trend === "down" ? "trend-down" : ""}`}
          >
            {trend === "up" ? "▲" : trend === "down" ? "▼" : "•"}
          </div>
        )}
      </div>
    </div>
  ),
  StatusIndicator: ({ status, text, className = "" }) => (
    <span className={`status-indicator status-${status} ${className}`}>
      <span className="status-dot">●</span> {text}
    </span>
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
      ChevronDown,
      ChevronUp,
      Copy,
      ExternalLink,
      Play,
      Square,
      RotateCcw,
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
  Accordion: ({ title, children, defaultOpen = false, className = "" }) => {
    const [isOpen, setIsOpen] = useState(defaultOpen);
    return (
      <div className={`accordion ${className}`}>
        <div className="accordion-header" onClick={() => setIsOpen(!isOpen)}>
          {title}
          <ComponentRegistry.Icon
            name={isOpen ? "ChevronUp" : "ChevronDown"}
            size={16}
          />
        </div>
        {isOpen && <div className="accordion-body">{children}</div>}
      </div>
    );
  },
  Modal: ({ isOpen, onClose, title, children, className = "" }) => {
    if (!isOpen) return null;
    return (
      <div className="dynamic-modal-overlay">
        <div className={`dynamic-modal-content ${className}`}>
          <div className="dynamic-modal-header">
            <h3>{title}</h3>
            <button className="dynamic-modal-close" onClick={onClose}>
              <ComponentRegistry.Icon name="X" size={20} />
            </button>
          </div>
          <div className="dynamic-modal-body">{children}</div>
        </div>
      </div>
    );
  },

  // Navigation
  Tabs: ({ children, activeTab, onTabChange, className = "" }) => {
    const [localActive, setLocalActive] = useState(activeTab || 0);

    // If activeTab changes from prop (e.g. schema re-fetch with new default), update state
    useEffect(() => {
      if (activeTab !== undefined) {
        setLocalActive(activeTab);
      }
    }, [activeTab]);

    // If children is not an array, make it one
    const childArray = React.Children.toArray(children);

    const tabHeaders = childArray.map((child, index) => {
      return {
        id: child.props.id || index,
        label: child.props.label || `Tab ${index + 1}`,
      };
    });

    const isControlled = onTabChange !== undefined;
    const currentTabId =
      isControlled && activeTab !== undefined ? activeTab : localActive;

    const handleTabClick = (id) => {
      if (!isControlled) {
        setLocalActive(id);
      }
      if (onTabChange) onTabChange(id);
    };

    return (
      <div className={`tabs-container ${className}`}>
        <div
          className="tabs-header"
          style={{
            display: "flex",
            gap: "10px",
            borderBottom: "1px solid #ccc",
            marginBottom: "15px",
          }}
        >
          {tabHeaders.map((header) => (
            <button
              key={header.id}
              className={`tab-button ${currentTabId === header.id ? "active" : ""}`}
              onClick={() => handleTabClick(header.id)}
              style={{
                padding: "8px 16px",
                background: "transparent",
                border: "none",
                borderBottom:
                  currentTabId === header.id
                    ? "2px solid var(--primary-color, #007bff)"
                    : "2px solid transparent",
                cursor: "pointer",
                fontWeight: currentTabId === header.id ? "bold" : "normal",
                color: "inherit",
              }}
            >
              {header.label}
            </button>
          ))}
        </div>
        <div className="tabs-content">
          {childArray.map((child) => {
            const childId = child.props.id || childArray.indexOf(child);
            if (childId !== currentTabId) return null;
            return <div key={childId}>{child}</div>;
          })}
        </div>
      </div>
    );
  },
  Tab: ({ children, className = "" }) => (
    <div className={`tab-panel ${className}`}>{children}</div>
  ),
};

const DynamicPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const dataUrl = searchParams.get("url");
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { addToast } = useToast();
  const { selectedServer } = useServer();
  const { isConnected, subscribe, unsubscribe, lastMessage } = useWebSocket();

  // State for inputs (basic form handling)
  // We'll store input values in a map: { [inputId]: value }
  const [formState, setFormState] = useState({});
  // State for active modal
  const [activeModalId, setActiveModalId] = useState(null);
  // State for WebSocket data: { [topic]: messageData }
  const [socketData, setSocketData] = useState({});

  // Using useCallback to define fetchSchema so it can be added to dependencies
  const fetchSchema = useCallback(
    async (url, server) => {
      setLoading(true);
      setError(null);
      try {
        // Construct URL with current search params
        const fetchUrlObj = new URL(url, window.location.origin);

        // Merge current search params into the fetch URL, excluding 'url' itself
        searchParams.forEach((value, key) => {
          if (key !== "url" && !fetchUrlObj.searchParams.has(key)) {
            fetchUrlObj.searchParams.append(key, value);
          }
        });

        // Append selected server if not present
        if (server && !fetchUrlObj.searchParams.has("server")) {
          fetchUrlObj.searchParams.append("server", server);
        }

        const relativeFetchUrl = fetchUrlObj.pathname + fetchUrlObj.search;

        const response = await get(relativeFetchUrl);
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
    },
    [searchParams],
  ); // Dependent on searchParams

  useEffect(() => {
    if (dataUrl) {
      setFormState({}); // Clear state on URL change
      setActiveModalId(null);
      setSocketData({}); // Clear socket data on page change
      fetchSchema(dataUrl, selectedServer);
    }
  }, [dataUrl, selectedServer, fetchSchema]);

  // Handle WebSocket subscriptions defined in schema
  useEffect(() => {
    if (!schema || !schema.websocketSubscriptions || !isConnected) return;

    const topics = schema.websocketSubscriptions
      .map((sub) => {
        // Replace placeholders like {server} with actual values
        return sub.replace("{server}", selectedServer || "");
      })
      .filter(Boolean);

    topics.forEach((topic) => subscribe(topic));

    return () => {
      topics.forEach((topic) => unsubscribe(topic));
    };
  }, [schema, isConnected, selectedServer, subscribe, unsubscribe]);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    // Update socketData map
    setSocketData((prev) => {
      const topic = lastMessage.topic;
      return { ...prev, [topic]: lastMessage };
    });
  }, [lastMessage]);

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
          // Refresh logic if needed
          if (actionDef.refresh) {
            // Trigger re-fetch logic if extracted
            fetchSchema(dataUrl, selectedServer);
          }
          if (actionDef.closeModal) setActiveModalId(null);
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
      if (actionDef.params) {
        const newParams = new URLSearchParams(searchParams);
        Object.keys(actionDef.params).forEach((key) => {
          newParams.set(key, actionDef.params[key]);
        });
        setSearchParams(newParams);
      } else if (actionDef.url) {
        const newParams = new URLSearchParams(searchParams);
        newParams.set("url", actionDef.url);
        setSearchParams(newParams);
      }
    } else if (actionDef.type === "open_modal") {
      if (actionDef.modalId) {
        setActiveModalId(actionDef.modalId);
      }
    } else if (actionDef.type === "close_modal") {
      setActiveModalId(null);
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

    // Inject Socket Data if needed
    if (props.socketTopic) {
      const topic = props.socketTopic.replace("{server}", selectedServer || "");
      const latestMsg = socketData[topic];

      props.latestSocketMessage = latestMsg;
    }

    // Wrapper for Chart to handle internal state for history
    if (node.type === "Chart") {
      return <ChartWrapper key={key} {...props} />;
    }

    // Wrapper for LogViewer
    if (node.type === "LogViewer") {
      return <LogViewerWrapper key={key} {...props} />;
    }

    // Wrapper for StatCard
    if (node.type === "StatCard") {
      return <StatCardWrapper key={key} {...props} />;
    }

    // Handle input binding
    if (
      node.type === "Input" ||
      node.type === "Select" ||
      node.type === "Switch" ||
      node.type === "Checkbox"
    ) {
      if (props.id) {
        const stateValue = formState[props.id];

        // For Switch and Checkbox, value is boolean
        if (node.type === "Switch" || node.type === "Checkbox") {
          props.value =
            stateValue !== undefined
              ? stateValue
              : props.checked || props.defaultChecked || false;
        } else {
          props.value =
            stateValue !== undefined
              ? stateValue
              : props.value || props.defaultValue || "";
        }

        props.onChange = (val) => {
          handleInputChange(props.id, val);
          if (props.onChangeAction) {
            const action = { ...props.onChangeAction };

            // If it's a navigation action, we might want to dynamically set a param based on the value
            if (action.type === "navigate" && action.dynamicParam) {
              if (!action.params) action.params = {};
              action.params[action.dynamicParam] = val;
            }

            handleAction(action);
          }
        };
      } else {
        if (node.type === "Input") props.readOnly = true;
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

    // Modal specific props
    if (node.type === "Modal") {
      props.isOpen = activeModalId === props.id;
      props.onClose = () => setActiveModalId(null);
    }

    // Special handling for Table rows to recursively render cells
    if (node.type === "Table" && Array.isArray(props.rows)) {
      props.rows = props.rows.map((row, rIndex) =>
        Array.isArray(row)
          ? row.map((cell, cIndex) => {
              if (cell && typeof cell === "object" && cell.type) {
                // Recursively render the cell if it looks like a component node
                return renderNode(cell, `row-${rIndex}-cell-${cIndex}`);
              }
              return cell;
            })
          : row,
      );
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

// --- Wrapper Components for State Handling ---

const ChartWrapper = ({ latestSocketMessage, data: initialData, ...props }) => {
  const [data, setData] = useState(initialData || []);

  useEffect(() => {
    if (latestSocketMessage && latestSocketMessage.data) {
      const newData = latestSocketMessage.data;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setData((prev) => {
        const updated = [...prev, newData];
        if (updated.length > 20) updated.shift();
        return updated;
      });
    }
  }, [latestSocketMessage]);

  return <ComponentRegistry.Chart data={data} {...props} />;
};

const LogViewerWrapper = ({
  latestSocketMessage,
  lines: initialLines,
  ...props
}) => {
  const [lines, setLines] = useState(initialLines || []);

  useEffect(() => {
    if (latestSocketMessage && latestSocketMessage.data) {
      const newContent = latestSocketMessage.data;
      const newLines =
        typeof newContent === "string" ? newContent.split("\n") : [newContent];
      if (newLines.length > 0 && newLines[newLines.length - 1] === "") {
        newLines.pop();
      }
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLines((prev) => [...prev, ...newLines].slice(-1000));
    }
  }, [latestSocketMessage]);

  return <ComponentRegistry.LogViewer lines={lines} {...props} />;
};

const StatCardWrapper = ({
  latestSocketMessage,
  value: initialValue,
  dataKey,
  ...props
}) => {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    if (latestSocketMessage && latestSocketMessage.data && dataKey) {
      const keys = dataKey.split(".");
      let current = latestSocketMessage.data;
      for (const key of keys) {
        if (current && current[key] !== undefined) {
          current = current[key];
        } else {
          current = undefined;
          break;
        }
      }
      if (current !== undefined) {
        setValue(current);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestSocketMessage]);

  return <ComponentRegistry.StatCard value={value} {...props} />;
};

export default DynamicPage;
