# Execution Log: LiteLLM auth error on cross-login

- Category: debug_fix
- Task: Fix litellm.AuthenticationError (OPENAI_API_KEY missing) when logging in elsewhere with same account/model
- Started: 2026-09-16 10:01:29
- Pipeline: 4a (04-bugfinder -> 05-fix -> 06-test -> 07-review)

## Skill: 00-orchestrator
- Status: completed
- Route: unknown bug → 04-bugfinder first

## Skill: 04-bugfinder
- Status: completed
- Issue: litellm.AuthenticationError OPENAI_API_KEY must be set when logging in elsewhere (same account/model)
- Primary root cause: local-gateway `_lean_conversation_create_body` always sets `secrets_encrypted=False` after `_rewrite_llm_from_ui_blob`. Per-user settings blob caches UI-redacted `api_key` (`**********`/`null`). Create then either keeps undecrypted Fernet ciphertext or ends with `api_key=None` → OpenAI client "api_key must be set".
- Evidence: conversation `7a20c0dc…` meta has `secrets_encrypted=False` and `api_key=None`; disk settings still have Fernet key; encrypted GET via gateway returns key; lean rewrite forces secrets_encrypted False.
- Likelihood: High
- Severity: Critical
- Next: 05-fix on services/local-gateway/proxy.py

## Skill: 05-fix
- Status: completed
- Changes:
  - `services/local-gateway/proxy.py`: plaintext-vs-Fernet aware `_rewrite_llm_from_ui_blob`; only set `secrets_encrypted=False` when plaintext key installed; sanitize redacted blob keys; always clear Fernet on local Ollama / analytics fallback
  - `services/local-gateway/tests/test_proxy_profiles_blob.py`: regression tests
  - `agent-canvas/src/api/settings-service/settings-service.api.ts`: treat null encrypted api_key as missing
- Verification: unit asserts PASS; live create as demo+admin → Ollama base + non-empty key; POST events returned 200 and LiteLLM completed (cost-calc warning, no AuthenticationError)
- Restarted: `docker compose restart local-gateway`

## Skill: 06-test
- Status: completed (inline asserts + live create/chat)

## Skill: 07-review
- Status: completed
- Verdict: PASS for targeted fix; tunnel models intentionally redirected to ANALYTICS_LLM (pre-existing stack policy)
