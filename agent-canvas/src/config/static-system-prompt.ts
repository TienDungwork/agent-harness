import manifestJson from "../../config/local-agent/manifest.json";
import soulContent from "../../config/SOUL.md?raw";
import role from "../../config/local-agent/ROLE.md?raw";
import securityRisk from "../../config/local-agent/SECURITY_RISK_ASSESSMENT.md?raw";
import browserTools from "../../config/local-agent/BROWSER_TOOLS.md?raw";
import externalServices from "../../config/local-agent/EXTERNAL_SERVICES.md?raw";
import processManagement from "../../config/local-agent/PROCESS_MANAGEMENT.md?raw";

const SECTION_SEPARATOR = "\n\n";

export type CanvasPromptSectionId =
  | "soul"
  | "role"
  | "security_risk_assessment"
  | "browser"
  | "external_services"
  | "process_management"
  | "harness"
  | "runtime_services";

export type StaticPromptSectionId = Exclude<
  CanvasPromptSectionId,
  "harness" | "runtime_services"
>;

type PromptManifest = {
  sections: Array<{
    id: CanvasPromptSectionId;
    file: string | null;
    enabled: boolean;
  }>;
  lan_disable: CanvasPromptSectionId[];
};

export const CANVAS_PROMPT_MANIFEST = manifestJson as PromptManifest;

function wrapSoul(raw: string): string {
  const text = raw.trim();
  if (text.startsWith("<SOUL>")) {
    return text;
  }
  return `<SOUL>\n${text}\n</SOUL>`;
}

/** Local running-agent laws. Edit the markdown; toggles live in config/local-agent/manifest.json. */
export const CANVAS_STATIC_PROMPT_SECTIONS: ReadonlyArray<{
  id: StaticPromptSectionId;
  text: string;
}> = [
  { id: "soul", text: wrapSoul(soulContent) },
  { id: "role", text: role },
  { id: "security_risk_assessment", text: securityRisk },
  { id: "browser", text: browserTools },
  { id: "external_services", text: externalServices },
  { id: "process_management", text: processManagement },
];

export function isCanvasPromptSectionEnabled(
  id: CanvasPromptSectionId,
  options: { isLan: boolean; enableBrowser?: boolean },
): boolean {
  const entry = CANVAS_PROMPT_MANIFEST.sections.find(
    (section) => section.id === id,
  );
  if (!entry?.enabled) {
    return false;
  }
  if (id === "browser" && options.enableBrowser === false) {
    return false;
  }
  if (options.isLan && CANVAS_PROMPT_MANIFEST.lan_disable.includes(id)) {
    return false;
  }
  return true;
}

export function assembleCanvasStaticSystemPrompt(options: {
  enableBrowser: boolean;
  isLan?: boolean;
}): string {
  const isLan = options.isLan === true;
  return CANVAS_STATIC_PROMPT_SECTIONS.filter((section) =>
    isCanvasPromptSectionEnabled(section.id, {
      isLan,
      enableBrowser: options.enableBrowser,
    }),
  )
    .map((section) => section.text.trim())
    .filter((text) => text.length > 0)
    .join(SECTION_SEPARATOR);
}
