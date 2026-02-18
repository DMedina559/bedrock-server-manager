import { render, screen, fireEvent, waitFor } from "../test/utils";
import ServerProperties from "./ServerProperties";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("ServerProperties", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("selectedServer", "TestServer");

    // Default mocks
    api.request.mockImplementation((url) => {
      if (url === "/api/servers") {
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer", status: "stopped" }],
        });
      }
      return Promise.resolve({});
    });

    api.get.mockImplementation((url) => {
      if (url.includes("/properties/get")) {
        return Promise.resolve({
          status: "success",
          properties: {
            "server-name": "My Server",
            "max-players": "10",
            "allow-cheats": "false",
          },
        });
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders properties form", async () => {
    render(<ServerProperties />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("My Server")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("10")).toBeInTheDocument();
  });

  it("saves changes", async () => {
    render(<ServerProperties />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("My Server")).toBeInTheDocument();
    });

    const nameInput = screen.getByDisplayValue("My Server");
    fireEvent.change(nameInput, { target: { value: "New Name" } });

    const saveBtns = screen.getAllByText("Save Changes");

    fireEvent.click(saveBtns[0]);

    await waitFor(
      () => {
        expect(api.post).toHaveBeenCalledWith(
          "/api/server/TestServer/properties/set",
          expect.objectContaining({
            properties: expect.objectContaining({
              "server-name": "New Name",
            }),
          }),
        );
      },
      { timeout: 3000 },
    );
  });

  it("adds custom property", async () => {
    render(<ServerProperties />);

    await waitFor(() => {
      expect(screen.getByText("Add Custom Property")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("e.g. max-threads"), {
      target: { value: "my-custom-prop" },
    });
    fireEvent.change(screen.getByPlaceholderText("Value"), {
      target: { value: "123" },
    });

    fireEvent.click(screen.getByText("Add Property"));

    expect(screen.getByText(/Added property 'my-custom-prop'/)).toBeVisible();
  });
});
