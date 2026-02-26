import { render, screen, waitFor } from "../test/utils";
import PluginViewer from "./PluginViewer";
import { describe, it, expect } from "vitest";
import { Routes, Route } from "react-router-dom";

describe("PluginViewer", () => {
  it("renders iframe with url", async () => {
    window.history.pushState({}, "Test", "/plugin-view?url=http://example.com");

    render(
      <Routes>
        <Route path="/plugin-view" element={<PluginViewer />} />
      </Routes>,
    );

    await waitFor(() => {
      expect(screen.getByTitle("Plugin Content")).toBeInTheDocument();
    });
    expect(screen.getByTitle("Plugin Content")).toHaveAttribute(
      "src",
      "http://example.com",
    );
  });

  it("shows error if no url", () => {
    window.history.pushState({}, "Test", "/plugin-view");

    render(
      <Routes>
        <Route path="/plugin-view" element={<PluginViewer />} />
      </Routes>,
    );

    expect(screen.getByText("No plugin URL provided.")).toBeInTheDocument();
  });
});
