import { render, screen, waitFor, fireEvent } from "../test/utils";
import Sidebar from "./Sidebar";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock global fetch for setup status and auth
    globalThis.fetch.mockImplementation((url) => {
      if (url === "/setup/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: false }),
        });
      }
      if (url === "/auth/logout") {
        return Promise.resolve({
          ok: true,
        });
      }
      // WebSocket token refresh or other calls
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });

    // Default mocks
    api.request.mockImplementation((url) => {
      if (url === "/api/account")
        return Promise.resolve({ username: "testuser", role: "admin" });
      if (url === "/api/servers")
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer", status: "stopped" }],
        });
      return Promise.resolve({});
    });

    api.get.mockImplementation((url) => {
      if (url === "/api/plugins/pages")
        return Promise.resolve({ status: "success", data: [] });
      if (url === "/api/info")
        return Promise.resolve({
          status: "success",
          info: { splash_text: "Splash!" },
        });
      // Fallback for context calls if they use get
      if (url === "/api/account")
        return Promise.resolve({ username: "testuser", role: "admin" });
      if (url === "/api/servers")
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer", status: "stopped" }],
        });
      return Promise.resolve({});
    });
  });

  it("renders navigation items", async () => {
    render(<Sidebar />);

    // Wait for user and servers to load (splash text is a good indicator or overview link)
    await waitFor(() => {
      expect(screen.getByText("Overview")).toBeInTheDocument();
    });

    expect(screen.getByText("Monitor")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    // Admin item
    expect(screen.getByText("Install Server")).toBeInTheDocument();
  });

  it("displays splash text", async () => {
    render(<Sidebar />);
    await waitFor(() => {
      expect(screen.getByText("Splash!")).toBeInTheDocument();
    });
  });

  it("handles server selection", async () => {
    render(<Sidebar />);

    await waitFor(() => {
      // Find select
      const select = screen.getByRole("combobox");
      expect(select).toBeInTheDocument();
      // Wait for options
      expect(screen.getByText("TestServer")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "TestServer" } });

    await waitFor(() => {
      expect(select.value).toBe("TestServer");
    });
  });

  it("toggles collapse state", async () => {
    render(<Sidebar />);
    await waitFor(() =>
      expect(screen.getByText("Overview")).toBeInTheDocument(),
    );

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse Sidebar",
    });
    fireEvent.click(collapseBtn);

    await waitFor(() => {
      expect(screen.queryByText("Overview")).not.toBeInTheDocument();
    });

    const expandBtn = screen.getByRole("button", { name: "Expand Sidebar" });
    fireEvent.click(expandBtn);

    await waitFor(() => {
      expect(screen.getByText("Overview")).toBeInTheDocument();
    });
  });

  it("calls logout on click", async () => {
    render(<Sidebar />);
    await waitFor(() => expect(screen.getByText("Logout")).toBeInTheDocument());

    const logoutBtn = screen.getByText("Logout").closest("button");
    fireEvent.click(logoutBtn);

    // Expect fetch to be called with /auth/logout
    expect(globalThis.fetch).toHaveBeenCalledWith("/auth/logout");
  });

  it("highlights the active plugin page based on URL", async () => {
    // Override mock for this test
    api.get.mockImplementation((url) => {
      if (url === "/api/plugins/pages")
        return Promise.resolve({
          status: "success",
          data: [
            { name: "Plugin A", path: "/plugin/a", type: "native" },
            { name: "Plugin B", path: "/plugin/b", type: "native" },
          ],
        });
      // Existing fallback
      if (url === "/api/info")
        return Promise.resolve({
          status: "success",
          info: { splash_text: "Splash!" },
        });
      if (url === "/api/account")
        return Promise.resolve({ username: "testuser", role: "admin" });
      if (url === "/api/servers")
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer", status: "stopped" }],
        });
      return Promise.resolve({});
    });

    // Simulate navigation to Plugin A
    window.history.pushState({}, "", "/plugin-native-view?url=%2Fplugin%2Fa");

    render(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText("Plugin A")).toBeInTheDocument();
      expect(screen.getByText("Plugin B")).toBeInTheDocument();
    });

    // Plugin A link should be active
    const linkA = screen.getByText("Plugin A").closest("a");
    expect(linkA).toHaveClass("active");

    // Plugin B link should NOT be active
    const linkB = screen.getByText("Plugin B").closest("a");
    expect(linkB).not.toHaveClass("active");
  });
});
