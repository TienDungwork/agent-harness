import { useParams } from "react-router";
import { useConfig } from "#/hooks/query/use-config";
import { useUserConversation } from "#/hooks/query/use-user-conversation";

const APP_TITLE_OSS = "Creanova";
const APP_TITLE_SAAS = "Creanova Cloud";

/**
 * Hook that returns the appropriate document title based on app_mode and current route.
 * - For conversation pages: "Conversation Title | Creanova" or "Conversation Title | Creanova Cloud"
 * - For other pages: "Creanova" or "Creanova Cloud"
 */
export const useAppTitle = () => {
  const { data: config } = useConfig();
  const { conversationId } = useParams<{ conversationId: string }>();
  const { data: conversation } = useUserConversation(conversationId ?? null);

  const appTitle = config?.app_mode === "oss" ? APP_TITLE_OSS : APP_TITLE_SAAS;
  const conversationTitle = conversation?.title;

  if (conversationId && conversationTitle) {
    return `${conversationTitle} | ${appTitle}`;
  }

  return appTitle;
};
