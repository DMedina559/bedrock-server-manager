import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "./App";
import { BrowserRouter } from "react-router-dom";
import * as api from "./api";

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
    global.fetch = vi.fn();
  });

  it("renders loading state initially", () => {
    // Mock fetch to return pending promise or just be called
    global.fetch.mockImplementation(() => new Promise(() => {}));

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
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ needs_setup: true }),
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
