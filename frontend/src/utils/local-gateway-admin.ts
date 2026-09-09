import type { WebClientConfig } from "#/api/option-service/option.types";

/** Synthetic org id so existing usage hooks that require organizationId still run. */
export const LOCAL_GATEWAY_ORG_ID = "local";

export function isLocalGatewayAdmin(): boolean {
  const raw = (import.meta.env.VITE_LOCAL_GATEWAY_ADMIN ?? "")
    .toString()
    .trim()
    .toLowerCase();
  return raw === "true" || raw === "1";
}

export const LOCAL_GATEWAY_WEB_CLIENT_CONFIG: WebClientConfig = {
  app_mode: "oss",
  posthog_client_key: null,
  feature_flags: {
    enable_billing: false,
    hide_llm_settings: false,
    enable_jira: false,
    enable_jira_dc: false,
    enable_linear: false,
    hide_users_page: false,
    hide_billing_page: true,
    hide_integrations_page: true,
    enable_onboarding: false,
  },
  providers_configured: [],
  maintenance_start_time: null,
  auth_url: null,
  recaptcha_site_key: null,
  faulty_models: [],
  error_message: null,
  updated_at: new Date().toISOString(),
  github_app_slug: null,
  gitlab_enabled: false,
  slack_enabled: false,
};
