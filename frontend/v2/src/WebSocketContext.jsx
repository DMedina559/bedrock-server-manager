import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";

const WebSocketContext = createContext(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [lastMessage, setLastMessage] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const pendingSubscriptions = useRef(new Set());
  const connectRef = useRef(null);
  const reconnectAttempts = useRef(0);

  const connect = useCallback(async () => {
    // If already connected or connecting, don't reconnect
    if (
      ws.current &&
      (ws.current.readyState === WebSocket.OPEN ||
        ws.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    if (typeof window === "undefined") return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    let token = sessionStorage.getItem("jwt_token");
    if (!token) {
      token = localStorage.getItem("jwt_token");
    }

    // Try to refresh token if missing or if previous attempts failed
    if (!token || reconnectAttempts.current > 0) {
      console.log("Refreshing token for WebSocket...");
      try {
        const response = await fetch("/auth/refresh-token");
        if (response.ok) {
          const data = await response.json();
          if (data.access_token) {
            token = data.access_token;
            sessionStorage.setItem("jwt_token", token);
          }
        }
      } catch (e) {
        console.error("Failed to refresh token", e);
      }
    }

    if (!token) {
      console.warn("No token found for WebSocket, skipping connection.");
      return;
    }

    console.log(`Connecting to WebSocket at ${wsUrl}`);

    try {
      const socket = new WebSocket(
        `${wsUrl}?token=${encodeURIComponent(token)}`,
      );
      ws.current = socket;

      socket.onopen = () => {
        console.log("WebSocket Connected");
        setIsConnected(true);
        reconnectAttempts.current = 0; // Reset attempts on success

        if (pendingSubscriptions.current.size > 0) {
          console.log(
            `Flushing ${pendingSubscriptions.current.size} pending subscriptions`,
          );
          pendingSubscriptions.current.forEach((topic) => {
            socket.send(JSON.stringify({ action: "subscribe", topic }));
          });
        }
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch (e) {
          console.error("Failed to parse WS message", e);
        }
      };

      socket.onclose = (event) => {
        console.log(
          `WebSocket Disconnected. Code: ${event.code}, Reason: ${event.reason}`,
        );
        setIsConnected(false);
        ws.current = null;

        if (event.code === 1008) {
          console.error("WebSocket authentication failed.");
          // We will retry, but maybe force a token refresh next time
          reconnectAttempts.current += 1;
        }

        if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
        // Use the ref to call the function recursively
        if (connectRef.current) {
          reconnectTimeout.current = setTimeout(connectRef.current, 3000);
        }
      };

      socket.onerror = (error) => {
        console.error("WebSocket Error:", error);
      };
    } catch (error) {
      console.error("WebSocket Connection Initialization Failed:", error);
    }
  }, []);

  // Update the ref whenever connect changes (though it shouldn't change often)
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      if (ws.current) {
        ws.current.onopen = null;
        ws.current.onmessage = null;
        ws.current.onerror = null;
        ws.current.onclose = null;
        ws.current.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    } else {
      console.warn("WebSocket not open, message not sent:", msg);
    }
  }, []);

  const subscribe = useCallback((topic) => {
    pendingSubscriptions.current.add(topic);
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: "subscribe", topic }));
    }
  }, []);

  const unsubscribe = useCallback((topic) => {
    pendingSubscriptions.current.delete(topic);
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: "unsubscribe", topic }));
    }
  }, []);

  const reconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close(); // This will trigger onclose which triggers reconnect
    } else {
      connect();
    }
  }, [connect]);

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        lastMessage,
        sendMessage,
        subscribe,
        unsubscribe,
        reconnect,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};
