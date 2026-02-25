import { render, screen, fireEvent, waitFor } from "../test/utils";
import ServerConfig from "./ServerConfig";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("ServerConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("selectedServer", "TestServer");

    api.request.mockImplementation((url) => {
      if (url === "/api/servers")
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer" }],
        });
      return Promise.resolve({});
    });

    api.get.mockImplementation((url) => {
      if (url.includes("/settings")) {
        return Promise.resolve({
          status: "success",
          settings: {
            server_info: {
              installed_version: "1.0",
            },
            auto_backup: {
              enabled: true,
            },
          },
        });
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
    api.del.mockResolvedValue({ status: "success" });
  });

  it("renders configuration settings", async () => {
    render(<ServerConfig />);

    await waitFor(() => {
      expect(screen.getByText("server info")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("1.0")).toBeInTheDocument();
  });

  it("saves configuration", async () => {
    render(<ServerConfig />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("1.0")).toBeInTheDocument();
    });

    // Toggle boolean
    // Find the select for enabled.
    // Label is "enabled".
    const select = screen.getByLabelText("enabled");
    fireEvent.change(select, { target: { value: "false" } });

    const saveBtn = screen.getByText("Save Settings").closest("button");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalled();
    });
  });

  it("renders the delete button and handles deletion", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    confirmSpy.mockReturnValue(true);

    render(<ServerConfig />);

    // Wait for the delete button to be fully visible and rendered
    await waitFor(() => {
      const deleteText = screen.getByText("Delete Server");
      expect(deleteText).toBeInTheDocument();
      const deleteBtn = deleteText.closest("button");
      expect(deleteBtn).toBeInTheDocument();
      // Ensure the button isn't disabled (though logic says it shouldn't be)
      expect(deleteBtn).not.toBeDisabled();
    });

    // Use closest("button") to ensure we click the button element, not just the text node
    const deleteBtn = screen.getByText("Delete Server").closest("button");
    fireEvent.click(deleteBtn);

    // Wait for the confirmation dialog interaction
    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalledWith(
        expect.stringContaining("TestServer"),
      );
    });

    // Wait for the API call
    await waitFor(() => {
      expect(api.del).toHaveBeenCalledWith("/api/server/TestServer/delete");
    });

    confirmSpy.mockRestore();
  });
});
