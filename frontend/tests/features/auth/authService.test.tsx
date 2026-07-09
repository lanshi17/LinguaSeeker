import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import { getAuthMe, login, logout } from "@/features/auth/services/auth";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedClient = vi.mocked(apiClient);

describe("auth service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the current account from /auth/me", async () => {
    mockedClient.get.mockResolvedValueOnce({
      data: {
        authenticated: false,
        account_type: "public",
        user_id: null,
        username: null,
        display_name: "Public account",
      },
    });

    await expect(getAuthMe()).resolves.toMatchObject({
      account_type: "public",
      user_id: null,
    });
    expect(mockedClient.get).toHaveBeenCalledWith("/auth/me");
  });

  it("posts username credentials for login", async () => {
    mockedClient.post.mockResolvedValue({ data: { success: true, account: {} } });

    await login({ username: "alice", password: "password123" });

    expect(mockedClient.post).toHaveBeenCalledWith("/auth/login", {
      username: "alice",
      password: "password123",
    });
  });

  it("posts logout without a request body", async () => {
    mockedClient.post.mockResolvedValueOnce({ data: { success: true } });

    await expect(logout()).resolves.toEqual({ success: true });
    expect(mockedClient.post).toHaveBeenCalledWith("/auth/logout");
  });
});
