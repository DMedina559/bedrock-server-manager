import { showStatusMessage, sendServerActionRequest } from '../utils';

// Mock fetch globally
global.fetch = jest.fn();

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

describe('utils.js', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = ''; // Clean up DOM
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('showStatusMessage', () => {
    test('displays message in #status-message-area and sets correct class', () => {
      const messageArea = document.createElement('div');
      messageArea.id = 'status-message-area';
      document.body.appendChild(messageArea);

      showStatusMessage('Operation successful', 'success');

      expect(messageArea.textContent).toBe('Operation successful');
      expect(messageArea.className).toBe('message-box message-success');
      expect(messageArea.style.opacity).toBe('1');
    });

    test('fades out and clears message after timeout', () => {
      const messageArea = document.createElement('div');
      messageArea.id = 'status-message-area';
      document.body.appendChild(messageArea);

      showStatusMessage('Fading message', 'info');

      // Fast-forward past the 5000ms delay
      jest.advanceTimersByTime(5000);

      expect(messageArea.style.opacity).toBe('0');
      expect(messageArea.style.transition).toBe('opacity 0.5s ease-out');

      // Fast-forward past the fade out animation (500ms)
      jest.advanceTimersByTime(500);

      expect(messageArea.textContent).toBe('');
      expect(messageArea.className).toBe('message-box');
    });

    test('falls back to alert if #status-message-area is missing', () => {
      const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});

      showStatusMessage('Critical Error', 'error');

      expect(alertSpy).toHaveBeenCalledWith('ERROR: Critical Error');
      alertSpy.mockRestore();
    });
  });

  describe('sendServerActionRequest', () => {
    // Helper to setup DOM elements usually involved
    let button;
    beforeEach(() => {
      button = document.createElement('button');
      // We also need status message area to avoid console warnings or alerts in tests unless expected
      const messageArea = document.createElement('div');
      messageArea.id = 'status-message-area';
      document.body.appendChild(messageArea);
    });

    test('constructs correct relative URL and sends POST request', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ status: 'success', message: 'OK' }),
      });

      const body = { action: 'start' };
      const result = await sendServerActionRequest('my-server', 'start', 'POST', body);

      expect(fetch).toHaveBeenCalledWith(
        '/api/server/my-server/start',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Accept: 'application/json',
          }),
          body: JSON.stringify(body),
        })
      );
      expect(result).toEqual({ status: 'success', message: 'OK' });
    });

    test('adds Authorization header if JWT token exists', async () => {
      localStorageMock.getItem.mockReturnValue('fake-jwt-token');
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ({ status: 'success' }),
      });

      await sendServerActionRequest('s1', 'a1');

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer fake-jwt-token',
          }),
        })
      );
    });

    test('disables and re-enables button', async () => {
        fetch.mockResolvedValueOnce({
            ok: true,
            status: 200,
            headers: { get: () => 'application/json' },
            json: async () => ({ status: 'success' }),
        });

        const promise = sendServerActionRequest('s1', 'a1', 'POST', null, button);
        
        // Button should be disabled immediately
        expect(button.disabled).toBe(true);

        await promise;

        // Button should be enabled after
        expect(button.disabled).toBe(false);
    });

    test('handles 204 No Content correctly', async () => {
        fetch.mockResolvedValueOnce({
            ok: true,
            status: 204,
            headers: { get: () => null },
            json: async () => ({}), // Should not be called
        });

        const result = await sendServerActionRequest('s1', 'a1');
        
        expect(result).toEqual({
            status: 'success', 
            message: expect.stringContaining('successful (No Content)')
        });
    });

    test('handles HTTP errors (non-2xx)', async () => {
        fetch.mockResolvedValueOnce({
            ok: false,
            status: 404,
            headers: { get: () => 'application/json' },
            json: async () => ({ message: 'Not Found' }),
        });

        const result = await sendServerActionRequest('s1', 'a1');

        expect(result).toBe(false);
        // Verify status message updated (we know it calls showStatusMessage)
        const messageArea = document.getElementById('status-message-area');
        expect(messageArea.textContent).toBe('Not Found');
        expect(messageArea.className).toContain('message-error');
    });

    test('handles invalid JSON response', async () => {
        fetch.mockResolvedValueOnce({
            ok: true, // HTTP success but bad content
            status: 200,
            headers: { get: () => 'text/html' }, // Unexpected content type
            text: async () => '<html>...</html>',
        });

        const result = await sendServerActionRequest('s1', 'a1');
        
        expect(result).toBe(false);
    });

    test('handles network failure', async () => {
        fetch.mockRejectedValueOnce(new Error('Network error'));

        const result = await sendServerActionRequest('s1', 'a1');

        expect(result).toBe(false);
        const messageArea = document.getElementById('status-message-area');
        expect(messageArea.textContent).toContain('Network error');
    });
  });
});
