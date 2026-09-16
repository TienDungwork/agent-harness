"""After MCP returns ``reply_vi``, finish without a second LLM retype.

Also recover when Ollama writes Qwen-style ``<tool_call>{json}</tool_call>``
as plain text instead of native function-calling (UI would otherwise freeze
on the raw XML and never run MCP).

No hardcoded intent→tool routing — only execute what the model already named.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from typing import Any

logger = logging.getLogger("agent-canvas.vms_reply_vi")

# Embedded in assistant MessageEvent text so the UI can render the chart even
# when ObservationEvent content is collapsed / not walked. Stripped from display.
_VMS_CHART_MARK = "<!--CREANOVA_VMS_CHART:"
_VMS_CHART_END = "-->"
# Fake token stream pacing. Must use asyncio.sleep on async path so the
# event loop can flush WebSocket pub_sub between chunks (time.sleep blocks
# the loop → UI only sees the final MessageEvent).
_STREAM_CHUNK_SLEEP = 0.045
_STREAM_CHUNK_CHARS = 12

_PATCH_ATTR = "_creanova_vms_reply_vi_finish"
_COUNT_NL_RE = re.compile(
    r'([đd][ếe]m|bao\s*nhi[êe]u|s[ốo]\s*(?:lư[ợo]ng\s*)?xe|lư[ợo]t\s*bi[ểe]n|'
    r'g[ầa]n\s*nh[ấa]t|ngày\s*g[ầa]n|ra\s*vào|xâm\s*nhập|hãng|truy\s*vết|'
    r'[ôo]\s*t[ôo]|xe\s*m[áa]y|ph[ưư][ơơ]ng\s*ti[ệe]n)',
    re.I,
)
_PLATE_NL_RE = re.compile(
    r'(?<![A-Z0-9])(\d{1,3}[A-Z]{1,3}-?\d{3,6})(?![A-Z0-9])',
    re.I,
)
# Qwen / Ollama text tool-call (not OpenAI native tool_calls).
_TOOL_CALL_XML_RE = re.compile(
    r'<tool_call>\s*(\{.*?\})\s*</tool_call>',
    re.I | re.S,
)
_FUNCTION_XML_RE = re.compile(
    r'<function=([a-z0-9_]+)>\s*(.*?)\s*</function>',
    re.I | re.S,
)
_PARAM_XML_RE = re.compile(
    r'<parameter=([a-z0-9_]+)>\s*(.*?)\s*</parameter>',
    re.I | re.S,
)


def _needs_mcp_tools(text: str) -> bool:
    if not text:
        return False
    if _COUNT_NL_RE.search(text) or _PLATE_NL_RE.search(text):
        return True
    return False


def _message_text(msg: object) -> str:
    parts: list[str] = []
    for c in getattr(msg, "content", None) or []:
        t = getattr(c, "text", None)
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def _parse_text_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """Return (tool_name, args) from Qwen/Ollama text tool-call markup."""
    if not text or "<tool_call>" not in text.lower() and "<function=" not in text.lower():
        return None
    m = _TOOL_CALL_XML_RE.search(text)
    if m:
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            name = str(data.get("name") or "").strip()
            args = data.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            if name:
                return name, args
    m2 = _FUNCTION_XML_RE.search(text)
    if m2:
        name = m2.group(1).strip()
        args: dict[str, Any] = {}
        for pm in _PARAM_XML_RE.finditer(m2.group(2) or ""):
            key = pm.group(1)
            raw = (pm.group(2) or "").strip()
            if re.fullmatch(r'-?\d+', raw):
                args[key] = int(raw)
            else:
                args[key] = raw
        if name:
            return name, args
    return None


def _reply_from_blob(text: str) -> str | None:
    text = (text or "").strip()
    if not text or "reply_vi" not in text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            reply = data.get("reply_vi")
            if isinstance(reply, str) and reply.strip():
                return reply.strip()
    except json.JSONDecodeError:
        pass
    m = re.search(r'"reply_vi"\s*:\s*"((?:\\.|[^"\\])*)"', text)
    if m:
        try:
            return json.loads(f'"{m.group(1)}"')
        except json.JSONDecodeError:
            return m.group(1).replace("\\n", "\n")
    return None


def _observation_text_blobs(observation: object) -> list[str]:
    if observation is None:
        return []
    candidates: list[str] = []
    text = getattr(observation, "text", None) or ""
    if text:
        candidates.append(text)
    if hasattr(observation, "content"):
        for item in observation.content or []:
            t = getattr(item, "text", None)
            if t:
                candidates.append(t)
    return candidates


def _extract_reply_vi(observation: object) -> str | None:
    candidates = _observation_text_blobs(observation)
    for blob in candidates:
        reply = _reply_from_blob(blob)
        if reply:
            return reply
    if len(candidates) > 1:
        return _reply_from_blob("\n".join(candidates))
    return None


def _extract_chart(observation: object) -> dict[str, Any] | None:
    for blob in _observation_text_blobs(observation):
        text = (blob or "").strip()
        if not text or "chart" not in text:
            continue
        try:
            if text.startswith("{"):
                data = json.loads(text)
            else:
                m = re.search(r"\{[\s\S]*\"chart\"\s*:[\s\S]*\}", text)
                data = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            chart = data.get("chart")
            if isinstance(chart, dict) and chart.get("type") and chart.get("data") is not None:
                return chart
    return None


def _embed_chart(reply: str, chart: dict[str, Any] | None) -> str:
    if not chart:
        return reply
    payload = json.dumps(chart, ensure_ascii=False, separators=(",", ":"))
    return f"{reply.rstrip()}\n\n{_VMS_CHART_MARK}{payload}{_VMS_CHART_END}"


def _iter_reply_chunks(reply: str):
    if not reply:
        return
    i = 0
    n = len(reply)
    while i < n:
        end = min(i + _STREAM_CHUNK_CHARS, n)
        if end < n:
            space = reply.rfind(" ", i, end + 6)
            newline = reply.rfind("\n", i, end + 6)
            break_at = max(space, newline)
            if break_at > i:
                end = break_at + 1
        chunk = reply[i:end]
        i = end
        if chunk:
            yield chunk


def _stream_reply_deltas(
    on_event: Any,
    reply: str,
    *,
    StreamingDeltaEvent: type,
) -> None:
    """Sync path: sleep between chunks (OK off the asyncio loop)."""
    for chunk in _iter_reply_chunks(reply):
        on_event(
            StreamingDeltaEvent(
                source="agent",
                content=chunk,
                reasoning_content=None,
            )
        )
        time.sleep(_STREAM_CHUNK_SLEEP)


async def _astream_reply_deltas(
    on_event: Any,
    reply: str,
    *,
    StreamingDeltaEvent: type,
) -> None:
    """Async path: await sleep so WS subscribers flush between chunks."""
    import asyncio

    for chunk in _iter_reply_chunks(reply):
        on_event(
            StreamingDeltaEvent(
                source="agent",
                content=chunk,
                reasoning_content=None,
            )
        )
        await asyncio.sleep(_STREAM_CHUNK_SLEEP)


def _last_user_text(conversation: Any) -> tuple[str | None, str | None]:
    try:
        events = list(conversation.state.events)
    except Exception:  # noqa: BLE001
        return None, None
    for ev in reversed(events):
        if getattr(ev, "kind", None) != "MessageEvent" and type(ev).__name__ != "MessageEvent":
            continue
        if getattr(ev, "source", None) != "user":
            continue
        msg = getattr(ev, "llm_message", None)
        text = _message_text(msg) if msg is not None else ""
        return getattr(ev, "id", None), text
    return None, None


def _resolve_tool_name(tools_map: dict[str, Any], want: str) -> str | None:
    if want in tools_map:
        return want
    for name in tools_map:
        if name.endswith(want) or want in name:
            return name
    return None


def _finish_with_reply(
    conversation: Any,
    on_event: Any,
    captured: list[object],
    *,
    MessageEvent: type,
    ObservationEvent: type,
    Message: type,
    TextContent: type,
    ConversationExecutionStatus: type,
    StreamingDeltaEvent: type | None = None,
) -> bool:
    for ev in captured:
        if not isinstance(ev, ObservationEvent):
            continue
        observation = getattr(ev, "observation", None)
        reply = _extract_reply_vi(observation)
        if not reply:
            continue
        chart = _extract_chart(observation)
        final_text = _embed_chart(reply, chart)
        logger.info(
            "VMS reply_vi short-circuit (%d chars, chart=%s) — skip second LLM turn",
            len(reply),
            bool(chart),
        )
        if StreamingDeltaEvent is not None:
            try:
                _stream_reply_deltas(
                    on_event, reply, StreamingDeltaEvent=StreamingDeltaEvent
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("VMS stream deltas failed: %s", exc)
        on_event(
            MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[TextContent(text=final_text)],
                ),
            )
        )
        conversation.state.execution_status = ConversationExecutionStatus.FINISHED
        print(
            "[agent-canvas] vms_reply_vi: finished without second LLM",
            file=sys.stderr,
        )
        return True
    return False


async def _afinish_with_reply(
    conversation: Any,
    on_event: Any,
    captured: list[object],
    *,
    MessageEvent: type,
    ObservationEvent: type,
    Message: type,
    TextContent: type,
    ConversationExecutionStatus: type,
    StreamingDeltaEvent: type | None = None,
) -> bool:
    """Like _finish_with_reply but awaits between deltas (does not block the loop)."""
    for ev in captured:
        if not isinstance(ev, ObservationEvent):
            continue
        observation = getattr(ev, "observation", None)
        reply = _extract_reply_vi(observation)
        if not reply:
            continue
        chart = _extract_chart(observation)
        final_text = _embed_chart(reply, chart)
        logger.info(
            "VMS reply_vi async short-circuit (%d chars, chart=%s)",
            len(reply),
            bool(chart),
        )
        if StreamingDeltaEvent is not None:
            try:
                await _astream_reply_deltas(
                    on_event, reply, StreamingDeltaEvent=StreamingDeltaEvent
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("VMS async stream deltas failed: %s", exc)
        on_event(
            MessageEvent(
                source="agent",
                llm_message=Message(
                    role="assistant",
                    content=[TextContent(text=final_text)],
                ),
            )
        )
        conversation.state.execution_status = ConversationExecutionStatus.FINISHED
        print(
            "[agent-canvas] vms_reply_vi: finished without second LLM (async)",
            file=sys.stderr,
        )
        return True
    return False


def apply_runtime_monkeypatch() -> int:
    try:
        from openhands.sdk.agent.agent import Agent
        from openhands.sdk.conversation.state import ConversationExecutionStatus
        from openhands.sdk.event import (
            ActionEvent,
            MessageEvent,
            ObservationEvent,
            StreamingDeltaEvent,
        )
        from openhands.sdk.llm import Message, TextContent
        from openhands.sdk.mcp.definition import MCPToolAction
    except ImportError:
        try:
            from Creanova.sdk.agent.agent import Agent
            from Creanova.sdk.conversation.state import ConversationExecutionStatus
            from Creanova.sdk.event import (
                ActionEvent,
                MessageEvent,
                ObservationEvent,
                StreamingDeltaEvent,
            )
            from Creanova.sdk.llm import Message, TextContent
            from Creanova.sdk.mcp.definition import MCPToolAction
        except ImportError as exc:
            print(
                f"[agent-canvas] vms_reply_vi patch: import failed: {exc}",
                file=sys.stderr,
            )
            return 0

    if getattr(Agent.step, _PATCH_ATTR, False):
        return 0

    original_step = Agent.step
    original_async_step = getattr(Agent, "astep", None)
    original_sync_exec = Agent._execute_actions
    original_async_exec = Agent._aexecute_actions

    def _execute_actions(self, conversation, pending_actions, on_event):  # type: ignore[no-untyped-def]
        captured: list[object] = []

        def _wrap(ev: object) -> None:
            captured.append(ev)
            on_event(ev)

        original_sync_exec(self, conversation, pending_actions, _wrap)
        _finish_with_reply(
            conversation,
            on_event,
            captured,
            MessageEvent=MessageEvent,
            ObservationEvent=ObservationEvent,
            Message=Message,
            TextContent=TextContent,
            ConversationExecutionStatus=ConversationExecutionStatus,
            StreamingDeltaEvent=StreamingDeltaEvent,
        )

    async def _aexecute_actions(self, conversation, pending_actions, on_event):  # type: ignore[no-untyped-def]
        captured: list[object] = []

        def _wrap(ev: object) -> None:
            captured.append(ev)
            on_event(ev)

        await original_async_exec(self, conversation, pending_actions, _wrap)
        await _afinish_with_reply(
            conversation,
            on_event,
            captured,
            MessageEvent=MessageEvent,
            ObservationEvent=ObservationEvent,
            Message=Message,
            TextContent=TextContent,
            ConversationExecutionStatus=ConversationExecutionStatus,
            StreamingDeltaEvent=StreamingDeltaEvent,
        )

    def _run_parsed_tool(
        self, conversation, on_event, tool_want: str, args: dict[str, Any]
    ) -> bool:
        tool_name = _resolve_tool_name(self.tools_map, tool_want)
        if not tool_name:
            logger.warning("text tool_call: tool %s not loaded", tool_want)
            return False
        # Drop unknown / ignored params that confuse MCP schemas.
        if "summary" in args:
            args = {k: v for k, v in args.items() if k != "summary"}
        call_id = f"text_tc_{uuid.uuid4().hex[:10]}"
        action_event = ActionEvent(
            source="agent",
            thought=[TextContent(text="")],
            action=MCPToolAction(data=args),
            tool_name=tool_name,
            tool_call_id=call_id,
            tool_call={
                "id": call_id,
                "name": tool_name,
                "arguments": json.dumps(args, ensure_ascii=False),
                "origin": "completion",
            },
            llm_response_id=f"text_tc_{uuid.uuid4().hex[:8]}",
        )
        print(
            f"[agent-canvas] text_tool_call→MCP: {tool_name} {args}",
            file=sys.stderr,
        )
        on_event(action_event)
        self._execute_actions(conversation, [action_event], on_event)
        return True

    def _wrap_step_callbacks(self, conversation, on_event, on_token, runner):  # type: ignore[no-untyped-def]
        """Run agent step; if model emits text <tool_call>, execute it as MCP."""
        pending: list[tuple[str, dict[str, Any]]] = []

        def filtered(ev: object) -> None:
            if isinstance(ev, MessageEvent) and getattr(ev, "source", None) == "agent":
                msg = getattr(ev, "llm_message", None)
                text = _message_text(msg) if msg is not None else ""
                parsed = _parse_text_tool_call(text)
                if parsed:
                    pending.append(parsed)
                    # Do not show raw <tool_call> XML in the UI.
                    return
            on_event(ev)

        result = runner(self, conversation, filtered, on_token)
        if pending:
            tool_want, args = pending[-1]
            if _run_parsed_tool(self, conversation, on_event, tool_want, args):
                return result
            # Fallback: surface the raw message if tool missing.
            on_event(
                MessageEvent(
                    source="agent",
                    llm_message=Message(
                        role="assistant",
                        content=[
                            TextContent(
                                text=f"Không tìm thấy tool `{tool_want}`."
                            )
                        ],
                    ),
                )
            )
            conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )
        return result

    def step(self, conversation, on_event, on_token=None):  # type: ignore[no-untyped-def]
        _, text = _last_user_text(conversation)
        if text and not _needs_mcp_tools(text) and hasattr(self, "_tools"):
            full = dict(self._tools)
            self._tools = {}
            try:
                return _wrap_step_callbacks(
                    self, conversation, on_event, on_token, original_step
                )
            finally:
                self._tools = full
        return _wrap_step_callbacks(
            self, conversation, on_event, on_token, original_step
        )

    async def astep(self, conversation, on_event, on_token=None):  # type: ignore[no-untyped-def]
        async def _async_runner(agent, conv, cb, tok):
            if original_async_step is None:
                return original_step(agent, conv, cb, tok)
            return await original_async_step(agent, conv, cb, tok)

        _, text = _last_user_text(conversation)
        if text and not _needs_mcp_tools(text) and hasattr(self, "_tools"):
            full = dict(self._tools)
            self._tools = {}
            try:
                return await _wrap_step_callbacks_async(
                    self, conversation, on_event, on_token, _async_runner
                )
            finally:
                self._tools = full
        return await _wrap_step_callbacks_async(
            self, conversation, on_event, on_token, _async_runner
        )

    async def _wrap_step_callbacks_async(self, conversation, on_event, on_token, runner):  # type: ignore[no-untyped-def]
        pending: list[tuple[str, dict[str, Any]]] = []

        def filtered(ev: object) -> None:
            if isinstance(ev, MessageEvent) and getattr(ev, "source", None) == "agent":
                msg = getattr(ev, "llm_message", None)
                text = _message_text(msg) if msg is not None else ""
                parsed = _parse_text_tool_call(text)
                if parsed:
                    pending.append(parsed)
                    return
            on_event(ev)

        result = await runner(self, conversation, filtered, on_token)
        if pending:
            tool_want, args = pending[-1]
            if _run_parsed_tool(self, conversation, on_event, tool_want, args):
                return result
            on_event(
                MessageEvent(
                    source="agent",
                    llm_message=Message(
                        role="assistant",
                        content=[
                            TextContent(
                                text=f"Không tìm thấy tool `{tool_want}`."
                            )
                        ],
                    ),
                )
            )
            conversation.state.execution_status = (
                ConversationExecutionStatus.FINISHED
            )
        return result

    setattr(step, _PATCH_ATTR, True)
    Agent.step = step  # type: ignore[method-assign]
    if original_async_step is not None:
        Agent.astep = astep  # type: ignore[method-assign]
    Agent._execute_actions = _execute_actions  # type: ignore[method-assign]
    Agent._aexecute_actions = _aexecute_actions  # type: ignore[method-assign]
    print(
        "[agent-canvas] vms_reply_vi + text_tool_call recovery applied",
        file=sys.stderr,
    )
    return 1


try:
    apply_runtime_monkeypatch()
except Exception as exc:  # pragma: no cover
    print(f"[agent-canvas] vms_reply_vi patch failed: {exc}", file=sys.stderr)
