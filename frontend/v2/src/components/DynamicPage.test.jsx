import { render, screen, fireEvent, waitFor } from "../test/utils";
import DynamicPage from "../components/DynamicPage";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("DynamicPage", () => {
  let fetchSpy;

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock global fetch for download test
    fetchSpy = vi.spyOn(window, "fetch").mockImplementation(() =>
      Promise.resolve({
        ok: true,
        blob: () =>
          Promise.resolve(new Blob(["content"], { type: "text/plain" })),
      }),
    );

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
});
