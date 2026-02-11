import { request, ApiError } from "../api";

// Mock fetch globally
global.fetch = jest.fn();
// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  clear: jest.fn(),
  removeItem: jest.fn(),
};
Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("api.js", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("request", () => {
    test("sends correct fetch request", async () => {
      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({ status: "success" }),
      });

      await request("/api/test");

      expect(fetch).toHaveBeenCalledWith(
        "/api/test",
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            Accept: "application/json",
          }),
        }),
      );
    });

    test("adds Authorization header if token exists", async () => {
      localStorageMock.getItem.mockReturnValue("fake-token");
      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({}),
      });

      await request("/api/test");

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer fake-token",
          }),
        }),
      );
    });

    test("handles JSON body correctly", async () => {
      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({}),
      });

      const body = { key: "value" };
      await request("/api/test", { method: "POST", body });

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
          body: JSON.stringify(body),
        }),
      );
    });

    test("handles 204 No Content", async () => {
      fetch.mockResolvedValue({
        ok: true,
        status: 204,
        headers: { get: () => null },
      });

      const result = await request("/api/test");
      expect(result).toBeNull();
    });

    test("throws ApiError on non-2xx status", async () => {
      fetch.mockResolvedValue({
        ok: false,
        status: 404,
        headers: { get: () => "application/json" },
        json: async () => ({ message: "Not Found" }),
      });

      // We need to test both properties.
      // Jest's toThrow checks the error message or class.
      // To check both, we can catch it manually or use multiple assertions on the same error object.

      try {
        await request("/api/test");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect(error.message).toBe("Not Found");
        expect(error.status).toBe(404);
      }
    });

    test("throws ApiError on application error status", async () => {
      fetch.mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: () => "application/json" },
        json: async () => ({ status: "error", message: "App Error" }),
      });

      try {
        await request("/api/test");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect(error.message).toBe("App Error");
      }
    });
  });
});
