import { CANVAS_UI_CLIENT_TOOL_NAME } from "#/constants/canvas-ui";

export {
  CANVAS_UI_CLIENT_ACTION_KIND,
  CANVAS_UI_CLIENT_TOOL_NAME,
  LEGACY_CANVAS_UI_TOOL_NAME,
} from "#/constants/canvas-ui";

export interface ClientToolSpec {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  annotations?: {
    title?: string | null;
    readOnlyHint: boolean;
    destructiveHint: boolean;
    idempotentHint: boolean;
    openWorldHint: boolean;
  };
}

const CANVAS_UI_DESCRIPTION = `Optional UI helper for Agent Canvas (chat left, tabs right: files/terminal/browser/…).

Do NOT call this tool for greetings, SSH, analytics questions, skill loading, or
idle turns. Do NOT call navigate_to_file on the project root or conversation
folder. Do NOT loop the same command.

Only call when you just produced something the user asked to see:

* Edited one specific file the user requested →
    command="navigate_to_file", path=<that file only>
* Previewable artifact (HTML/image/PDF/md report) →
    command="show_preview", path=<that file>
* Long terminal output the user should inspect →
    command="open_tab", tab="terminal"
* Browser URL the user should see → after browser_get_state(include_screenshot=true),
    command="open_tab", tab="browser"

At most one call per logical step. Prefer answering in chat when no artifact exists.
Never invent parameters (no security_risk).`;

export const CANVAS_UI_CLIENT_TOOL: ClientToolSpec = {
  name: CANVAS_UI_CLIENT_TOOL_NAME,
  description: CANVAS_UI_DESCRIPTION,
  parameters: {
    type: "object",
    additionalProperties: false,
    properties: {
      command: {
        type: "string",
        enum: ["navigate_to_file", "open_tab", "show_preview"],
        description: "UI command to dispatch.",
      },
      path: {
        type: "string",
        description:
          "Workspace-relative file path. Required for navigate_to_file and show_preview; ignored otherwise.",
      },
      tab: {
        type: "string",
        enum: ["files", "browser", "vscode", "terminal", "planner", "tasklist"],
        description: "Tab to open. Required for open_tab; ignored otherwise.",
      },
    },
    required: ["command"],
  },
  annotations: {
    readOnlyHint: true,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: false,
  },
};
