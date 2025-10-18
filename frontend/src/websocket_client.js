/**
 * WebSocket Client Module
 *
 * Manages a single, shared WebSocket connection for the entire application.
 * It handles connection, disconnection, message passing, and a fallback mechanism.
 */

class WebSocketClient {
  constructor() {
    this.socket = null;
    this.connectionState = 'disconnected'; // 'disconnected', 'connecting', 'connected'
    this.useFallback = false;
    this.pendingSubscriptions = [];
  }

  /**
   * Attempts to establish a WebSocket connection.
   * If a connection is already established or in progress, this does nothing.
   */
  connect() {
    if (this.socket || this.connectionState === 'connecting') {
      console.log('WebSocketClient.connect(): Connection attempt already in progress or established.');
      return;
    }
    if (this.useFallback) {
      console.log('WebSocketClient.connect(): Fallback is active, not attempting to connect.');
      return;
    }

    console.log('WebSocketClient.connect(): Attempting to establish connection...');
    this.connectionState = 'connecting';
    const protocol = window.location.protocol === 'https' ? 'wss' : 'ws';
    const token = localStorage.getItem('jwt_token');

    if (!token) {
      console.error('WebSocketClient.connect(): JWT token not found in localStorage. Cannot authenticate.');
      this.handleConnectionFailure();
      return;
    }

    const wsUrl = `${protocol}://${window.location.host}/ws?token=${encodeURIComponent(token)}`;
    console.log(`WebSocketClient.connect(): Connecting to ${wsUrl}`);

    try {
      this.socket = new WebSocket(wsUrl);
    } catch (error) {
      console.error('WebSocketClient.connect(): WebSocket initialization failed:', error);
      this.handleConnectionFailure();
      return;
    }

    this.socket.onopen = () => {
      console.log('WebSocketClient.onopen: Connection established successfully.');
      this.connectionState = 'connected';
      // Subscribe to any topics that were requested before the connection was ready
      this.pendingSubscriptions.forEach((topic) => this.subscribe(topic));
      this.pendingSubscriptions = [];
    };

    this.socket.onclose = (event) => {
      console.log(`WebSocketClient.onclose: Connection closed. Code: ${event.code}, Reason: "${event.reason}", Clean: ${event.wasClean}`);
      this.connectionState = 'disconnected';
      this.socket = null;
      // If the connection was not closed cleanly, we activate the fallback.
      if (!event.wasClean) {
        this.handleConnectionFailure();
      } else {
        this.useFallback = true; // Also use fallback on clean close for simplicity
      }
    };

    this.socket.onerror = (error) => {
      console.error('WebSocketClient.onerror: An error occurred with the WebSocket.', error);
      this.handleConnectionFailure();
    };

    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        // Dispatch a generic event that includes the topic and data from the server.
        // UI components can listen for this event to get real-time updates.
        const customEvent = new CustomEvent('websocket-message', {
          detail: message,
        });
        document.dispatchEvent(customEvent);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
  }

  /**
   * Centralized handler for connection failures.
   */
  handleConnectionFailure() {
    // Prevent multiple fallback triggers
    if (this.useFallback) return;

    console.warn('WebSocketClient.handleConnectionFailure(): WebSocket connection failed. Activating fallback.');
    this.connectionState = 'disconnected';
    this.useFallback = true;
    this.socket = null;
    // Dispatch an event to notify the app that WS failed and it should use polling
    document.dispatchEvent(new CustomEvent('websocket-fallback'));
  }

  /**
   * Sends a JSON message to the server.
   * @param {object} message - The message object to send.
   */
  sendMessage(message) {
    if (this.connectionState !== 'connected' || !this.socket) {
      // If not connected, don't log an error, as this might be expected
      // if the connection is in progress or has failed.
      return;
    }
    this.socket.send(JSON.stringify(message));
  }

  /**
   * Subscribes to a topic for server-sent events.
   * @param {string} topic - The topic to subscribe to.
   */
  subscribe(topic) {
    // If not connected yet, queue the subscription
    if (this.connectionState !== 'connected') {
      if (!this.pendingSubscriptions.includes(topic)) {
        this.pendingSubscriptions.push(topic);
      }
      return;
    }
    this.sendMessage({ action: 'subscribe', topic });
  }

  /**
   * Unsubscribes from a topic.
   * @param {string} topic - The topic to unsubscribe from.
   */
  unsubscribe(topic) {
    this.sendMessage({ action: 'unsubscribe', topic });
  }

  /**
   * Checks if the application should use the polling fallback.
   * @returns {boolean} - True if WebSockets are not available.
   */
  shouldUseFallback() {
    return this.useFallback;
  }
}

// Export a singleton instance so the entire app shares one WebSocket connection.
const webSocketClient = new WebSocketClient();

export default webSocketClient;
