import { useQuery, type QueryClient } from "@tanstack/react-query";
import { getAuthMe } from "../services/auth";
import type { AuthAccount } from "../types/auth";

export const authMeQueryKey = ["auth", "me"] as const;

export const PUBLIC_ACCOUNT: AuthAccount = {
  authenticated: false,
  account_type: "public",
  user_id: null,
  username: null,
  display_name: "Public account",
};

export function useAuthAccount() {
  return useQuery({
    queryKey: authMeQueryKey,
    queryFn: getAuthMe,
    initialData: PUBLIC_ACCOUNT,
    staleTime: 15_000,
  });
}

export function resetAccountScopedQueries(
  queryClient: QueryClient,
  account: AuthAccount,
): void {
  queryClient.clear();
  queryClient.setQueryData(authMeQueryKey, account);
}
