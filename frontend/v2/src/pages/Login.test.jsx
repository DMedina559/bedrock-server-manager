import { render, screen, fireEvent, waitFor } from "../test/utils";
import Login from "./Login";
import { vi, describe, it, expect, beforeEach } from "vitest";

describe("Login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default fetch mock (success setup status)
    globalThis.fetch.mockImplementation((url) => {
      if (url === "/setup/status")
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: false }),
        });
      if (url === "/api/account") return Promise.reject({ status: 401 }); // Initially not logged in
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it("renders login form", async () => {
    render(<Login />);
    await waitFor(() =>
      expect(screen.getByLabelText(/Username/i)).toBeInTheDocument(),
    );
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Sign In/i }),
    ).toBeInTheDocument();
  });

  it("handles successful login", async () => {
    // Mock successful login response
    globalThis.fetch.mockImplementation((url) => {
      if (url === "/setup/status")
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: false }),
        });
      // After login, checkUser is called which calls /api/account
      if (url === "/api/account")
        return Promise.resolve({
          ok: true,
          json: async () => ({ username: "testuser" }),
        }); // Use fetch response structure because request calls fetch? No request calls fetch.
      // Wait, api.js request calls fetch. If we mock global fetch, request uses it.
      // But /api/account should return JSON matching backend.
      // api.js expects response.json().

      if (url === "/auth/token")
        return Promise.resolve({
          ok: true,
          json: async () => ({ access_token: "fake-token" }),
        });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    render(<Login />);

    fireEvent.change(screen.getByLabelText(/Username/i), {
      target: { value: "user" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign In/i }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/auth/token",
        expect.anything(),
      );
    });
  });

  it("handles login failure", async () => {
    globalThis.fetch.mockImplementation((url) => {
      if (url === "/setup/status")
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: false }),
        });
      if (url === "/api/account") return Promise.reject({ status: 401 });
      if (url === "/auth/token")
        return Promise.resolve({ ok: false, status: 401 });
      return Promise.resolve({ ok: true });
    });

    render(<Login />);

    fireEvent.change(screen.getByLabelText(/Username/i), {
      target: { value: "user" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign In/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Invalid username or password"),
      ).toBeInTheDocument();
    });
  });
});
