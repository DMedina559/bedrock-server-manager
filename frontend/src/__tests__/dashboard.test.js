import { initializeDashboard } from '../dashboard';
import { sendServerActionRequest, showStatusMessage } from '../utils';
import * as serverActions from '../server_actions';
import webSocketClient from '../websocket_client';

// Mock utils
jest.mock('../utils', () => ({
  sendServerActionRequest: jest.fn(),
  showStatusMessage: jest.fn(),
}));

// Mock server_actions
jest.mock('../server_actions', () => ({
  startServer: jest.fn(),
  stopServer: jest.fn(),
  restartServer: jest.fn(),
  promptCommand: jest.fn(),
  triggerServerUpdate: jest.fn(),
  deleteServer: jest.fn(),
}));

// Mock websocket client
jest.mock('../websocket_client', () => ({
  shouldUseFallback: jest.fn(),
  subscribe: jest.fn(),
  connect: jest.fn(), // If called from dashboard, though main.js calls it
}));

describe('dashboard.js', () => {
    let mockServers;
    
    beforeEach(() => {
        jest.clearAllMocks();
        
        // Setup DOM
        document.body.innerHTML = `
            <select id="server-select"></select>
            <div id="server-card-list">
                <!-- Servers will be added here -->
            </div>
            <div id="no-servers-message" style="display: none;">No servers</div>
            <div class="server-selection-section">
                <div class="action-buttons-group">
                    <button id="start-server-btn">Start</button>
                    <button id="stop-server-btn">Stop</button>
                    <button id="restart-server-btn">Restart</button>
                    <button id="prompt-command-btn">Command</button>
                    <button id="update-server-btn">Update</button>
                    <button id="delete-server-btn">Delete</button>
                </div>
            </div>
            <div class="server-dependent-actions">
                <span id="selected-server-name">(No server selected)</span>
                <a id="config-link-properties" class="action-link" href="#">Prop</a>
                <button class="action-button">Action</button>
            </div>
        `;

        mockServers = [
            { name: 'server1', status: 'RUNNING', version: '1.20', player_count: 5 },
            { name: 'server2', status: 'STOPPED', version: '1.19', player_count: 0 },
        ];
    });

    test('initializes and fetches servers', async () => {
        // Mock successful server fetch
        sendServerActionRequest.mockResolvedValueOnce({
            status: 'success',
            servers: mockServers
        });

        webSocketClient.shouldUseFallback.mockReturnValue(false);

        initializeDashboard();

        // Check initial loading call
        expect(sendServerActionRequest).toHaveBeenCalledWith(
            null, '/api/servers', 'GET', null, null, true
        );

        // Wait for async execution
        await Promise.resolve();
        await Promise.resolve();

        // Check if servers were rendered
        const cards = document.querySelectorAll('.server-card');
        expect(cards.length).toBe(2);
        expect(cards[0].innerHTML).toContain('server1');
        expect(cards[1].innerHTML).toContain('server2');

        // Check dropdown populated
        const select = document.getElementById('server-select');
        expect(select.options.length).toBe(3); // --Select-- + 2 servers
        expect(select.options[1].value).toBe('server1');
    });

    test('updates UI when server selected', async () => {
        sendServerActionRequest.mockResolvedValueOnce({ status: 'success', servers: mockServers });
        initializeDashboard();
        await Promise.resolve(); // Fetch done

        const select = document.getElementById('server-select');
        select.value = 'server1';
        select.dispatchEvent(new Event('change'));

        // Check if buttons enabled
        const startBtn = document.getElementById('start-server-btn');
        expect(startBtn.disabled).toBe(false);

        // Check links updated
        const propLink = document.getElementById('config-link-properties');
        expect(propLink.href).toContain('/server/server1/configure_properties');
    });

    test('handles no servers case', async () => {
        sendServerActionRequest.mockResolvedValueOnce({
            status: 'success',
            servers: []
        });

        initializeDashboard();
        await Promise.resolve();
        
        expect(document.getElementById('no-servers-message').style.display).toBe('block');
        const select = document.getElementById('server-select');
        expect(select.disabled).toBe(true);
    });

    test('handles fetch failure (null data)', async () => {
         sendServerActionRequest.mockResolvedValueOnce(null);

        initializeDashboard();
        await Promise.resolve();
        
        expect(showStatusMessage).toHaveBeenCalledWith(
            expect.stringContaining('Failed to update dashboard'), 
            'warning'
        );
    });

    test('wires up action buttons', async () => {
        sendServerActionRequest.mockResolvedValue({ status: 'success', servers: mockServers });
        initializeDashboard();
        await Promise.resolve();

        document.getElementById('start-server-btn').click();
        expect(serverActions.startServer).toHaveBeenCalled();

        document.getElementById('stop-server-btn').click();
        expect(serverActions.stopServer).toHaveBeenCalled();

        document.getElementById('restart-server-btn').click();
        expect(serverActions.restartServer).toHaveBeenCalled();
        
        document.getElementById('prompt-command-btn').click();
        expect(serverActions.promptCommand).toHaveBeenCalled();

        // For update and delete, we need a selected server
        const select = document.getElementById('server-select');
        select.value = 'server1'; 
        
        document.getElementById('update-server-btn').click();
        
        expect(serverActions.triggerServerUpdate).toHaveBeenCalledWith(
            expect.any(HTMLElement),
            'server1'
        );

        document.getElementById('delete-server-btn').click();
        expect(serverActions.deleteServer).toHaveBeenCalledWith(
            expect.any(HTMLElement),
            'server1'
        );
    });
    
    test('handles websocket refresh events', async () => {
        sendServerActionRequest.mockResolvedValue({ status: 'success', servers: mockServers });
        initializeDashboard();
        await Promise.resolve();
        sendServerActionRequest.mockClear();
        
        // Trigger a fake websocket event
        const event = new CustomEvent('websocket-message', {
            detail: { topic: 'event:after_server_statuses_updated' }
        });
        document.dispatchEvent(event);
        
        expect(sendServerActionRequest).toHaveBeenCalled();
    });

    test('uses polling fallback if websocket unavailable', () => {
        webSocketClient.shouldUseFallback.mockReturnValue(true);
        jest.useFakeTimers();
        
        sendServerActionRequest.mockResolvedValue({ status: 'success', servers: mockServers });
        
        initializeDashboard();
        
        expect(sendServerActionRequest).toHaveBeenCalledTimes(1);
        
        jest.advanceTimersByTime(60000);
        
        expect(sendServerActionRequest).toHaveBeenCalledTimes(2);
        
        jest.useRealTimers();
    });
});
