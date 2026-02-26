import { render, screen, fireEvent, waitFor } from "../test/utils";
import DynamicPage from "../components/DynamicPage";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("DynamicPage", () => {
  let fetchSpy;

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock global fetch for download test and setup status
    fetchSpy = vi.spyOn(window, "fetch").mockImplementation((url) => {
      if (url === "/setup/status") {
        return Promise.resolve({
          ok: true,
          json: async () => ({ needs_setup: false }),
        });
      }
      // Handle download test case
      if (url === "/api/download/file.txt") {
        return Promise.resolve({
          ok: true,
          blob: () =>
            Promise.resolve(new Blob(["content"], { type: "text/plain" })),
        });
      }
      // WebSocket or other calls
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({}),
      });
    });

    // Mock window URL methods
    window.URL.createObjectURL = vi.fn(() => "blob:test");
    window.URL.revokeObjectURL = vi.fn();

    api.get.mockImplementation((url) => {
      if (url === "/api/test/native") {
        return Promise.resolve([
          {
            type: "Input",
            props: { id: "testInput", placeholder: "Enter text" },
          },
          {
            type: "Button",
            props: {
              label: "Submit",
              onClickAction: {
                type: "api_call",
                endpoint: "/api/test/submit",
                includeFormState: true,
              },
            },
          },
        ]);
      }
      if (url === "/api/test/upload") {
        return Promise.resolve([
          {
            type: "FileUpload",
            props: { id: "fileInput", accept: ".txt" },
          },
          {
            type: "Button",
            props: {
              label: "Upload",
              onClickAction: {
                type: "api_call",
                endpoint: "/api/upload",
                includeFormState: true,
              },
            },
          },
        ]);
      }
      if (url === "/api/test/download") {
        return Promise.resolve([
          {
            type: "FileDownload",
            props: {
              label: "Download Me",
              endpoint: "/api/download/file.txt",
              filename: "file.txt",
            },
          },
        ]);
      }
      if (url === "/api/test/components") {
        return Promise.resolve([
          {
            type: "Switch",
            props: { id: "switchInput", label: "Toggle Me" },
          },
          {
            type: "Checkbox",
            props: { id: "checkboxInput", label: "Check Me" },
          },
          {
            type: "Button",
            props: {
              label: "Open Modal",
              onClickAction: { type: "open_modal", modalId: "testModal" },
            },
          },
          {
            type: "Modal",
            props: { id: "testModal", title: "Test Modal" },
            children: [
              { type: "Text", props: { content: "Inside Modal" } },
              {
                type: "Button",
                props: {
                  label: "Close Modal",
                  onClickAction: { type: "close_modal" },
                },
              },
            ],
          },
          {
            type: "Button",
            props: {
              label: "Submit Form",
              onClickAction: {
                type: "api_call",
                endpoint: "/api/submit-components",
                includeFormState: true,
              },
            },
          },
        ]);
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders from schema and handles text input", async () => {
    window.history.pushState(
      {},
      "Test",
      "/plugin-native-view?url=/api/test/native",
    );
    render(<DynamicPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Enter text")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Enter text"), {
      target: { value: "test value" },
    });

    fireEvent.click(screen.getByText("Submit"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/test/submit",
        expect.objectContaining({ testInput: "test value" }),
      );
    });
  });

  it("handles file upload using FormData", async () => {
    window.history.pushState(
      {},
      "Test",
      "/plugin-native-view?url=/api/test/upload",
    );
    render(<DynamicPage />);

    await waitFor(() => {
      // Find file input
      expect(document.querySelector('input[type="file"]')).toBeInTheDocument();
    });

    const fileInput = document.querySelector('input[type="file"]');
    const file = new File(["hello"], "hello.txt", { type: "text/plain" });

    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByText("Upload"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalled();
      const [endpoint, body] = api.post.mock.calls[0];
      expect(endpoint).toBe("/api/upload");
      expect(body).toBeInstanceOf(FormData);
      expect(body.get("fileInput")).toEqual(file);
    });
  });

  it("handles file download", async () => {
    window.history.pushState(
      {},
      "Test",
      "/plugin-native-view?url=/api/test/download",
    );
    render(<DynamicPage />);

    await waitFor(() => {
      expect(screen.getByText("Download Me")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Download Me"));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/download/file.txt",
        expect.any(Object),
      );
      expect(window.URL.createObjectURL).toHaveBeenCalled();
    });
  });

  it("renders new components and handles modal interaction", async () => {
    window.history.pushState(
      {},
      "Test Components",
      "/plugin-native-view?url=/api/test/components",
    );
    render(<DynamicPage />);

    // Verify Switch and Checkbox render
    await waitFor(() => {
      expect(screen.getByText("Toggle Me")).toBeInTheDocument();
      expect(screen.getByText("Check Me")).toBeInTheDocument();
    });

    // Interact with Switch and Checkbox
    // We query by checkbox type
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBe(2); // One switch, one checkbox

    // Toggle them
    fireEvent.click(checkboxes[0]); // Switch
    fireEvent.click(checkboxes[1]); // Checkbox

    // Open Modal
    fireEvent.click(screen.getByText("Open Modal"));

    await waitFor(() => {
      expect(screen.getByText("Test Modal")).toBeInTheDocument();
      expect(screen.getByText("Inside Modal")).toBeInTheDocument();
    });

    // Close Modal
    fireEvent.click(screen.getByText("Close Modal"));

    await waitFor(() => {
      expect(screen.queryByText("Inside Modal")).not.toBeInTheDocument();
    });

    // Submit form to verify state
    fireEvent.click(screen.getByText("Submit Form"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/submit-components",
        expect.objectContaining({
          switchInput: true,
          checkboxInput: true,
        }),
      );
    });
  });
});
