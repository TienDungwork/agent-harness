# Execution Log: debug_fix_settings_blob_corrupts_llm

## Task
After updating Qwen LLM profile, base_url/api_key appear broken and chat fails with `model 'qwen-3.8-27B' not found`.

## Pipeline
04-bugfinder → 05-fix → 06-test → 07-review

## Status
Complete

## 05-fix

- `proxy.py`: store settings PATCH *response*; reject diff-shaped blobs; invalidate blob on profile activate
- `llm-settings-local-view.tsx`: keep custom base_url on Basic model change
- `llm-model-wire.ts` + ProfilesService: normalize host-root base_url → `/v1`
- Live: repaired `qwen-3.8-27B` → model `openai/qwen3.8:27b-q4_K_M`, base `.../v1`

## 06-test

- Unit: 22 gateway tests passed; vitest llm-model-wire 6 passed
- Live: PATCH then GET settings keeps full doc; activate updates active profile

## 07-review

**Status: PASS**
