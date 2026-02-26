import {
  startServer,
  stopServer,
  restartServer,
  sendCommand,
  deleteServer,
  updateServer,
  fetchServers,
  getServerUsage,
} from "../server_actions";
import { request } from "../api";

// Mock request
jest.mock("../api", () => ({
  request: jest.fn(),
}));

describe("server_actions.js (API)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("startServer", () => {
    test("calls request with correct params", () => {
      startServer("Server1");
      expect(request).toHaveBeenCalledWith("/api/server/Server1/start", {
        method: "POST",
      });
    });

    test("throws if server name missing", () => {
      expect(() => startServer()).toThrow("Server name is required");
    });
  });

  describe("stopServer", () => {
    test("calls request with correct params", () => {
      stopServer("Server1");
      expect(request).toHaveBeenCalledWith("/api/server/Server1/stop", {
        method: "POST",
      });
    });
  });

  describe("restartServer", () => {
    test("calls request with correct params", () => {
      restartServer("Server1");
      expect(request).toHaveBeenCalledWith("/api/server/Server1/restart", {
        method: "POST",
      });
    });
  });

  describe("sendCommand", () => {
    test("calls request with command in body", () => {
      sendCommand("Server1", "say hello");
      expect(request).toHaveBeenCalledWith("/api/server/Server1/send_command", {
        method: "POST",
        body: { command: "say hello" },
      });
    });

    test("throws if command empty", () => {
      expect(() => sendCommand("Server1", "")).toThrow(
        "Command cannot be empty",
      );
    });
  });

  describe("deleteServer", () => {
    test("calls request with DELETE method", () => {
      deleteServer("Server1");
      expect(request).toHaveBeenCalledWith("/api/server/Server1/delete", {
        method: "DELETE",
      });
    });
  });

  describe("updateServer", () => {
    test("calls request with correct params", () => {
      updateServer("Server1");
      expect(request).toHaveBeenCalledWith("/api/server/Server1/update", {
        method: "POST",
      });
    });
  });

  describe("fetchServers", () => {
    test("calls request for server list", () => {
      fetchServers();
      expect(request).toHaveBeenCalledWith("/api/servers", { method: "GET" });
    });
  });

  describe("getServerUsage", () => {
    test("calls request for process info", () => {
      getServerUsage("Server1");
      expect(request).toHaveBeenCalledWith("/api/server/Server1/process_info", {
        method: "GET",
      });
    });
  });
});
