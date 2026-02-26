import { initializeLoginPage } from "../auth";
import { login } from "../auth_api";
import { handleApiAction } from "../ui_utils";

// Mock dependencies
jest.mock("../auth_api");
jest.mock("../ui_utils");

describe("auth.js", () => {
  let loginForm, loginButton;

  beforeEach(() => {
    jest.clearAllMocks();
    document.body.innerHTML = `
      <form id="login-form">
        <input id="username" value="testuser" />
        <input id="password" value="testpass" />
        <button type="submit">Login</button>
      </form>
    `;
    loginForm = document.getElementById("login-form");
    loginButton = loginForm.querySelector("button");
  });

  test("calls login API on submit", async () => {
    initializeLoginPage();

    loginForm.dispatchEvent(new Event("submit"));

    expect(handleApiAction).toHaveBeenCalledWith(
      loginButton,
      expect.any(Function),
      "Attempting login...",
    );

    // Simulate the callback
    const callback = handleApiAction.mock.calls[0][1];
    await callback();

    expect(login).toHaveBeenCalledWith(expect.any(FormData));
  });

  test("handles successful login", async () => {
    initializeLoginPage();

    // Mock successful login response
    login.mockResolvedValue({ access_token: "fake-token" });

    const setItemSpy = jest.spyOn(Storage.prototype, "setItem");

    loginForm.dispatchEvent(new Event("submit"));
    const callback = handleApiAction.mock.calls[0][1];
    await callback();

    expect(setItemSpy).toHaveBeenCalledWith("jwt_token", "fake-token");
  });
});
