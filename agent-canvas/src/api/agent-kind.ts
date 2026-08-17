/**
 * Default agent kind for Creanova product surfaces.
 *
 * UI and API both use ``Creanova``. Legacy persisted values ``openhands`` /
 * ``llm`` are normalized on read for compatibility with older agent-server
 * state that may still be on disk.
 */
export const UI_DEFAULT_AGENT_KIND = "Creanova" as const;
export const API_DEFAULT_AGENT_KIND = "Creanova" as const;

const LEGACY_DEFAULT_AGENT_KINDS = new Set(["openhands", "llm", "Creanova"]);

export function toApiAgentKind(
  kind: string | null | undefined,
): string | null | undefined {
  if (kind == null) return kind;
  if (LEGACY_DEFAULT_AGENT_KINDS.has(kind)) {
    return API_DEFAULT_AGENT_KIND;
  }
  return kind;
}

export function fromApiAgentKind(
  kind: string | null | undefined,
): string | null | undefined {
  if (kind == null) return kind;
  if (LEGACY_DEFAULT_AGENT_KINDS.has(kind)) {
    return UI_DEFAULT_AGENT_KIND;
  }
  return kind;
}

export function isDefaultAgentKind(kind: string | null | undefined): boolean {
  return kind == null || LEGACY_DEFAULT_AGENT_KINDS.has(kind);
}
