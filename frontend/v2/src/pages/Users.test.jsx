import { render, screen, fireEvent, waitFor } from "../test/utils";
import Users from "./Users";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("Users", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.request.mockResolvedValue({ username: "admin", role: "admin", id: 1 });

    api.get.mockImplementation((url) => {
      if (url === "/users/list") {
        return Promise.resolve([
          { id: 1, username: "admin", role: "admin", is_active: true },
          { id: 2, username: "user1", role: "user", is_active: true },
        ]);
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders user list", async () => {
    render(<Users />);

    // Wait for header to appear to ensure component mounted
    await waitFor(() => {
      expect(screen.getByText("User Management")).toBeInTheDocument();
    });

    // Check for users
    await waitFor(() => {
      // Use getAll because admin appears as text and maybe in table
      expect(screen.getAllByText("admin")[0]).toBeInTheDocument();
    });
    expect(screen.getByText("user1")).toBeInTheDocument();
  });

  it("handles invite user", async () => {
    render(<Users />);

    await waitFor(() => {
      expect(screen.getAllByText("admin")[0]).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Invite User"));

    await waitFor(() => {
      expect(screen.getByText("Generate Link")).toBeInTheDocument();
    });

    // Mock invite response
    api.post.mockResolvedValueOnce({
      redirect_url: "http://test/register/123",
    });

    fireEvent.click(screen.getByText("Generate Link"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/register/generate-token",
        expect.anything(),
      );
    });
  });
});
