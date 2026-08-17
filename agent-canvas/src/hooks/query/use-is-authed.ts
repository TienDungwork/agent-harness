import { useQuery } from "@tanstack/react-query";
import { fetchLocalMe, isLocalAuthEnabled } from "#/api/local-auth/client";

export const useIsAuthed = () =>
  useQuery({
    queryKey: ["user", "authenticated"],
    queryFn: async () => {
      if (!isLocalAuthEnabled()) {
        return true;
      }
      const me = await fetchLocalMe();
      return me !== null;
    },
    staleTime: 1000 * 60 * 5,
    gcTime: 1000 * 60 * 15,
    retry: false,
    meta: {
      disableToast: true,
    },
  });
