import { render, screen, fireEvent, waitFor } from "../test/utils";
import Setup from "./Setup";
import { vi, describe, it, expect, beforeEach } from "vitest";

describe("Setup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
  });

  it("renders setup form", async () => {
    render(<Setup />);
    await waitFor(() => {
      expect(
        screen.getByText("Setup Bedrock Server Manager"),
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/Username/i)).toBeInTheDocument();
  });

  it("handles successful setup", async () => {
    globalThis.fetch.mockImplementation((url) => {
      if (url === "/setup/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: true }),
        });
      }
      if (url === "/setup/create-first-user") {
        return Promise.resolve({
          ok: true,
          json: async () => ({}),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });

    render(<Setup />);

    fireEvent.change(screen.getByLabelText(/Username/i), {
      target: { value: "admin" },
    });
    // Use precise regex for password
    fireEvent.change(screen.getByLabelText(/^Password$/i), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText(/^Confirm Password$/i), {
      target: { value: "password123" },
    });

    const submitBtn = screen.getByRole("button", { name: /Create Account/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/setup/create-first-user",
        expect.anything(),
      );
    });
  });
});
