import { render, screen, waitFor } from "../test/utils";
import Monitor from "./Monitor";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

// Mock Recharts to avoid complex SVG rendering issues
vi.mock("recharts", async () => {
  const OriginalModule = await vi.importActual("recharts");
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }) => (
      <div className="recharts-responsive-container">{children}</div>
    ),
    AreaChart: () => <div data-testid="area-chart" />,
    Area: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
  };
});

describe("Monitor", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mocks
    api.request.mockImplementation((url) => {
      if (url === "/api/servers") {
        return Promise.resolve({
          status: "success",
          servers: [{ name: "TestServer", status: "running" }],
        });
      }
      if (url === "/api/account")
        return Promise.resolve({ username: "admin", role: "admin" });
      return Promise.resolve({});
    });

    api.get.mockImplementation((url) => {
      if (url.includes("/process_info")) {
        return Promise.resolve({
          status: "success",
          data: {
            process_info: {
              pid: 12345,
              uptime: "1h 30m",
              cpu_percent: 10.5,
              memory_mb: 2048,
            },
          },
        });
      }
      return Promise.resolve({});
    });
  });

  it("renders monitor dashboard", async () => {
    // Mock the useServer hook to return a selected server
    // Since we are mocking api.js but using ServerContext which calls it,
    // we need to ensure ServerProvider initializes with a selected server or we mock localStorage.
    localStorage.setItem("selectedServer", "TestServer");

    render(<Monitor />);

    await waitFor(() => {
      expect(
        screen.getByText("Server Monitor: TestServer"),
      ).toBeInTheDocument();
    });

    // Check for stats
    await waitFor(() => {
      expect(screen.getByText("Process Status")).toBeInTheDocument();
    });

    // Check console
    await waitFor(() => {
      expect(screen.getByText("Waiting for logs...")).toBeInTheDocument();
    });
  });
});
