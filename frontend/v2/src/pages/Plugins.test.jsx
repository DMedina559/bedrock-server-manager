import { render, screen, fireEvent, waitFor } from "../test/utils";
import Plugins from "./Plugins";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("Plugins", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    api.get.mockImplementation((url) => {
      if (url === "/api/plugins") {
        return Promise.resolve({
          status: "success",
          data: {
            "Test Plugin": {
              version: "1.0",
              author: "Tester",
              description: "A test plugin",
              enabled: true,
            },
          },
        });
      }
      return Promise.resolve({});
    });

    api.put.mockResolvedValue({ status: "success" });
    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders plugin list", async () => {
    render(<Plugins />);

    await waitFor(() => {
      expect(screen.getByText("Test Plugin")).toBeInTheDocument();
    });
    expect(screen.getByText("v1.0")).toBeInTheDocument();
  });

  it("toggles plugin", async () => {
    render(<Plugins />);

    await waitFor(() => {
      expect(screen.getByText("Test Plugin")).toBeInTheDocument();
    });

    const toggleBtn = screen.getByTitle("Disable");
    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/plugins/Test Plugin",
        expect.objectContaining({ enabled: false }),
      );
    });
  });
});
