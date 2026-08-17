import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchLocalMe,
  isLocalAuthEnabled,
  localLogin,
  localLogout,
  type LocalAuthUser,
} from "#/api/local-auth/client";

export const LOCAL_AUTH_QUERY_KEY = ["local-auth", "me"] as const;

function clearUserScopedCaches(qc: ReturnType<typeof useQueryClient>) {
  // Avoid leaking conversations/settings between users on the same browser.
  qc.clear();
}

export function useLocalAuthUser() {
  const enabled = isLocalAuthEnabled();
  return useQuery({
    queryKey: LOCAL_AUTH_QUERY_KEY,
    queryFn: fetchLocalMe,
    enabled,
    retry: false,
    staleTime: 1000 * 60 * 5,
    meta: { disableToast: true },
  });
}

export function useLocalLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      username,
      password,
    }: {
      username: string;
      password: string;
    }) => localLogin(username, password),
    onSuccess: (user: LocalAuthUser) => {
      clearUserScopedCaches(qc);
      qc.setQueryData(LOCAL_AUTH_QUERY_KEY, user);
      qc.setQueryData(["user", "authenticated"], true);
    },
  });
}

export function useLocalLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: localLogout,
    onSuccess: () => {
      clearUserScopedCaches(qc);
      qc.setQueryData(LOCAL_AUTH_QUERY_KEY, null);
      qc.setQueryData(["user", "authenticated"], false);
    },
  });
}
