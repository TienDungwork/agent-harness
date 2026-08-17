/**
 * Canonical LLM defaults for Creanova local installs.
 * Override via VITE_CREANOVA_LLM_MODEL / VITE_CREANOVA_LLM_BASE_URL in `.env`.
 */
import sharedDefaults from "../../config/defaults.json";

const llm = (sharedDefaults as { llm?: { model?: string; baseUrl?: string } })
  .llm;

export const CREANOVA_LLM_DEFAULT_MODEL =
  import.meta.env.VITE_CREANOVA_LLM_MODEL ||
  llm?.model ||
  "openai/nemotron-3-nano:4b";

export const CREANOVA_LLM_DEFAULT_BASE_URL =
  import.meta.env.VITE_CREANOVA_LLM_BASE_URL ||
  llm?.baseUrl ||
  "https://realtor-authentication-collecting-areas.trycloudflare.com/v1";
