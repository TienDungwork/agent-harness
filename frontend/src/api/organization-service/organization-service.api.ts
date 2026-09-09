import {
  PendingInvitationsPage,
  BatchInvitationResult,
  GitOrgClaim,
  Organization,
  OrganizationMember,
  OrganizationMembersPage,
  OrganizationUserRole,
  UpdateOrganizationMemberParams,
} from "#/types/org";
import { Settings, MarketplaceRegistration } from "#/types/settings";
import { Creanova } from "../open-hands-axios";
import {
  isLocalGatewayAdmin,
  LOCAL_GATEWAY_ORG_ID,
} from "#/utils/local-gateway-admin";
import {
  localAuthUserToMember,
  localGatewayConversationStats,
  localGatewayFetchMe,
  localGatewaySearchConversations,
  localGatewayStopConversation,
  localGatewayUsageStats,
  localGatewayUserUsage,
} from "../local-gateway-admin.api";

type OrganizationSettingsResponse = Pick<
  Settings,
  | "agent_settings"
  | "conversation_settings"
  | "search_api_key"
  | "llm_api_key_set"
>;

export type OrganizationAppSettingsResponse = {
  enable_proactive_conversation_starters: boolean;
  max_budget_per_task: number | null;
  registered_marketplaces: MarketplaceRegistration[];
  updated_at: string | null;
};

export type OrganizationAppSettingsUpdate = {
  enable_proactive_conversation_starters?: boolean;
  max_budget_per_task?: number | null;
  registered_marketplaces?: MarketplaceRegistration[] | null;
  /** For optimistic locking - must match current updated_at */
  last_known_updated_at?: string | null;
};

