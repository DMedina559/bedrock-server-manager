import { showStatusMessage, handleApiAction } from "../ui_utils";
import { ApiError } from "../api";

// Mock localStorage if needed (showStatusMessage doesn't use it, but good to have context)
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  clear: jest.fn(),
  removeItem: jest.fn(),
};
Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("ui_utils.js", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = ""; // Clean up DOM
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe("showStatusMessage", () => {
    test("displays message in #status-message-area", () => {
      const messageArea = document.createElement("div");
      messageArea.id = "status-message-area";
      document.body.appendChild(messageArea);

      showStatusMessage("Test message", "success");

      expect(messageArea.textContent).toBe("Test message");
      expect(messageArea.className).toBe("message-box message-success");
      expect(messageArea.style.opacity).toBe("1");
    });

    test("falls back to alert if area missing", () => {
      const alertSpy = jest.spyOn(window, "alert").mockImplementation(() => {});
      showStatusMessage("Critical Error", "error");
      expect(alertSpy).toHaveBeenCalledWith("ERROR: Critical Error");
      alertSpy.mockRestore();
    });
  });

  describe("handleApiAction", () => {
    let button;
    beforeEach(() => {
      button = document.createElement("button");
      const messageArea = document.createElement("div");
      messageArea.id = "status-message-area";
      document.body.appendChild(messageArea);
    });

    test("disables button while executing async function", async () => {
      const asyncFn = jest.fn(
        () => new Promise((resolve) => setTimeout(resolve, 100)),
      );

      const promise = handleApiAction(button, asyncFn);

      expect(button.disabled).toBe(true);

      jest.runAllTimers();
      await promise;

      expect(button.disabled).toBe(false);
    });

    test("shows loading message if provided", async () => {
      const asyncFn = jest.fn().mockResolvedValue({ status: "success" });

      await handleApiAction(button, asyncFn, "Wait...");

      expect(asyncFn).toHaveBeenCalled();
    });

    test("handles success result", async () => {
      const asyncFn = jest
        .fn()
        .mockResolvedValue({ status: "success", message: "Done" });

      await handleApiAction(button, asyncFn);

      const messageArea = document.getElementById("status-message-area");
      expect(messageArea.textContent).toBe("Done");
      expect(messageArea.className).toContain("message-success");
    });

    test("handles ApiError", async () => {
      const asyncFn = jest
        .fn()
        .mockRejectedValue(new ApiError("API Failed", 500));

      await handleApiAction(button, asyncFn);

      const messageArea = document.getElementById("status-message-area");
      expect(messageArea.textContent).toBe("API Failed");
      expect(messageArea.className).toContain("message-error");
    });

    test("handles generic Error", async () => {
      const asyncFn = jest.fn().mockRejectedValue(new Error("Random Error"));

      await handleApiAction(button, asyncFn);

      const messageArea = document.getElementById("status-message-area");
      expect(messageArea.textContent).toBe("Random Error");
      expect(messageArea.className).toContain("message-error");
    });
  });
});
