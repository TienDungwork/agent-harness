import { CreanovaEvent } from "#/types/agent-server/core";

export const MAX_CONTENT_LENGTH = 1000;

export const getDefaultEventContent = (event: CreanovaEvent): string =>
  `\`\`\`json\n${JSON.stringify(event, null, 2)}\n\`\`\``;
