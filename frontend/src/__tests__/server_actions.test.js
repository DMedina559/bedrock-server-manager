import {
  startServer,
  stopServer,
  restartServer,
  promptCommand,
  deleteServer,
  triggerServerUpdate,
} from "../server_actions";
import { sendServerActionRequest, showStatusMessage } from "../utils";

// Mock utils
jest.mock("../utils", () => ({
  sendServerActionRequest: jest.fn(),
  showStatusMessage: jest.fn(),
}));

describe("server_actions.js", () => {
  let button;
  let serverSelect;

  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = `
            <select id="server-select">
                <option value="">-- Select --</option>
                <option value="Server1">Server1</option>
            </select>
            <button id="action-btn">Action</button>
        `;
    button = document.getElementById("action-btn");
    serverSelect = document.getElementById("server-select");
  });

  describe("helper getSelectedServer", () => {
    // Since getSelectedServer is internal, we test it via the exported functions that use it

    test("shows warning if no server selected", () => {
      serverSelect.value = "";
      startServer(button);

      expect(showStatusMessage).toHaveBeenCalledWith(
        expect.stringContaining("Please select a server"),
        "warning",
      );
      expect(sendServerActionRequest).not.toHaveBeenCalled();
    });

    test("shows error if dropdown missing", () => {
      document.body.innerHTML = ""; // Remove dropdown
      const btn = document.createElement("button");
      startServer(btn);

      expect(showStatusMessage).toHaveBeenCalledWith(
        expect.stringContaining("Server selection dropdown element"),
        "error",
      );
    });
  });

  describe("startServer", () => {
    test("calls sendServerActionRequest with correct params", () => {
      serverSelect.value = "Server1";
      startServer(button);

      expect(sendServerActionRequest).toHaveBeenCalledWith(
        "Server1",
        "start",
        "POST",
        null,
        button,
      );
    });
  });

  describe("stopServer", () => {
    test("calls sendServerActionRequest with correct params", () => {
      serverSelect.value = "Server1";
      stopServer(button);

      expect(sendServerActionRequest).toHaveBeenCalledWith(
        "Server1",
        "stop",
        "POST",
        null,
        button,
      );
    });
  });

  describe("restartServer", () => {
    test("calls sendServerActionRequest with correct params", () => {
      serverSelect.value = "Server1";
      restartServer(button);

      expect(sendServerActionRequest).toHaveBeenCalledWith(
        "Server1",
        "restart",
        "POST",
        null,
        button,
      );
    });
  });

  describe("promptCommand", () => {
    test("aborts if no server selected", () => {
      serverSelect.value = "";
      const promptSpy = jest.spyOn(window, "prompt").mockReturnValue("cmd");

      promptCommand(button);

      expect(promptSpy).not.toHaveBeenCalled();
      expect(sendServerActionRequest).not.toHaveBeenCalled();
    });

    test("sends command if input valid", () => {
      serverSelect.value = "Server1";
      jest.spyOn(window, "prompt").mockReturnValue("say hello");

      promptCommand(button);

      expect(sendServerActionRequest).toHaveBeenCalledWith(
        "Server1",
        "send_command",
        "POST",
        { command: "say hello" },
        button,
      );
    });

    test("handles cancel (null input)", () => {
      serverSelect.value = "Server1";
      jest.spyOn(window, "prompt").mockReturnValue(null);

      promptCommand(button);

      expect(showStatusMessage).toHaveBeenCalledWith(
        "Command input cancelled.",
        "info",
      );
      expect(sendServerActionRequest).not.toHaveBeenCalled();
    });

    test("handles empty input", () => {
      serverSelect.value = "Server1";
      jest.spyOn(window, "prompt").mockReturnValue("   ");

      promptCommand(button);

      expect(showStatusMessage).toHaveBeenCalledWith(
        "Command cannot be empty.",
        "warning",
      );
      expect(sendServerActionRequest).not.toHaveBeenCalled();
    });
  });

  describe("deleteServer", () => {
    test("sends delete request if confirmed", () => {
      jest.spyOn(window, "confirm").mockReturnValue(true);

      deleteServer(button, "ServerToDelete");

      expect(sendServerActionRequest).toHaveBeenCalledWith(
        "ServerToDelete",
        "delete",
        "DELETE",
        null,
        button,
      );
    });

    test("aborts if cancelled", () => {
      jest.spyOn(window, "confirm").mockReturnValue(false);

      deleteServer(button, "ServerToDelete");

      expect(showStatusMessage).toHaveBeenCalledWith(
        "Deletion cancelled.",
        "info",
      );
      expect(sendServerActionRequest).not.toHaveBeenCalled();
    });

    test("handles missing server name", () => {
      deleteServer(button, "");
      expect(showStatusMessage).toHaveBeenCalledWith(
        expect.stringContaining("Server name is missing"),
        "error",
      );
      expect(sendServerActionRequest).not.toHaveBeenCalled();
    });
  });

  describe("triggerServerUpdate", () => {
    test("calls sendServerActionRequest with correct params", () => {
      triggerServerUpdate(button, "Server1");

      expect(sendServerActionRequest).toHaveBeenCalledWith(
        "Server1",
        "update",
        "POST",
        null,
        button,
      );
    });

    test("handles missing server name", () => {
      triggerServerUpdate(button, null);
      expect(showStatusMessage).toHaveBeenCalledWith(
        expect.stringContaining("Server name is missing"),
        "error",
      );
      expect(sendServerActionRequest).not.toHaveBeenCalled();
    });
  });
});
