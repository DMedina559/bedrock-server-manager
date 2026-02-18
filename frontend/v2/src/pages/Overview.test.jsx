import { render, screen, fireEvent, waitFor } from "../test/utils";
import Overview from "./Overview";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("Overview", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock servers fetch
    api.request.mockImplementation((url) => {
      if (url === "/api/servers") {
        return Promise.resolve({
          status: "success",
          servers: [
            {
              name: "Server1",
              status: "stopped",
              version: "1.0",
              player_count: 0,
            },
            {
              name: "Server2",
              status: "running",
              version: "1.1",
              player_count: 5,
            },
          ],
        });
      }
      if (url === "/api/account")
        return Promise.resolve({ username: "admin", role: "admin" });
      return Promise.resolve({});
    });

    // Mock actions
    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders server list", async () => {
    render(<Overview />);
    await waitFor(() =>
      expect(screen.getByText("Server1")).toBeInTheDocument(),
    );
    expect(screen.getByText("Server2")).toBeInTheDocument();
    expect(screen.getByText("STOPPED")).toBeInTheDocument();
    expect(screen.getByText("RUNNING")).toBeInTheDocument();
  });

  it("handles start action", async () => {
    render(<Overview />);
    await waitFor(() =>
      expect(screen.getByText("Server1")).toBeInTheDocument(),
    );

    const startBtns = screen.getAllByTitle("Start Server");
    // Server1 is first (Server1)
    const btn = startBtns[0];
    fireEvent.click(btn);

    // api.post params: url, body, options
    // handleAction calls post(`/api/server/${serverName}/${action}`)
    // post helper: post(url, body, options)
    // If body is undefined, it might pass undefined.
    // Overview.jsx calls post with 1 argument.
    expect(api.post).toHaveBeenCalledWith("/api/server/Server1/start");
  });
});
