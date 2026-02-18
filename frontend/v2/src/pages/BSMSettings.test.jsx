import { render, screen, fireEvent, waitFor } from "../test/utils";
import BSMSettings from "./BSMSettings";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("BSMSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    api.get.mockImplementation((url) => {
      if (url === "/api/settings") {
        return Promise.resolve({
          status: "success",
          settings: {
            server: {
              name: "Bedrock Server",
              port: 19132,
            },
            advanced: {
              debug: false,
            },
          },
        });
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders settings form", async () => {
    render(<BSMSettings />);

    await waitFor(() => {
      expect(screen.getByText("Global Settings")).toBeInTheDocument();
    });
    // Section headers
    expect(screen.getByText("server")).toBeInTheDocument();
    // Inputs
    expect(screen.getByDisplayValue("Bedrock Server")).toBeInTheDocument();
    expect(screen.getByDisplayValue("19132")).toBeInTheDocument();
  });

  it("saves settings", async () => {
    render(<BSMSettings />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Bedrock Server")).toBeInTheDocument();
    });

    const nameInput = screen.getByDisplayValue("Bedrock Server");
    fireEvent.change(nameInput, { target: { value: "New Name" } });

    const saveBtn = screen.getByText("Save Changes").closest("button");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/settings",
        expect.objectContaining({ key: "server.name", value: "New Name" }),
      );
    });
  });
});
