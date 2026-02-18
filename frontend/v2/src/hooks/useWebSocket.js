import { useState, useEffect, useRef, useCallback } from "react";

const useWebSocket = () => {
  const [lastMessage, setLastMessage] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);

  useEffect(() => {
    const connect = () => {
      // If already connected or connecting, don't reconnect
      if (
        ws.current &&
        (ws.current.readyState === WebSocket.OPEN ||
          ws.current.readyState === WebSocket.CONNECTING)
      )
        return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;

      const wsUrl = `${protocol}//${host}/ws`;

      const token = localStorage.getItem("jwt_token");
      if (!token) {
        console.warn("No token found for WebSocket");
        return;
      }

      console.log(`Connecting to WebSocket at ${wsUrl}`);
      const socket = new WebSocket(
        `${wsUrl}?token=${encodeURIComponent(token)}`,
      );
      ws.current = socket;

      socket.onopen = () => {
        console.log("WebSocket Connected");
        setIsConnected(true);
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
        // Simple retry with backoff
        if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
        reconnectTimeout.current = setTimeout(connect, 3000);
      };

      socket.onerror = (error) => {
        console.error("WebSocket Error:", error);
        socket.close();
      };
    };

    connect();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, []);

  const sendMessage = useCallback((msg) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  }, []);

  const subscribe = useCallback((topic) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: "subscribe", topic }));
    } else {
      console.warn(`Cannot subscribe to ${topic}, socket not open`);
    }
  }, []);

  const unsubscribe = useCallback((topic) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: "unsubscribe", topic }));
    }
  }, []);

  return { isConnected, lastMessage, sendMessage, subscribe, unsubscribe };
};

export default useWebSocket;
