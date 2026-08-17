import { useInfiniteQuery } from "@tanstack/react-query";
import { SharedClient } from "@Creanova/typescript-client/clients";
import type { CreanovaEvent } from "#/types/agent-server/core";
import { getAgentServerClientOptions } from "#/api/agent-server-client-options";

interface SharedEventPage {
  items: CreanovaEvent[];
  next_page_id: string | null;
}

export const useSharedConversationEvents = (conversationId?: string) =>
  useInfiniteQuery({
    queryKey: ["shared-conversation-events", conversationId],
    queryFn: ({ pageParam }) => {
      if (!conversationId) {
        throw new Error("Conversation ID is required");
      }
      return new SharedClient(getAgentServerClientOptions()).searchSharedEvents(
        {
          conversationId,
          limit: 100,
          pageId: pageParam,
        },
      ) as Promise<SharedEventPage>;
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_page_id ?? undefined,
    enabled: !!conversationId,
    retry: false, // Don't retry for shared conversations
  });
