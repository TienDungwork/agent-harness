import { CreanovaAction } from "#/types/core/actions";
import { CreanovaObservation } from "#/types/core/observations";

export const MAX_CONTENT_LENGTH = 1000;

export const getDefaultEventContent = (
  event: CreanovaAction | CreanovaObservation,
): string => `\`\`\`json\n${JSON.stringify(event, null, 2)}\n\`\`\``;
