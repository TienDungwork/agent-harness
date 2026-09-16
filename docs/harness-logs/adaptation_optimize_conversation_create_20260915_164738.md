# Execution Log: Optimize conversation create latency

**Task**: Reduce New-chat → Enter → conversation-ready delay on Agent Canvas local stack  
**Category**: adaptation  
**Started**: 2026-09-15 16:47:38  
**Pipeline**: 03-implement → verify

---

## Skill: 03-implement

**Root cause**:
- Lean create without MCP: ~0.14s
- Create with MCP stdio handshake: ~2.2s (the real remaining cost)
- Persisted settings used `uv run --with mcp` (extra cold-start risk)
- Home Enter blocked on create before navigate

**Changes**:
1. Rewrite legacy `uv` infra MCP → `python3` (UI + gateway)
2. Patch live settings MCP to python3
3. Parallel settings/secrets fetch; prefetch on Home
4. Home: create without `initial_message`, then send after navigate
5. Home warm-pools one empty conversation on mount

**Verify**: 16 unit tests passed in Docker; gateway rewrite ok; overlay rebuilt.

**Status**: complete
