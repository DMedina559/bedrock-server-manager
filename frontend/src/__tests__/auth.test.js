import { initializeLoginPage } from "../auth";
import { showStatusMessage } from "../utils";

// Mock utils
jest.mock("../utils", () => ({
  showStatusMessage: jest.fn(),
}));

// Mock fetch
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
Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("auth.js", () => {
  beforeAll(() => {
    // Attempt to clear window.location to simulate a clean environment,
    // though strict mode or JSDOM settings may prevent full deletion.
    try {
      delete window.location;
      window.location = { href: "", search: "" };
    } catch {
      // If deletion fails, tests will proceed but redirect assertions may be limited.
    }
  });

  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = `
      <form id="login-form">
        <input type="text" id="username" value="" />
        <input type="password" id="password" value="" />
        <button type="submit">Login</button>
      </form>
    `;
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("initializeLoginPage attaches submit listener", () => {
    const form = document.getElementById("login-form");
    const addEventListenerSpy = jest.spyOn(form, "addEventListener");

    initializeLoginPage();

    expect(addEventListenerSpy).toHaveBeenCalledWith(
      "submit",
      expect.any(Function),
    );
  });

  test("handles login success", async () => {
    initializeLoginPage();

    const form = document.getElementById("login-form");
    const usernameInput = document.getElementById("username");
    const passwordInput = document.getElementById("password");
    const button = form.querySelector("button");

    usernameInput.value = "admin";
    passwordInput.value = "password";

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ access_token: "fake-token", message: "Success" }),
    });

    // Suppress console.error if navigation fails in JSDOM
    const consoleErrorSpy = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});

    form.dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }),
    );

    // Wait for async operations
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(button.disabled).toBe(true);
    expect(showStatusMessage).toHaveBeenCalledWith(
      "Attempting login...",
      "info",
    );
    expect(fetch).toHaveBeenCalledWith("/auth/token", expect.any(Object));
    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      "jwt_token",
      "fake-token",
    );
    expect(showStatusMessage).toHaveBeenCalledWith("Success", "success");

    consoleErrorSpy.mockRestore();
  });

  test("handles login failure (invalid credentials)", async () => {
    initializeLoginPage();

    const form = document.getElementById("login-form");
    document.getElementById("username").value = "admin";
    document.getElementById("password").value = "wrong";

    fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: "Invalid credentials" }),
    });

    form.dispatchEvent(new Event("submit"));

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(showStatusMessage).toHaveBeenCalledWith(
      "Invalid credentials",
      "error",
    );
  });

  test("validates empty inputs", async () => {
    initializeLoginPage();
    const form = document.getElementById("login-form");

    // Empty username
    form.dispatchEvent(new Event("submit"));
    expect(showStatusMessage).toHaveBeenCalledWith(
      "Username is required.",
      "warning",
    );

    // Empty password
    document.getElementById("username").value = "user";
    form.dispatchEvent(new Event("submit"));
    expect(showStatusMessage).toHaveBeenCalledWith(
      "Password is required.",
      "warning",
    );

    expect(fetch).not.toHaveBeenCalled();
  });

  test("handles network error", async () => {
    initializeLoginPage();
    const form = document.getElementById("login-form");
    document.getElementById("username").value = "user";
    document.getElementById("password").value = "pass";

    fetch.mockRejectedValueOnce(new Error("Network fail"));

    form.dispatchEvent(new Event("submit"));

    await Promise.resolve();
    await Promise.resolve();

    expect(showStatusMessage).toHaveBeenCalledWith(
      expect.stringContaining("Network or processing error"),
      "error",
    );
  });
});
