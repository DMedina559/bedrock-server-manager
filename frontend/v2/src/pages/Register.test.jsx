import { render, screen, waitFor } from "../test/utils";
import Register from "./Register";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { Routes, Route } from "react-router-dom";

describe("Register", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("validates token on mount and renders form", async () => {
    // Mock validation
    globalThis.fetch.mockImplementation((url) => {
      if (url.includes("/setup/status"))
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: false }),
        });
      if (url === "/register/validate/valid-token")
        return Promise.resolve({ ok: true, json: async () => ({}) });
      return Promise.resolve({ ok: false });
    });

    window.history.pushState({}, "Test", "/register/valid-token");

    render(
      <Routes>
        <Route path="/register/:token" element={<Register />} />
      </Routes>,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Register" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
  });

  it("shows error for invalid token", async () => {
    globalThis.fetch.mockImplementation((url) => {
      if (url.includes("/setup/status"))
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: false }),
        });
      if (url === "/register/validate/invalid-token")
        return Promise.resolve({ ok: false });
      return Promise.resolve({ ok: false });
    });

    window.history.pushState({}, "Test", "/register/invalid-token");

    render(
      <Routes>
        <Route path="/register/:token" element={<Register />} />
      </Routes>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Invalid or expired registration link."),
      ).toBeInTheDocument();
    });
  });
});
