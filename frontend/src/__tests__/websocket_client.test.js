import { WebSocketClient } from '../websocket_client';

// Mock localStorage
const localStorageMock = (function () {
  let store = {};
  return {
    getItem: jest.fn((key) => store[key] || null),
    setItem: jest.fn((key, value) => {
      store[key] = value.toString();
    }),
    clear: jest.fn(() => {
      store = {};
    }),
    removeItem: jest.fn((key) => {
      delete store[key];
    }),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock fetch globally
global.fetch = jest.fn();

// Mock WebSocket
class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.send = jest.fn();
    this.close = jest.fn();
    this.onopen = null;
    this.onclose = null;
    this.onerror = null;
    this.onmessage = null;
    
    MockWebSocket.instances.push(this);
  }
}
MockWebSocket.instances = [];
global.WebSocket = MockWebSocket;

describe('WebSocketClient', () => {
  let client;
  let dispatchSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    MockWebSocket.instances = [];
    localStorageMock.getItem.mockReturnValue('valid-token');
    
    dispatchSpy = jest.spyOn(document, 'dispatchEvent');
    
    client = new WebSocketClient();
  });

  afterEach(() => {
      dispatchSpy.mockRestore();
  });

  test('initializes with default state', () => {
    expect(client.connectionState).toBe('disconnected');
    expect(client.useFallback).toBe(false);
  });

  test('connects successfully', async () => {
    await client.connect();

    expect(client.connectionState).toBe('connecting');
    expect(MockWebSocket.instances.length).toBe(1);
    const mockSocket = MockWebSocket.instances[0];
    // JSDOM defaults to localhost
    expect(mockSocket.url).toBe('ws://localhost/ws?token=valid-token');

    // Simulate connection open
    mockSocket.onopen();

    expect(client.connectionState).toBe('connected');
    expect(client.isConnected()).toBe(true);
  });

  test('tries to refresh token if missing', async () => {
    localStorageMock.getItem.mockReturnValue(null); // No token initially
    
    // Mock successful refresh
    fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: 'refreshed-token' })
    });

    await client.connect();

    expect(fetch).toHaveBeenCalledWith('/auth/refresh-token');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('jwt_token', 'refreshed-token');
    
    // Should proceed to connect with new token
    expect(MockWebSocket.instances.length).toBe(1);
    expect(MockWebSocket.instances[0].url).toContain('refreshed-token');
  });

  test('fails if token missing and refresh fails', async () => {
    localStorageMock.getItem.mockReturnValue(null);
    fetch.mockResolvedValueOnce({
        ok: false,
        status: 401
    });

    await client.connect();

    expect(client.connectionState).toBe('disconnected');
    expect(client.useFallback).toBe(true);
    expect(MockWebSocket.instances.length).toBe(0);
  });

  test('queues subscriptions when not connected', async () => {
    client.subscribe('topic1');
    expect(client.pendingSubscriptions).toContain('topic1');
    expect(MockWebSocket.instances.length).toBe(0); // Not connected yet

    await client.connect();
    const mockSocket = MockWebSocket.instances[0];
    mockSocket.onopen();

    expect(mockSocket.send).toHaveBeenCalledWith(JSON.stringify({ action: 'subscribe', topic: 'topic1' }));
    expect(client.pendingSubscriptions).toEqual([]);
  });

  test('sends message when connected', async () => {
    await client.connect();
    const mockSocket = MockWebSocket.instances[0];
    mockSocket.onopen();

    client.sendMessage({ type: 'ping' });
    expect(mockSocket.send).toHaveBeenCalledWith(JSON.stringify({ type: 'ping' }));
  });

  test('handles incoming messages', async () => {
    await client.connect();
    const mockSocket = MockWebSocket.instances[0];
    mockSocket.onopen();

    const payload = { type: 'update', data: 123 };
    mockSocket.onmessage({ data: JSON.stringify(payload) });

    expect(dispatchSpy).toHaveBeenCalledWith(expect.any(CustomEvent));
    const event = dispatchSpy.mock.calls[0][0];
    expect(event.type).toBe('websocket-message');
    expect(event.detail).toEqual(payload);
  });

  test('handles WebSocket initialization error', async () => {
    global.WebSocket = jest.fn(() => { throw new Error('Init failed'); });
    await client.connect();

    expect(client.useFallback).toBe(true);
    
    // Restore Mock
    global.WebSocket = MockWebSocket;
  });

  test('activates fallback on unclean close', async () => {
    await client.connect();
    const mockSocket = MockWebSocket.instances[0];
    mockSocket.onopen();

    mockSocket.onclose({ wasClean: false, code: 1006 });

    expect(client.useFallback).toBe(true);
    expect(client.connectionState).toBe('disconnected');
    expect(dispatchSpy).toHaveBeenCalledWith(expect.any(CustomEvent));
    const event = dispatchSpy.mock.calls.find(call => call[0].type === 'websocket-fallback');
    expect(event).toBeTruthy();
  });
  
  test('isConnected and isConnecting helpers', async () => {
    expect(client.isConnected()).toBe(false);
    expect(client.isConnecting()).toBe(false);
    
    const connectPromise = client.connect();
    
    expect(client.isConnecting()).toBe(true);
    await connectPromise;
    
    // Socket created but not open yet
    expect(client.isConnecting()).toBe(true);
    
    const mockSocket = MockWebSocket.instances[0];
    mockSocket.onopen();
    expect(client.isConnected()).toBe(true);
    expect(client.isConnecting()).toBe(false);
  });
});