export const organizationService = {
  getMe: async ({ orgId }: { orgId: string }) => {
    if (isLocalGatewayAdmin()) {
      const me = await localGatewayFetchMe();
      return localAuthUserToMember(me);
    }
    const { data } = await Creanova.get<OrganizationMember>(
      `/api/organizations/${orgId}/me`,
    );

    return data;
  },

  getOrganizations: async () => {
    if (isLocalGatewayAdmin()) {
      const localOrg: Organization = {
        id: LOCAL_GATEWAY_ORG_ID,
        name: "Local",
        contact_name: "",
        contact_email: "",
        conversation_expiration: 0,
        remote_runtime_resource_factor: 1,
        billing_margin: 0,
        enable_proactive_conversation_starters: false,
        sandbox_base_container_image: "",
        sandbox_runtime_container_image: "",
        org_version: 1,
        search_api_key: null,
        sandbox_api_key: null,
        max_budget_per_task: 0,
        enable_solvability_analysis: false,
        v1_enabled: true,
        credits: null,
        is_personal: false,
      };
      return {
        items: [localOrg],
        currentOrgId: LOCAL_GATEWAY_ORG_ID,
      };
    }
    const { data } = await Creanova.get<{
      items: Organization[];
      current_org_id: string | null;
    }>("/api/organizations");
    return {
      items: data?.items || [],
      currentOrgId: data?.current_org_id || null,
    };
  },

  updateOrganization: async ({
    orgId,
    name,
  }: {
    orgId: string;
    name: string;
  }) => {
    const { data } = await Creanova.patch<Organization>(
      `/api/organizations/${orgId}`,
      { name },
    );
    return data;
  },

  deleteOrganization: async ({ orgId }: { orgId: string }) => {
    await Creanova.delete(`/api/organizations/${orgId}`);
  },

  getOrganizationMembers: async ({
    orgId,
    page = 1,
    limit = 10,
    email,
  }: {
    orgId: string;
    page?: number;
    limit?: number;
    email?: string;
  }) => {
    const params = new URLSearchParams();

    // Calculate offset from page number (page_id is offset-based)
    const offset = (page - 1) * limit;
    params.set("page_id", String(offset));
    params.set("limit", String(limit));

    if (email) {
      params.set("email", email);
    }

    const { data } = await Creanova.get<OrganizationMembersPage>(
      `/api/organizations/${orgId}/members?${params.toString()}`,
    );

    return data;
  },

  getOrganizationMembersCount: async ({
    orgId,
    email,
  }: {
    orgId: string;
    email?: string;
  }) => {
    const params = new URLSearchParams();

    if (email) {
      params.set("email", email);
    }

    const { data } = await Creanova.get<number>(
      `/api/organizations/${orgId}/members/count?${params.toString()}`,
    );

    return data;
  },

  getOrganizationPaymentInfo: async ({ orgId }: { orgId: string }) => {
    const { data } = await Creanova.get<{
      cardNumber: string;
    }>(`/api/organizations/${orgId}/payment`);
    return data;
  },

  updateMember: async ({
    orgId,
    userId,
    ...updateData
  }: {
    orgId: string;
    userId: string;
  } & UpdateOrganizationMemberParams) => {
    const { data } = await Creanova.patch(
      `/api/organizations/${orgId}/members/${userId}`,
      updateData,
    );

    return data;
  },

  removeMember: async ({
    orgId,
    userId,
  }: {
    orgId: string;
    userId: string;
  }) => {
    await Creanova.delete(`/api/organizations/${orgId}/members/${userId}`);
  },

  inviteMembers: async ({
    orgId,
    emails,
    role = "member",
  }: {
    orgId: string;
    emails: string[];
    role?: OrganizationUserRole;
  }) => {
    const { data } = await Creanova.post<BatchInvitationResult>(
      `/api/organizations/${orgId}/members/invite`,
      {
        emails,
        role,
      },
    );

    return data;
  },

  getPendingInvitations: async ({ orgId }: { orgId: string }) => {
    const { data } = await Creanova.get<PendingInvitationsPage>(
      `/api/organizations/${orgId}/members/invite`,
    );

    return data;
  },

  revokeInvitation: async ({
    orgId,
    invitationId,
  }: {
    orgId: string;
    invitationId: number;
  }) => {
    await Creanova.delete(
      `/api/organizations/${orgId}/members/invite/${invitationId}`,
    );
  },

  switchOrganization: async ({ orgId }: { orgId: string }) => {
    const { data } = await Creanova.post<Organization>(
      `/api/organizations/${orgId}/switch`,
    );
    return data;
  },

  acceptInvitation: async ({ token }: { token: string }) => {
    const { data } = await Creanova.post<{
      success: boolean;
      org_id: string;
      org_name: string;
      role: string;
    }>("/api/organizations/members/invite/accept", { token });

    return data;
  },

  getOrganizationSettings: async ({ orgId }: { orgId: string }) => {
    const { data } = await Creanova.get<OrganizationSettingsResponse>(
      `/api/organizations/${orgId}/settings`,
    );
    return data;
  },

  saveOrganizationSettings: async ({
    orgId,
    settings,
  }: {
    orgId: string;
    settings: Partial<Settings> & Record<string, unknown>;
  }) => {
    const { data } = await Creanova.patch<OrganizationSettingsResponse>(
      `/api/organizations/${orgId}/settings`,
      settings,
    );
    return data;
  },

  getGitClaims: async ({ orgId }: { orgId: string }) => {
    const { data } = await Creanova.get<GitOrgClaim[]>(
      `/api/organizations/${orgId}/git-claims`,
    );
    return data;
  },

  claimGitOrg: async ({
    orgId,
    provider,
    gitOrganization,
  }: {
    orgId: string;
    provider: string;
    gitOrganization: string;
  }) => {
    const { data } = await Creanova.post<GitOrgClaim>(
      `/api/organizations/${orgId}/git-claims`,
      { provider, git_organization: gitOrganization },
    );
    return data;
  },

  disconnectGitOrg: async ({
    orgId,
    claimId,
  }: {
    orgId: string;
    claimId: string;
  }) => {
    await Creanova.delete(`/api/organizations/${orgId}/git-claims/${claimId}`);
  },

  getOrganizationAppSettings: async () => {
    const { data } = await Creanova.get<OrganizationAppSettingsResponse>(
      "/api/organizations/app",
    );
    return data;
  },

  saveOrganizationAppSettings: async (
    settings: OrganizationAppSettingsUpdate,
  ) => {
    const { data } = await Creanova.post<OrganizationAppSettingsResponse>(
      "/api/organizations/app",
      settings,
    );
    return data;
  },

  // Organization Conversation APIs
  getConversationStats: async ({ orgId }: { orgId: string }) => {
    if (isLocalGatewayAdmin()) {
      return localGatewayConversationStats();
    }
    const { data } = await Creanova.get<OrgConversationStats>(
      `/api/organizations/${orgId}/conversations/stats`,
    );
    return data;
  },

  getUsageStats: async ({
    orgId,
    days,
    timeWindow,
  }: {
    orgId: string;
    days?: number;
    timeWindow?: string;
  }) => {
    if (isLocalGatewayAdmin()) {
      return localGatewayUsageStats();
    }
    let resolvedDays: number | undefined;
    if (typeof days === "number") {
      resolvedDays = days;
    } else if (!timeWindow) {
      resolvedDays = 7;
    }
    const params: Record<string, number | string> = {};
    if (typeof resolvedDays === "number") {
      params.days = resolvedDays;
    }
    if (timeWindow) {
      params.time_window = timeWindow;
    }
    const { data } = await Creanova.get<OrgUsageStats>(
      `/api/organizations/${orgId}/conversations/usage-stats`,
      { params },
    );
    return data;
  },

  getUserUsageStats: async ({
    orgId,
    limit,
    offset,
  }: {
    orgId: string;
    limit?: number;
    offset?: number;
  }) => {
    if (isLocalGatewayAdmin()) {
      return localGatewayUserUsage();
    }
    const params: Record<string, number> = {};
    if (typeof limit === "number") {
      params.limit = limit;
    }
    if (typeof offset === "number") {
      params.offset = offset;
    }
    const { data } = await Creanova.get<OrgUserUsageStats>(
      `/api/organizations/${orgId}/conversations/user-usage`,
      { params },
    );
    return data;
  },

  getBudgetSettings: async ({
    orgId,
    usersPage,
    usersPerPage,
    usersSearch,
    usersStatus,
  }: {
    orgId: string;
    usersPage?: number;
    usersPerPage?: number;
    usersSearch?: string;
    usersStatus?: string;
  }) => {
    const params: Record<string, number | string> = {};
    if (typeof usersPage === "number") {
      params.users_page = usersPage;
    }
    if (typeof usersPerPage === "number") {
      params.users_per_page = usersPerPage;
    }
    if (usersSearch) {
      params.users_search = usersSearch;
    }
    if (usersStatus) {
      params.users_status = usersStatus;
    }
    const { data } = await Creanova.get<OrgBudgetSettings>(
      `/api/organizations/${orgId}/budgets`,
      { params },
    );
    return data;
  },

  updateBudgetSettings: async ({
    orgId,
    payload,
  }: {
    orgId: string;
    payload: OrgBudgetSettingsUpdate;
  }) => {
    const { data } = await Creanova.patch<OrgBudgetSettings>(
      `/api/organizations/${orgId}/budgets`,
      payload,
    );
    return data;
  },

  upsertBudgetOverride: async ({
    orgId,
    userId,
    payload,
  }: {
    orgId: string;
    userId: string;
    payload: OrgBudgetUserOverrideUpdate;
  }) => {
    const { data } = await Creanova.put<OrgBudgetUser>(
      `/api/organizations/${orgId}/budgets/overrides/${userId}`,
      payload,
    );
    return data;
  },

  deleteBudgetOverride: async ({
    orgId,
    userId,
  }: {
    orgId: string;
    userId: string;
  }) => {
    await Creanova.delete(
      `/api/organizations/${orgId}/budgets/overrides/${userId}`,
    );
  },

  getConversations: async ({
    orgId,
    page = 1,
    perPage = 20,
    search,
    sortBy = "updated_at",
    sortOrder = "desc",
    executionStatus,
    sandboxStatus,
    timeWindow,
    includeSubConversations = false,
  }: {
    orgId: string;
    page?: number;
    perPage?: number;
    search?: string;
    sortBy?: string;
    sortOrder?: string;
    executionStatus?: string;
    sandboxStatus?: string;
    timeWindow?: string;
    includeSubConversations?: boolean;
  }) => {
    if (isLocalGatewayAdmin()) {
      return localGatewaySearchConversations(perPage);
    }
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("per_page", String(perPage));
    params.set("sort_by", sortBy);
    params.set("sort_order", sortOrder);
    if (search) params.set("search", search);
    if (executionStatus) params.set("execution_status", executionStatus);
    if (sandboxStatus) params.set("sandbox_status", sandboxStatus);
    if (timeWindow) params.set("time_window", timeWindow);
    if (includeSubConversations)
      params.set("include_sub_conversations", "true");

    const { data } = await Creanova.get<OrgConversationPage>(
      `/api/organizations/${orgId}/conversations?${params.toString()}`,
    );
    return data;
  },

  getConversation: async ({
    orgId,
    conversationId,
  }: {
    orgId: string;
    conversationId: string;
  }) => {
    const { data } = await Creanova.get<OrgConversationResponse>(
      `/api/organizations/${orgId}/conversations/${conversationId}`,
    );
    return data;
  },

  stopConversation: async ({
    orgId,
    conversationId,
  }: {
    orgId: string;
    conversationId: string;
  }) => {
    if (isLocalGatewayAdmin()) {
      await localGatewayStopConversation(conversationId);
      return {
        success: true,
        message: "paused",
        conversation_id: conversationId,
      };
    }
    const { data } = await Creanova.post<{
      success: boolean;
      message: string;
      conversation_id: string;
      sandbox_id?: string;
    }>(`/api/organizations/${orgId}/conversations/${conversationId}/stop`);
    return data;
  },

  exportConversationsUrl: ({
    orgId,
    search,
    sortBy = "updated_at",
    sortOrder = "desc",
    executionStatus,
    sandboxStatus,
    timeWindow,
  }: {
    orgId: string;
    search?: string;
    sortBy?: string;
    sortOrder?: string;
    executionStatus?: string;
    sandboxStatus?: string;
    timeWindow?: string;
  }) => {
    const params = new URLSearchParams();
    params.set("sort_by", sortBy);
    params.set("sort_order", sortOrder);
    if (search) params.set("search", search);
    if (executionStatus) params.set("execution_status", executionStatus);

    if (sandboxStatus) params.set("sandbox_status", sandboxStatus);
    if (timeWindow) params.set("time_window", timeWindow);
    return `/api/organizations/${orgId}/conversations/export?${params.toString()}`;
  },
};

