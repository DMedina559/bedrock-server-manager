import { render, screen } from "../test/utils";
import SidebarLabel from "./SidebarLabel";
import { describe, it, expect } from "vitest";

describe("SidebarLabel", () => {
  it("renders children text", () => {
    render(<SidebarLabel>Test Label</SidebarLabel>);
    expect(screen.getByText("Test Label")).toBeInTheDocument();
  });
});
