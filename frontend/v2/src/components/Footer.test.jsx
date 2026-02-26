import { render, screen, waitFor } from "../test/utils";
import Footer from "./Footer";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("Footer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ needs_setup: false }),
    });
  });

  it("renders app version after fetching", async () => {
    api.get.mockResolvedValue({
      status: "success",
      info: { app_version: "1.2.3" },
    });

    render(<Footer />);

    await waitFor(() => {
      expect(screen.getByText(/1.2.3/)).toBeInTheDocument();
    });
    expect(screen.getByText(/MIT 2025-2026/)).toBeInTheDocument();
  });

  it("handles fetch error gracefully", async () => {
    api.get.mockRejectedValue(new Error("Failed"));

    render(<Footer />);

    // Should remain "Unknown"
    expect(screen.getByText(/Unknown/)).toBeInTheDocument();
  });
});