// Types for org conversation APIs
interface OrgConversationStats {
  active_conversations: number;
  running_runtimes: number;
  completed_24h: number;
  completed_7d: number;
  completed_30d: number;
  total_cost: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
}

interface DailyUsageData {
  date: string;
  tokens: number;
  conversations: number;
}

interface TeamUsageData {
  user_id: string;
  user_email: string | null;
  user_name: string | null;
  conversation_count: number;
  total_tokens: number;
  percentage: number;
}

interface OrgUserUsageRow {
  user_id: string;
  user_email: string | null;
  user_name: string | null;
  conversation_count: number;
  first_conversation_at: string | null;
  last_conversation_at: string | null;
  first_login_at: string | null;
  last_login_at: string | null;
  spend_mtd: number;
  spend_ytd: number;
  spend_lifetime: number;
  budget_monthly_limit: number | null;
  budget_is_disabled: boolean;
  prs_merged: number | null;
}

interface OrgUserUsageStats {
  items: OrgUserUsageRow[];
  has_more: boolean;
}

interface ModelUsageData {
  model_name: string;
  conversation_count: number;
  total_tokens: number;
  total_cost: number;
}

interface AgentUsageData {
  agent_name: string;
  conversation_count: number;
  total_cost: number;
}

interface OrgUsageStats {
  active_users: number;
  agent_runs: number;
  total_tokens: number;
  estimated_spend: number;
  daily_usage: DailyUsageData[];
  team_usage: TeamUsageData[];
  model_usage: ModelUsageData[];
  agent_usage: AgentUsageData[];
}

