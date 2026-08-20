/**
 * Default agent kind mapping between Creanova UI and OpenHands agent-server.
 *
 * UI surfaces use ``Creanova``. The agent-server wire format (and
 * ``@Creanova/typescript-client`` ``AgentKind``) still expects ``openhands``
 * or ``acp``. Legacy persisted ``llm`` values are treated as the default kind.
 */
export const UI_DEFAULT_AGENT_KIND = "Creanova" as const;
export const API_DEFAULT_AGENT_KIND = "openhands" as const;

const DEFAULT_AGENT_KINDS = new Set(["openhands", "llm", "Creanova"]);

export function toApiAgentKind(
  kind: string | null | undefined,
): string | null | undefined {
  if (kind == null) return kind;
  if (DEFAULT_AGENT_KINDS.has(kind)) {
    return API_DEFAULT_AGENT_KIND;
  }
  return kind;
}

export function fromApiAgentKind(
  kind: string | null | undefined,
): string | null | undefined {
  if (kind == null) return kind;
  if (DEFAULT_AGENT_KINDS.has(kind)) {
    return UI_DEFAULT_AGENT_KIND;
  }
  return kind;
}

export function isDefaultAgentKind(kind: string | null | undefined): boolean {
  return kind == null || DEFAULT_AGENT_KINDS.has(kind);
}
