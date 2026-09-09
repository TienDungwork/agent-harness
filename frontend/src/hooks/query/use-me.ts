import { useQuery } from "@tanstack/react-query";
import { useConfig } from "./use-config";
import { organizationService } from "#/api/organization-service/organization-service.api";
import { useSelectedOrganizationId } from "#/context/use-selected-organization";
import {
  isLocalGatewayAdmin,
  LOCAL_GATEWAY_ORG_ID,
} from "#/utils/local-gateway-admin";
import { useIsAuthed } from "./use-is-authed";

export const useMe = () => {
  const { data: config } = useConfig();
  const { organizationId } = useSelectedOrganizationId();
  const { data: isAuthed } = useIsAuthed();

  const isSaas = config?.app_mode === "saas";
  const localAdmin = isLocalGatewayAdmin();

  return useQuery({
    queryKey: ["organizations", organizationId, "me"],
    queryFn: () =>
      organizationService.getMe({
        orgId: organizationId || LOCAL_GATEWAY_ORG_ID,
      }),
    staleTime: 1000 * 60 * 5, // 5 minutes
    enabled: localAdmin ? !!isAuthed : isSaas && !!organizationId,
  });
};