interface OrgBudgetThreshold {
  id: number;
  percentage: number;
  email_enabled: boolean;
  slack_enabled: boolean;
}

interface OrgBudgetUser {
  user_id: string;
  user_email: string | null;
  user_name: string | null;
  current_spend: number;
  monthly_limit: number | null;
  effective_monthly_limit: number | null;
  is_disabled: boolean;
  is_override: boolean;
}

interface OrgBudgetSettings {
  enabled: boolean;
  monthly_limit: number | null;
  reset_day: number;
  slack_channel: string | null;
  slack_team_id: string | null;
  default_user_monthly_limit: number | null;
  cycle_start_at: string;
  cycle_end_at: string;
  current_spend: number;
  current_spend_percentage: number;
  thresholds: OrgBudgetThreshold[];
  users: OrgBudgetUser[];
  users_total: number;
  users_page: number;
  users_per_page: number;
}

interface OrgBudgetSettingsUpdate {
  enabled?: boolean | null;
  monthly_limit?: number | null;
  reset_day?: number | null;
  default_user_monthly_limit?: number | null;
  slack_channel?: string | null;
  slack_team_id?: string | null;
  thresholds?:
    | {
        percentage: number;
        email_enabled: boolean;
        slack_enabled: boolean;
      }[]
    | null;
}

interface OrgBudgetUserOverrideUpdate {
  monthly_limit?: number | null;
  is_disabled: boolean;
}

interface OrgConversationResponse {
  id: string;
  title: string;
  llm_model: string | null;
  agent_kind: string;
  user_id: string;
  user_email: string | null;
  created_at: string;
  updated_at: string;
  sandbox_id: string | null;
  sandbox_status: string | null;
  runtime_url: string | null;
  execution_status: string | null;
  selected_repository: string | null;
  selected_branch: string | null;
  git_provider: string | null;
  trigger: string | null;
  pr_number: number[];
  pr_merged: boolean | null;
  tags: Record<string, string>;
  accumulated_cost: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
}

interface OrgConversationPage {
  items: OrgConversationResponse[];
  total_items: number;
  page: number;
  per_page: number;
  total_pages: number;
}
