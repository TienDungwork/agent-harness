import { CreanovaObservation } from "./types/core/observations";
import { CreanovaAction } from "./types/core/actions";

export type Message = {
  sender: "user" | "assistant";
  content: string;
  timestamp: string;
  imageUrls?: string[];
  type?: "thought" | "error" | "action";
  success?: boolean;
  pending?: boolean;
  translationID?: string;
  eventID?: number;
  observation?: { payload: CreanovaObservation };
  action?: { payload: CreanovaAction };
};
