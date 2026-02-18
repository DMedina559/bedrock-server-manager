import { render, screen, fireEvent, waitFor } from "../test/utils";
import ServerInstall from "./ServerInstall";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("ServerInstall", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Admin user required for this page usually
    api.request.mockResolvedValue({ username: "admin", role: "admin" });
    api.get.mockImplementation((url) => {
      if (url === "/api/downloads/list") {
        return Promise.resolve({
          status: "success",
          custom_zips: ["custom.zip"],
        });
      }
      return Promise.resolve({});
    });
    api.post.mockResolvedValue({ status: "success", task_id: 123 });
  });

  it("renders installation form", async () => {
    render(<ServerInstall />);
    expect(screen.getByText("Install New Server")).toBeInTheDocument();
    expect(screen.getByLabelText("Server Name")).toBeInTheDocument();
  });

  it("handles installation submission", async () => {
    render(<ServerInstall />);

    fireEvent.change(screen.getByLabelText("Server Name"), {
      target: { value: "NewServer" },
    });

    const installBtn = screen.getByRole("button", { name: /Install Server/i });
    fireEvent.click(installBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/server/install",
        expect.objectContaining({ server_name: "NewServer" }),
      );
    });
  });
});
