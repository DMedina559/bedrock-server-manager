import { render, screen, fireEvent, waitFor } from "../test/utils";
import Backups from "./Backups";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("Backups", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("selectedServer", "TestServer");

    // Need to mock ServerContext requirements too
    api.request.mockImplementation((url) => {
      if (url === "/api/servers")
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer" }],
        });
      return Promise.resolve({});
    });

    api.get.mockImplementation((url) => {
      if (url.includes("/backup/list/all")) {
        return Promise.resolve({
          status: "success",
          details: {
            all_backups: {
              world_backups: ["world_backup_1.zip"],
              properties_backups: [],
              allowlist_backups: [],
              permissions_backups: [],
            },
          },
        });
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders backup lists", async () => {
    render(<Backups />);

    await waitFor(() => {
      expect(screen.getByText("World Backups")).toBeInTheDocument();
    });
    expect(await screen.findByText("world_backup_1.zip")).toBeInTheDocument();
  });

  it("handles create backup", async () => {
    render(<Backups />);

    // Wait for load
    await waitFor(() => {
      expect(screen.getByText("World Backups")).toBeInTheDocument();
    });

    vi.spyOn(window, "confirm").mockReturnValue(true);

    // Using getAllByText because "New World Backup" might appear or similar
    const createBtn = screen
      .getByRole("button", { name: /New World Backup/i })
      .closest("button");
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/server/TestServer/backup/action",
        expect.objectContaining({ backup_type: "world" }),
      );
    });
  });

  it("handles restore backup", async () => {
    render(<Backups />);

    expect(await screen.findByText("world_backup_1.zip")).toBeInTheDocument();

    vi.spyOn(window, "confirm").mockReturnValue(true);

    const restoreBtn = screen.getAllByTitle("Restore")[0];
    fireEvent.click(restoreBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        expect.stringContaining("/restore/action"),
        expect.objectContaining({
          restore_type: "world",
          backup_file: "world_backup_1.zip",
        }),
      );
    });
  });
});
