import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { useAuth } from "./AuthContext";

const WebSocketContext = createContext(null);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const { user } = useAuth();
  const [lastMessage, setLastMessage] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isFallback, setIsFallback] = useState(false);
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const pendingSubscriptions = useRef(new Set());
  const connectRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const isConnecting = useRef(false);
  const MAX_RECONNECT_ATTEMPTS = 5;

  const connect = useCallback(async () => {
    // If not authenticated, don't attempt to connect
    if (!user) {
      return;
    }

    // If already connected, or explicitly connecting, don't reconnect
    if (
      ws.current &&
      (ws.current.readyState === WebSocket.OPEN ||
        ws.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    if (isConnecting.current) {
      return;
    }

    if (typeof window === "undefined") return;

    // Check if we should fallback
    if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
      console.warn(
        "Max reconnect attempts reached. Switching to polling fallback.",
      );
      // Yield to avoid synchronous state update in effect
      setTimeout(() => {
        setIsFallback(true);
        setIsConnected(false);
      }, 0);
      return;
    }

    isConnecting.current = true;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    let token = sessionStorage.getItem("jwt_token");
    if (!token) {
      token = localStorage.getItem("jwt_token");
    }

    // Attempt to refresh token only if we have a user (logic implies we should have a token)
    // or if we are retrying.
    if ((!token && user) || reconnectAttempts.current > 0) {
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
      isConnecting.current = false;
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
        setIsFallback(false);
        reconnectAttempts.current = 0; // Reset attempts on success
        isConnecting.current = false;

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
        isConnecting.current = false;

        // If closed because of auth error (1008), we might retry with refresh
        if (event.code === 1008) {
          console.error("WebSocket authentication failed.");
        }

        reconnectAttempts.current += 1;

        if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s... capped at 30s
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttempts.current - 1),
          30000,
        );
        console.log(`Reconnecting in ${delay}ms...`);

        // Use the ref to call the function recursively
        if (connectRef.current) {
          reconnectTimeout.current = setTimeout(connectRef.current, delay);
        }
      };

      socket.onerror = (error) => {
        console.error("WebSocket Error:", error);
        // onError usually followed by onClose, so we handle reconnect there
        isConnecting.current = false;
      };
    } catch (error) {
      console.error("WebSocket Connection Initialization Failed:", error);
      isConnecting.current = false;
      reconnectAttempts.current += 1;
      const delay = Math.min(
        1000 * Math.pow(2, reconnectAttempts.current - 1),
        30000,
      );
      if (connectRef.current) {
        reconnectTimeout.current = setTimeout(connectRef.current, delay);
      }
    }
  }, [user]);

  // Update the ref whenever connect changes
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    if (user) {
      connect();
    } else {
      // If user logs out, close connection
      if (ws.current) {
        console.log("User logged out, closing WebSocket.");
        // Prevent reconnect loop
        ws.current.onopen = null;
        ws.current.onmessage = null;
        ws.current.onerror = null;
        ws.current.onclose = null;
        ws.current.close();
        ws.current = null;
      }
      isConnecting.current = false;
      // Avoid calling setState synchronously
      setTimeout(() => {
        setIsConnected(false);
        setIsFallback(false);
      }, 0);
      reconnectAttempts.current = 0;
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    }

    return () => {
      if (ws.current) {
        ws.current.onopen = null;
        ws.current.onmessage = null;
        ws.current.onerror = null;
        ws.current.onclose = null;
        ws.current.close();
        ws.current = null;
      }
      isConnecting.current = false;
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, [connect, user]);

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
    reconnectAttempts.current = 0; // Reset attempts on manual reconnect
    setIsFallback(false);
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
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
        isFallback,
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
