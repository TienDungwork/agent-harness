# Task — Phase 5 line 101: TTL / memory fail — degrade an toàn (vẫn trả lời được)

Workdir: agent-harness/dong

Implement ONLY this unchecked item from specs/implementation-plan.md:
`- [ ] TTL / memory fail: degrade an toàn (vẫn trả lời được).`

Do NOT implement Phase 6/7 or unrelated tasks.

## Context

Memory subsystems:
- `src/memory/ttl_cache.py` — `get_ttl_cached`, `set_ttl_cached` (thread-safe dict)
- `src/memory/longterm.py` — `recall_long_term`, `save_to_long_term` (in-memory + optional Qdrant)
- `src/memory/extract.py` — `extract_and_store_memory` (heuristic + LLM, already swallows LLM errors)
- `src/agent/graph.py` — `recall_node` (start of graph), `run_store_extract` (post-pipeline after answer)
- `src/main.py` — `_lookup_ttl_cache()` before graph; `set_ttl_cached()` after success on `/api/chat`, `/ask`, `/api/agent/stream`

Existing tests: `tests/test_memory_ttl_cache.py`, `tests/test_memory_nodes.py`, `tests/test_memory_longterm.py`

test-plan.md expects: TTL cache hit/miss; memory short/long-term. **This task:** when TTL or memory ops fail, agent MUST still answer (degrade gracefully, no 503/crash solely due to cache/memory).

## Requirements

1. **TTL cache degrade** (`src/memory/ttl_cache.py` and/or `src/main.py`):
   - `get_ttl_cached`: on unexpected exception (corrupt entry, lock error, bad data shape) → return `None` (cache miss), optionally log warning — do NOT propagate to caller.
   - `set_ttl_cached`: on failure → swallow/log, do NOT break response path.
   - `_lookup_ttl_cache` in main.py: wrap safely so lookup failure = miss, not 503.

2. **Long-term recall degrade** (`src/agent/graph.py` `recall_node`):
   - If `recall_long_term` raises → return `recalled_memories=[]` with recall event showing degraded/empty output; graph continues normally.

3. **Store/extract degrade** (`src/agent/graph.py` `run_store_extract`):
   - Wrap `extract_and_store_memory` in try/except.
   - On failure: return store_extract events with `output={"extracted_memories": [], "degraded": true, "error": "<short msg>"}` — do NOT raise (post-pipeline must never crash answer or stream thread).

4. **Optional hardening** (`src/memory/longterm.py`):
   - Ensure `save_to_long_term` never raises to caller (already mostly safe; verify).

5. **Tests** — create `tests/test_phase5_ttl_memory_degrade.py`:
   - TTL get raises → `_lookup_ttl_cache` returns None; `/api/chat` still 200 when agent mocked OK.
   - TTL set raises → response still returned with answer.
   - `recall_long_term` raises → `recall_node` returns empty memories, no exception.
   - `extract_and_store_memory` raises → `run_store_extract` returns done event with degraded output, no raise.
   - Integration: stream with recall fail + agent OK → `__answer__` status done (not error); store_extract degraded OK.
   - Follow patterns from `tests/test_phase5_llm_db_errors.py`, `tests/test_memory_ttl_cache.py`.

6. **Docs**:
   - Mark `[x]` line 101 in `specs/implementation-plan.md`.
   - Add entry to `specs/change-log.md`.

7. **Run**:
   ```bash
   pytest tests/test_phase5_ttl_memory_degrade.py tests/test_memory_ttl_cache.py tests/test_memory_nodes.py -q
   pytest -q
   ```

## Constraints

- Minimal diff; no new features beyond graceful degrade.
- Memory/TTL failures must NOT surface as user-facing 503 unless core agent also fails.
- PEP 8, plain Python style.
