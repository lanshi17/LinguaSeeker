import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAccountCacheScope } from "@/features/auth/hooks/useAuthAccount";
import { getAuthMe } from "@/features/auth/services/auth";
import type { AuthAccount } from "@/features/auth/types/auth";

vi.mock("@/features/auth/services/auth", () => ({
  getAuthMe: vi.fn(),
}));

const mockedGetAuthMe = vi.mocked(getAuthMe);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useAccountCacheScope", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not authorize cache reads until the account is verified", async () => {
    let resolveAccount: ((account: AuthAccount) => void) | undefined;
    mockedGetAuthMe.mockReturnValue(
      new Promise((resolve) => {
        resolveAccount = resolve;
      }),
    );
    const { result } = renderHook(() => useAccountCacheScope(), {
      wrapper: createWrapper(),
    });

    expect(result.current).toMatchObject({
      error: null,
      isReady: false,
      scope: "public",
    });

    await act(async () => {
      resolveAccount?.({
        authenticated: true,
        account_type: "user",
        user_id: "user-123",
        username: "curator",
        display_name: "Curator",
      });
    });

    await waitFor(() => {
      expect(result.current).toMatchObject({
        error: null,
        isReady: true,
        scope: "user-123",
      });
    });
  });

  it("keeps cache reads disabled when account verification fails", async () => {
    mockedGetAuthMe.mockRejectedValueOnce(new Error("auth unavailable"));
    const { result } = renderHook(() => useAccountCacheScope(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.error?.message).toBe("auth unavailable");
    });
    expect(result.current.isReady).toBe(false);
  });
});
