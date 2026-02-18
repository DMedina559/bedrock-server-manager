import { initializeDashboard } from "../dashboard";
import {
  startServer,
  sendCommand,
  deleteServer,
  fetchServers,
} from "../server_actions";
import { handleApiAction } from "../ui_utils";

// Mock dependencies
jest.mock("../server_actions");
jest.mock("../ui_utils");
jest.mock("../websocket_client");

describe("dashboard.js", () => {
  let serverSelect;
  let serverCardList;
  let startBtn, commandBtn, deleteBtn;

  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = `
      <select id="server-select">
          <option value="">-- Select --</option>
          <option value="Server1">Server1</option>
      </select>
      <div id="server-card-list"></div>
      <div id="no-servers-message" style="display: none;"></div>
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
          <span id="selected-server-name"></span>
          <a id="config-link-properties" class="action-link">Properties</a>
      </div>
    `;

    serverSelect = document.getElementById("server-select");
    serverCardList = document.getElementById("server-card-list");
    startBtn = document.getElementById("start-server-btn");
    commandBtn = document.getElementById("prompt-command-btn");
    deleteBtn = document.getElementById("delete-server-btn");

    fetchServers.mockResolvedValue({
      status: "success",
      servers: [
        { name: "Server1", status: "STOPPED", version: "1.0", player_count: 0 },
      ],
    });
  });

  test("initializes dashboard and fetches servers", async () => {
    initializeDashboard();
    expect(fetchServers).toHaveBeenCalled();
    // Wait for promise resolution (microtask queue)
    await Promise.resolve();

    expect(serverCardList.children.length).toBe(1);
    expect(serverCardList.children[0].dataset.serverName).toBe("Server1");
  });

  test("handles start button click", () => {
    initializeDashboard();
    serverSelect.value = "Server1";
    startBtn.click();

    expect(handleApiAction).toHaveBeenCalledWith(
      startBtn,
      expect.any(Function),
    );
    // Verify the callback calls startServer
    const callback = handleApiAction.mock.calls[0][1];
    callback();
    expect(startServer).toHaveBeenCalledWith("Server1");
  });

  test("handles command button click", () => {
    initializeDashboard();
    serverSelect.value = "Server1";
    jest.spyOn(window, "prompt").mockReturnValue("say hello");

    commandBtn.click();

    expect(handleApiAction).toHaveBeenCalledWith(
      commandBtn,
      expect.any(Function),
    );
    const callback = handleApiAction.mock.calls[0][1];
    callback();
    expect(sendCommand).toHaveBeenCalledWith("Server1", "say hello");
  });

  test("handles delete button click", () => {
    initializeDashboard();
    serverSelect.value = "Server1";
    jest.spyOn(window, "confirm").mockReturnValue(true);

    deleteBtn.click();

    expect(handleApiAction).toHaveBeenCalledWith(
      deleteBtn,
      expect.any(Function),
    );
    const callback = handleApiAction.mock.calls[0][1];
    callback();
    expect(deleteServer).toHaveBeenCalledWith("Server1");
  });

  test("updates UI when server selected", () => {
    initializeDashboard();
    serverSelect.value = "Server1";
    serverSelect.dispatchEvent(new Event("change"));

    const link = document.getElementById("config-link-properties");
    expect(link.href).toContain("/server/Server1/configure_properties");
  });
});
