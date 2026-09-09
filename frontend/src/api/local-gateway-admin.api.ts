import { Creanova } from "./open-hands-axios";
import { OrganizationMember } from "#/types/org";
import { LOCAL_GATEWAY_ORG_ID } from "#/utils/local-gateway-admin";

export type LocalAuthUser = {
  id: string;
  username: string;
  email: string | null;
  is_admin: boolean;
  credit_balance: number;
};

export type LocalAdminUser = LocalAuthUser & {
  is_active: boolean;
  credit_limit: number;
};

type ConversationSearchItem = {
  id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
  execution_status?: string | null;
  sandbox_status?: string | null;
  metrics?: {
    accumulated_cost?: number | null;
    accumulated_token_usage?: {
      prompt_tokens?: number;
      completion_tokens?: number;
      cache_read_tokens?: number;
      cache_write_tokens?: number;
    } | null;
  } | null;
  agent?: {
    kind?: string | null;
    llm?: { model?: string | null } | null;
  } | null;
  current_model_id?: string | null;
};

type OrgConversationRow = {
  id: string;
  title: string | null;
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
};

function tokenUsage(item: ConversationSearchItem) {
  return item.metrics?.accumulated_token_usage ?? {};
}

export function toOrgConversationRow(
  item: ConversationSearchItem,
): OrgConversationRow {
  const tokens = tokenUsage(item);
  const prompt = tokens.prompt_tokens ?? 0;
  const completion = tokens.completion_tokens ?? 0;
  return {
    id: item.id,
    title: item.title ?? null,
    llm_model: item.agent?.llm?.model ?? item.current_model_id ?? null,
    agent_kind: item.agent?.kind ?? "Agent",
    user_id: "",
    user_email: null,
    created_at: item.created_at,
    updated_at: item.updated_at,
    sandbox_id: null,
    sandbox_status: item.sandbox_status ?? null,
    runtime_url: null,
    execution_status: item.execution_status ?? null,
    selected_repository: null,
    selected_branch: null,
    git_provider: null,
    trigger: null,
    pr_number: [],
    pr_merged: null,
    tags: {},
    accumulated_cost: item.metrics?.accumulated_cost ?? 0,
    prompt_tokens: prompt,
    completion_tokens: completion,
    total_tokens: prompt + completion,
    cache_read_tokens: tokens.cache_read_tokens ?? 0,
    cache_write_tokens: tokens.cache_write_tokens ?? 0,
  };
}

export function localAuthUserToMember(user: LocalAuthUser): OrganizationMember {
  return {
    org_id: LOCAL_GATEWAY_ORG_ID,
    user_id: user.id,
    email: user.email || user.username,
    role: user.is_admin ? "owner" : "member",
    max_iterations: 20,
    llm_model: "",
    llm_base_url: "",
    llm_api_key: "",
    status: "active",
  };
}

export async function localGatewayLogin(
  username: string,
  password: string,
): Promise<LocalAuthUser> {
  const { data } = await Creanova.post<LocalAuthUser>("/api/auth/login", {
    username,
    password,
  });
  return data;
}

export async function localGatewayFetchMe(): Promise<LocalAuthUser> {
  const { data } = await Creanova.get<LocalAuthUser>("/api/auth/me");
  return data;
}

export async function localGatewayLogout(): Promise<void> {
  await Creanova.post("/api/auth/logout");
}

export async function localGatewaySearchConversations(limit = 50): Promise<{
  items: OrgConversationRow[];
  total_items: number;
  page: number;
  per_page: number;
  total_pages: number;
}> {
  const { data } = await Creanova.get<{
    items?: ConversationSearchItem[];
  }>("/api/conversations/search", { params: { limit } });
  const raw = Array.isArray(data) ? data : (data.items ?? []);
  const items = raw.map(toOrgConversationRow);
  return {
    items,
    total_items: items.length,
    page: 1,
    per_page: limit,
    total_pages: 1,
  };
}

export async function localGatewayConversationStats() {
  const page = await localGatewaySearchConversations(100);
  const running = page.items.filter(
    (row) =>
      row.execution_status === "running" ||
      row.execution_status === "waiting_for_confirmation",
  ).length;
  const totalCost = page.items.reduce(
    (sum, row) => sum + row.accumulated_cost,
    0,
  );
  const prompt = page.items.reduce((sum, row) => sum + row.prompt_tokens, 0);
  const completion = page.items.reduce(
    (sum, row) => sum + row.completion_tokens,
    0,
  );
  return {
    active_conversations: running,
    running_runtimes: running,
    completed_24h: 0,
    completed_7d: 0,
    completed_30d: page.items.length,
    total_cost: totalCost,
    total_prompt_tokens: prompt,
    total_completion_tokens: completion,
    total_tokens: prompt + completion,
  };
}

export async function localGatewayUsageStats() {
  const stats = await localGatewayConversationStats();
  const page = await localGatewaySearchConversations(100);
  return {
    active_users: 1,
    agent_runs: page.total_items,
    total_tokens: stats.total_tokens,
    estimated_spend: stats.total_cost,
    daily_usage: [],
    team_usage: [],
    model_usage: [],
    agent_usage: [],
  };
}

export async function localGatewayUserUsage() {
  try {
    const { data } = await Creanova.get<LocalAdminUser[]>("/api/admin/users");
    return {
      items: data.map((user) => ({
        user_id: user.id,
        user_email: user.email || user.username,
        user_name: user.username,
        conversation_count: 0,
        first_conversation_at: null,
        last_conversation_at: null,
        first_login_at: null,
        last_login_at: null,
        spend_mtd: 0,
        spend_ytd: 0,
        spend_lifetime: user.credit_limit - user.credit_balance,
        budget_monthly_limit: user.credit_limit,
        budget_is_disabled: !user.is_active,
        prs_merged: null,
      })),
      has_more: false,
    };
  } catch {
    return { items: [], has_more: false };
  }
}

export async function localGatewayStopConversation(
  conversationId: string,
): Promise<void> {
  await Creanova.post(`/api/conversations/${conversationId}/pause`);
}
