import { render, screen, fireEvent, waitFor } from "../test/utils";
import AccessControl from "./AccessControl";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("AccessControl", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("selectedServer", "TestServer");

    api.request.mockImplementation((url) => {
      if (url === "/api/servers")
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer" }],
        });
      if (url === "/api/account")
        return Promise.resolve({ username: "admin", role: "admin" });
      return Promise.resolve({});
    });

    api.get.mockImplementation((url) => {
      if (url.includes("/allowlist/get")) {
        return Promise.resolve({
          status: "success",
          players: [{ name: "Player1", ignoresPlayerLimit: false }],
        });
      }
      if (url.includes("/permissions/get")) {
        return Promise.resolve({
          status: "success",
          data: {
            permissions: [
              { xuid: "123", name: "AdminPlayer", permission: "operator" },
            ],
          },
        });
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders allowlist", async () => {
    render(<AccessControl />);

    await waitFor(() => {
      expect(screen.getByText("Player1")).toBeInTheDocument();
    });
  });

  it("switches to permissions tab", async () => {
    render(<AccessControl />);

    await waitFor(() => {
      expect(screen.getByText("Player1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Permissions"));

    await waitFor(() => {
      expect(screen.getByText("AdminPlayer")).toBeInTheDocument();
    });
  });

  it("adds player to allowlist", async () => {
    render(<AccessControl />);

    await waitFor(() => {
      expect(screen.getByText("Player1")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Enter Gamertag to allow...");
    fireEvent.change(input, { target: { value: "NewPlayer" } });

    fireEvent.click(screen.getByText("Add"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        expect.stringContaining("/allowlist/add"),
        expect.anything(),
      );
    });
  });
});
