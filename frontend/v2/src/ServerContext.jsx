import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { request } from "./api";
import { useAuth } from "./AuthContext";
import useWebSocket from "./hooks/useWebSocket";

const ServerContext = createContext();

export const useServer = () => useContext(ServerContext);

export const ServerProvider = ({ children }) => {
  const { user } = useAuth();
  const [servers, setServers] = useState([]);
  const [selectedServer, setSelectedServerState] = useState(
    localStorage.getItem("selectedServer") || null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const { isConnected, lastMessage, subscribe, unsubscribe } = useWebSocket();

  // Wrapper for setting selected server to also persist to localStorage
  const setSelectedServer = useCallback((serverName) => {
    setSelectedServerState(serverName);
    if (serverName) {
      localStorage.setItem("selectedServer", serverName);
    } else {
      localStorage.removeItem("selectedServer");
    }
  }, []);

  const fetchServers = useCallback(async () => {
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
            (s) => s.name === selectedServer,
          );

          if (!selectedServer || !currentSelectionExists) {
            // Default to the first server if selection is invalid or missing
            setSelectedServer(serverList[0].name);
          }
        } else {
          // No servers available
          setSelectedServer(null);
        }
        return true;
      } else {
        setServers([]);
        // If data.servers is missing, something is wrong.
        setError("Invalid server data received.");
        return false;
      }
    } catch (err) {
      console.error("Error fetching servers:", err);
      setError(err.message || "Failed to fetch servers");
      return false;
    } finally {
      setLoading(false);
    }
  }, [user, selectedServer, setSelectedServer]);

  useEffect(() => {
    if (user) {
      fetchServers();
    } else {
      // Clear sensitive state on logout
      setServers([]);
      setSelectedServer(null);
    }
  }, [user, fetchServers, setSelectedServer]);

  // Handle WebSocket subscriptions for server updates
  useEffect(() => {
    if (isConnected && user) {
      const refreshTopics = [
        "event:after_server_statuses_updated",
        "event:after_server_start",
        "event:after_server_stop",
        "event:after_delete_server_data",
        "event:after_server_updated",
        "event:server_install_complete",
      ];

      refreshTopics.forEach((topic) => subscribe(topic));

      return () => {
        refreshTopics.forEach((topic) => unsubscribe(topic));
      };
    }
  }, [isConnected, user, subscribe, unsubscribe]);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      const refreshTopics = [
        "event:after_server_statuses_updated",
        "event:after_server_start",
        "event:after_server_stop",
        "event:after_delete_server_data",
        "event:after_server_updated",
        "event:server_install_complete",
      ];

      if (refreshTopics.includes(lastMessage.topic)) {
        console.log("Refreshing servers due to WS event:", lastMessage.topic);
        fetchServers();
      }
    }
  }, [lastMessage, fetchServers]);

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
