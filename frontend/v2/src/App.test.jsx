import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "./App";
import { BrowserRouter } from "react-router-dom";

// Mock the API module
vi.mock("./api", () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  request: vi.fn(),
}));

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn();
  });

  it("renders loading state initially", () => {
    // Mock fetch to return pending promise or just be called
    globalThis.fetch.mockImplementation(() => new Promise(() => {}));

    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );

    // It should show "Loading..."
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("redirects to setup if setup is needed", async () => {
    // Mock setup status
    globalThis.fetch.mockImplementation((url) => {
      if (url === "/setup/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: true }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });

    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );

    await waitFor(() => {
      // App redirects to /setup, Setup component renders
      // Setup component has "Setup Bedrock Server Manager"
      expect(
        screen.getByText("Setup Bedrock Server Manager"),
      ).toBeInTheDocument();
    });
  });
});
