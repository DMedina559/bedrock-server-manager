import { render, screen, fireEvent, waitFor } from "../test/utils";
import Account from "./Account";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as api from "../api";

vi.mock("../api");

describe("Account", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    api.get.mockImplementation((url) => {
      if (url === "/api/info/themes") {
        return Promise.resolve({
          themes: ["default", "dark", "light"],
        });
      }
      return Promise.resolve({});
    });

    api.post.mockResolvedValue({ status: "success" });
  });

  it("renders account info", async () => {
    // Auth context mock provides user.
    // However, customRender uses AuthProvider which fetches /api/account.
    api.request.mockResolvedValue({ username: "testuser", role: "admin" });

    render(<Account />);

    await waitFor(() => {
      // The header title is "My Account"
      expect(screen.getByText("My Account")).toBeInTheDocument();
    });
    // Check for theme selector (might need wait)
    // The theme section has an H2 "Theme"
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Theme" }),
      ).toBeInTheDocument();
    });
  });

  it("updates password", async () => {
    api.request.mockResolvedValue({ username: "testuser", role: "admin" });
    render(<Account />);

    await waitFor(() => {
      expect(screen.getByText("My Account")).toBeInTheDocument();
    });

    // Label association might be strict about id/for attribute which might be missing in component
    // Let's use getByLabelText with loose match or fallback to other selectors if needed
    // The error says "Found a label with the text of: New Password, however no form control was found associated to that label"
    // This implies the htmlFor attribute might be missing or mismatched.

    // In Account.jsx: <label ...>New Password</label><input ... />
    // If input is not nested or linked by ID, this fails.

    // Let's look for inputs by name attribute which seems safer given the DOM output
    // input name="new-password"

    // Wait, let's use `getByLabelText` generally works if nested.
    // The previous test failed because they are not nested and ID is likely used but maybe mismatched?

    // Let's inspect DOM dump from error:
    // <label class="form-label">New Password</label>
    // <input class="form-input" name="new-password" ... />

    // They are siblings in a div. No nesting, no 'for' attribute on label visible in dump (wait, let me check dump again).
    // <label class="form-label">New Password</label> -- NO FOR attribute.

    // So getByLabelText won't work.

    // Use container.querySelector or getByRole/Placeholder/DisplayValue.
    // Or finding input by name/type.

    // Since names are distinct:
    // Since we added ids and htmlFors in Account.jsx, getByLabelText should work now.
    // But let's be careful about exact label text.

    fireEvent.change(screen.getByLabelText("New Password"), {
      target: { value: "newpass" },
    });
    fireEvent.change(screen.getByLabelText("Confirm New Password"), {
      target: { value: "newpass" },
    });
    fireEvent.change(screen.getByLabelText("Current Password"), {
      target: { value: "oldpass" },
    });

    fireEvent.click(screen.getByText("Update Password"));

    // Account.jsx uses `/api/account/change-password` not `/api/account/password`
    // Let's check Account.jsx... "await post("/api/account/change-password", ..."
    // The previous run failed saying it was not called.
    // This could be because finding elements by selectors failed silently or incorrectly targeted previous elements?
    // No, if finding failed, it would throw.
    // So click happened.

    // Maybe validation failed?
    // Account.jsx: if (passwords.newPassword !== passwords.confirmPassword)
    // There is an SVG inside button. `getByText` finds the text node. Click bubbles to button. Should be fine.

    // Maybe `api.post` mock is not working as expected?
    // It's mocked in `beforeEach` with `mockResolvedValue({ status: "success" })`.

    // Let's check if the form submit handler is triggered.
    // The handler calls `e.preventDefault()`.

    // Account.jsx: `await post("/api/account/change-password", ...)`

    // Let's verify `current_password` is also set (it is required).
    // I missed setting current password in the test!
    // "Current Password" input is there.

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/account/change-password",
        expect.anything(),
      );
    });
  });
});
