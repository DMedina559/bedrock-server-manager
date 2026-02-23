import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import ServerProperties from "./ServerProperties";
import * as api from "../api";
import { BrowserRouter } from "react-router-dom";
import { ToastProvider } from "../ToastContext";
import { ServerContext } from "../ServerContext";

// Mock the useServer hook
vi.mock("../ServerContext", () => ({
  useServer: vi.fn(),
  ServerProvider: ({ children }) => <div>{children}</div>,
}));

import { useServer } from "../ServerContext";

// Mock API
vi.mock("../api", () => ({
  get: vi.fn(),
  post: vi.fn(),
  request: vi.fn(),
}));

const renderWithProviders = (ui) => {
  return render(
    <BrowserRouter>
      <ToastProvider>{ui}</ToastProvider>
    </BrowserRouter>,
  );
};

describe("ServerProperties", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useServer return value
    useServer.mockReturnValue({
      selectedServer: "TestServer",
      servers: [{ name: "TestServer", status: "stopped" }],
    });

    // Mock API responses
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

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders properties form and saves changes", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ServerProperties />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByDisplayValue("My Server")).toBeInTheDocument();
    });

    const nameInput = screen.getByDisplayValue("My Server");

    // Clear and type new name
    await user.clear(nameInput);
    await user.type(nameInput, "New Name");

    expect(nameInput).toHaveValue("New Name");

    // Find Save Changes button
    const saveButtons = screen.getAllByText("Save Changes");
    const saveButton = saveButtons[0];

    expect(saveButton).toBeEnabled();

    await user.click(saveButton);

    // Verify API call
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        expect.stringContaining("/properties/set"),
        expect.objectContaining({
          properties: expect.objectContaining({
            "server-name": "New Name",
          }),
        }),
      );
    });
  });
});
