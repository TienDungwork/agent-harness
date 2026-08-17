export type CreanovaEventType =
  | "message"
  | "system"
  | "agent_state_changed"
  | "change_agent_state"
  | "run"
  | "read"
  | "write"
  | "edit"
  | "run_ipython"
  | "delegate"
  | "browse"
  | "browse_interactive"
  | "reject"
  | "think"
  | "finish"
  | "error"
  | "recall"
  | "mcp"
  | "call_tool_mcp"
  | "task_tracking"
  | "user_rejected";

export type CreanovaSourceType = "agent" | "user" | "environment" | "hook";

interface CreanovaBaseEvent {
  id: number;
  source: CreanovaSourceType;
  message: string;
  timestamp: string; // ISO 8601
}

export interface CreanovaActionEvent<
  T extends CreanovaEventType,
> extends CreanovaBaseEvent {
  action: T;
  args: Record<string, unknown>;
}

export interface CreanovaObservationEvent<
  T extends CreanovaEventType,
> extends CreanovaBaseEvent {
  cause: number;
  observation: T;
  content: string;
  extras: Record<string, unknown>;
}
