import {
  type RouteConfig,
  layout,
  index,
  route,
} from "@react-router/dev/routes";

export default [
  route("login", "routes/local-login.tsx"),
  layout("routes/root-layout.tsx", [
    index("routes/index-home.tsx"),
    route("conversations", "routes/home.tsx"),
    route(
      "conversations/:conversationId/panel",
      "routes/conversation-panel.tsx",
    ),
    route("conversations/:conversationId", "routes/conversation.tsx"),
    route("launch", "routes/launch.tsx"),
    route("customize", "routes/extensions-hub.tsx"),
    route("skills", "routes/skills-settings.tsx"),
    route("plugins", "routes/skills-plugins.tsx"),
    route("mcp", "routes/mcp.tsx"),
    route("settings", "routes/settings.tsx", [
      index("routes/settings-index.tsx"),
      route("llm", "routes/llm-settings.tsx"),
      route("agent", "routes/agent-settings.tsx"),
      route("agents", "routes/agent-profiles-settings.tsx"),
      route("condenser", "routes/condenser-settings.tsx"),
      route("verification", "routes/verification-settings.tsx"),
      route("app", "routes/app-settings.tsx"),
      route("secrets", "routes/secrets-settings.tsx"),
      route("host", "routes/host-settings.tsx"),
    ]),
    route("oauth/device/verify", "routes/device-verify.tsx"),
    route("automations", "routes/automations-list.tsx"),
    route("automations/:automationId", "routes/automation-detail.tsx"),
    route("admin/users", "routes/local-admin-users.tsx"),
    // Legacy redirects → Settings → Host
    route("admin/infra", "routes/host-redirect-infra.tsx"),
    route("admin/infra/:serverId", "routes/host-redirect-infra-detail.tsx"),
    route("admin/ssh", "routes/host-redirect-ssh.tsx"),
  ]),
  route(
    "shared/conversations/:conversationId",
    "routes/shared-conversation.tsx",
  ),
] satisfies RouteConfig;
