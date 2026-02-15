import React, { createContext, useContext, useState, useEffect } from "react";
import { request } from "./api";
import { useAuth } from "./AuthContext";

const ServerContext = createContext();

export const useServer = () => useContext(ServerContext);

export const ServerProvider = ({ children }) => {
  const { user } = useAuth();
  const [servers, setServers] = useState([]);
  const [selectedServer, setSelectedServerState] = useState(
    localStorage.getItem("selectedServer") || null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Wrapper for setting selected server to also persist to localStorage
  const setSelectedServer = (serverName) => {
    setSelectedServerState(serverName);
    if (serverName) {
      localStorage.setItem("selectedServer", serverName);
    } else {
      localStorage.removeItem("selectedServer");
    }
  };

  const fetchServers = async () => {
    if (!user) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // Use the API client we just created
      const data = await request("/api/servers", { method: "GET" });

      if (data && data.status === "success" && Array.isArray(data.servers)) {
        setServers(data.servers);

        const serverList = data.servers;
        if (serverList.length > 0) {
          // Check if currently selected server still exists
          const currentSelectionExists = serverList.some(
            (s) => s.name === selectedServer
          );

          if (!selectedServer || !currentSelectionExists) {
            // Default to the first server if selection is invalid or missing
            setSelectedServer(serverList[0].name);
          }
        } else {
          // No servers available
          setSelectedServer(null);
        }
      } else {
        setServers([]);
        // If data.servers is missing, something is wrong.
        setError("Invalid server data received.");
      }
    } catch (err) {
      console.error("Error fetching servers:", err);
      setError(err.message || "Failed to fetch servers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchServers();
    } else {
        // Clear sensitive state on logout
        setServers([]);
        setSelectedServer(null);
    }
  }, [user]);

  const refreshServers = () => {
    return fetchServers();
  };

  return (
    <ServerContext.Provider
      value={{
        servers,
        selectedServer,
        setSelectedServer,
        loading,
        error,
        refreshServers,
      }}
    >
      {children}
    </ServerContext.Provider>
  );
};
