import { useState, useEffect, useRef, useCallback } from "react";

const useWebSocket = () => {
  const [lastMessage, setLastMessage] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);

  const connect = useCallback(() => {
    // If already connected or connecting, don't reconnect
    if (
      ws.current &&
      (ws.current.readyState === WebSocket.OPEN ||
        ws.current.readyState === WebSocket.CONNECTING)
    )
      return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    let host = window.location.host;

    // In dev mode, we might need to point to port 8000 explicitly if vite proxy doesn't handle WS upgrade perfectly
    // But vite config has ws: true, so it should work on same port as vite dev server

    // If we are running on port 5173 (Vite default), we want to connect to ws://localhost:5173/ws which proxies to 8000
    const wsUrl = `${protocol}//${host}/ws`;

    const token = localStorage.getItem("jwt_token");
    if (!token) {
      console.warn("No token found for WebSocket");
      return;
    }

    console.log(`Connecting to WebSocket at ${wsUrl}`);
    const socket = new WebSocket(`${wsUrl}?token=${encodeURIComponent(token)}`);
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
      // Close will trigger onclose which handles reconnect
      socket.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (ws.current) {
        ws.current.close();
      }
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
    };
  }, []); // Only run once on mount

  const sendMessage = (msg) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  };

  const subscribe = (topic) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: "subscribe", topic }));
    } else {
      console.warn(`Cannot subscribe to ${topic}, socket not open`);
    }
  };

  const unsubscribe = (topic) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: "unsubscribe", topic }));
    }
  };

  return { isConnected, lastMessage, sendMessage, subscribe, unsubscribe };
};

export default useWebSocket;
