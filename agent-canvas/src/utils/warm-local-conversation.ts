import type { CreateConversationResponse } from "#/hooks/mutation/use-create-conversation";

type CreateFn = () => Promise<CreateConversationResponse>;

/**
 * One idle local conversation kept warm so Home Enter does not wait on create.
 *
 * Only used for plain local launches (no workspace / plugins / attachments).
 */
let generation = 0;
let inflight: Promise<CreateConversationResponse> | null = null;
let ready: CreateConversationResponse | null = null;

export function peekWarmLocalConversation(): CreateConversationResponse | null {
  return ready;
}

export function ensureWarmLocalConversation(createFn: CreateFn): void {
  if (ready || inflight) {
    return;
  }
  const gen = generation;
  inflight = createFn()
    .then((response) => {
      if (gen === generation) {
        ready = response;
        inflight = null;
      }
      return response;
    })
    .catch((error) => {
      if (gen === generation) {
        inflight = null;
      }
      throw error;
    });
}

/** Claim the warm slot (ready or in-flight). Returns null if none started. */
export async function claimWarmLocalConversation(): Promise<CreateConversationResponse | null> {
  if (ready) {
    const claimed = ready;
    ready = null;
    return claimed;
  }
  if (!inflight) {
    return null;
  }
  const gen = generation;
  try {
    const claimed = await inflight;
    if (gen !== generation) {
      return null;
    }
    // createFn's then may have already parked the result in `ready`.
    ready = null;
    return claimed;
  } catch {
    return null;
  }
}

/**
 * Drop a pre-created warm conversation. Call when the launch LLM / agent
 * profile changes so Home Enter does not claim a slot baked with old settings.
 */
export function discardWarmLocalConversation(): void {
  generation += 1;
  inflight = null;
  ready = null;
}

/** Test helper */
export function resetWarmLocalConversationForTests(): void {
  discardWarmLocalConversation();
}
