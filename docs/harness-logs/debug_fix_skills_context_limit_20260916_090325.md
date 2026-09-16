# debug_fix: skills still blow LiteLLM project limit on new chat

## Goal
New chat must not send ~480KB skill catalog; latency should match a lean API call.

## Root cause (confirmed)
1. `agent_profile_id` → `discover_profile_skills()` injected ~63 skills (~480KB).
2. Create used encrypted disk LLM (`18083` LiteLLM project limits) while UI/API used Ollama `11434`.

## Fix
- `patch_no_profile_skills.py` → empty catalog
- UI local-auth skips `agent_profile_id`
- Gateway lean: strip skills, rewrite LLM from UI settings blob to Ollama + `api_key=ollama`

## Verify
- Conversation finished with assistant `OK`, skills=0, model=qwen3-16k-nothink @ 11434
- No more `vượt giới hạn project` on lean create path
