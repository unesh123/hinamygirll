import type { ActivityStep } from "../components/AgentActivityCard";

export type ToolStatus = ActivityStep["status"];
export type ActivityLane = "reasoning" | "research" | "files" | "media" | "system";

export interface TurnArtifact {
  id: string;
  kind: string;
  label: string;
  path?: string;
  downloadUrl?: string;
  mimeType?: string;
}

export interface PendingToolApproval {
  approvalId: string;
  toolName: string;
  label: string;
  target?: string;
  reason: string;
  argumentsHash?: string;
  scope?: string;
}

export type AgentTurnPhase =
  | "idle"
  | "routing"
  | "thinking"
  | "executing"
  | "awaiting_approval"
  | "streaming"
  | "done"
  | "error"
  | "cancelled";

export type AgentEvent =
  | { type: "turn.started"; turnId: string; route?: string; at?: number }
  | { type: "thought.delta"; text: string; step?: number }
  | { type: "thought.done"; summary?: string; step?: number }
  | {
      type: "tool.started";
      id?: string;
      toolName: string;
      label?: string;
      target?: string;
      lane?: ActivityLane | string;
      parallelGroup?: string;
      step?: number;
      arguments?: Record<string, unknown>;
    }
  | {
      type: "tool.completed" | "tool.finished";
      id?: string;
      toolName?: string;
      label?: string;
      target?: string;
      status?: "ok" | "success" | "err" | "error";
      durationMs?: number;
      step?: number;
    }
  | {
      type: "tool.failed";
      id?: string;
      toolName?: string;
      label?: string;
      target?: string;
      error?: string;
      step?: number;
    }
  | {
      type: "confirmation.required" | "approval.required";
      approval_id?: string;
      approvalId?: string;
      tool?: string;
      toolName?: string;
      label?: string;
      target?: string;
      reason?: string;
      arguments_hash?: string;
      argumentsHash?: string;
      scope?: string;
    }
  | {
      type: "artifact.ready";
      step?: number;
      artifact: Record<string, unknown>;
    }
  | { type: "text.delta" | "token"; text?: string; delta?: string }
  | { type: "turn.done" | "agentic.completed" | "agentic.finalized"; summary?: string; usage?: Record<string, number> }
  | { type: "turn.error" | "agent.run.failed" | "error"; message?: string; summary?: string }
  | { type: "agent.run.cancelled"; summary?: string };

export interface RichActivityStep extends ActivityStep {
  label?: string;
  target?: string;
  lane?: ActivityLane | string;
  parallelGroup?: string;
  durationMs?: number;
  startedAt?: number;
  finishedAt?: number;
}

export interface AgentTurnState {
  phase: AgentTurnPhase;
  runId: string | null;
  route: string | null;
  thought: string;
  thoughtSummary: string | null;
  steps: RichActivityStep[];
  artifacts: TurnArtifact[];
  pendingApproval: PendingToolApproval | null;
  streamedText: string;
  error: string | null;
  usage: Record<string, number> | null;
  startedAt: number | null;
  finishedAt: number | null;
}

export function createInitialAgentTurnState(): AgentTurnState {
  return {
    phase: "idle",
    runId: null,
    route: null,
    thought: "",
    thoughtSummary: null,
    steps: [],
    artifacts: [],
    pendingApproval: null,
    streamedText: "",
    error: null,
    usage: null,
    startedAt: null,
    finishedAt: null,
  };
}

export function formatToolTitle(toolName?: string, explicitLabel?: string, target?: string): string {
  const cleanLabel = (explicitLabel || "").trim();
  const base =
    cleanLabel ||
    (toolName || "Working")
      .replace(/^workspace_/, "")
      .replace(/[_.]+/g, " ")
      .replace(/\b\w/g, (ch) => ch.toUpperCase());
  return target ? `${base} ${target}` : base;
}

function stepMatchIndex(steps: RichActivityStep[], id: string | undefined, toolName: string | undefined, stepNum: number | undefined): number {
  if (id) {
    const byId = steps.findIndex((s) => s.id === id);
    if (byId >= 0) return byId;
  }
  for (let i = steps.length - 1; i >= 0; i--) {
    const s = steps[i];
    if (s.status === "running" && (!toolName || s.toolName === toolName) && (stepNum === undefined || s.stepNumber === stepNum)) {
      return i;
    }
  }
  if (toolName) {
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i].toolName === toolName && steps[i].status === "running") return i;
    }
  }
  return -1;
}

export function reduceAgentTurnEvent(
  state: AgentTurnState,
  raw: Record<string, unknown>,
  now: number = Date.now(),
): AgentTurnState {
  const type = String(raw.type || raw.event_type || "").trim();
  const payload =
    raw.payload && typeof raw.payload === "object"
      ? (raw.payload as Record<string, unknown>)
      : raw;

  switch (type) {
    case "turn.started":
    case "agentic.started": {
      const runId = typeof (payload.turnId ?? payload.runId ?? raw.run_id ?? raw.correlationId) === "string"
        ? String(payload.turnId ?? payload.runId ?? raw.run_id ?? raw.correlationId)
        : state.runId;
      const route = typeof payload.route === "string" ? payload.route : state.route;
      return {
        ...createInitialAgentTurnState(),
        phase: "thinking",
        runId,
        route,
        startedAt: typeof payload.at === "number" ? payload.at : now,
      };
    }

    case "thought.delta": {
      const chunk = String(payload.text ?? payload.delta ?? "");
      if (!chunk) return state;
      const sep = state.thought && !state.thought.endsWith("\n") ? "\n" : "";
      return {
        ...state,
        phase: state.steps.some((s) => s.status === "running") ? "executing" : "thinking",
        thought: `${state.thought}${sep}${chunk}`,
      };
    }

    case "thought.done": {
      const summary = typeof payload.summary === "string" && payload.summary.trim()
        ? payload.summary.trim()
        : state.thoughtSummary;
      return {
        ...state,
        thoughtSummary: summary,
      };
    }

    case "tool.started": {
      const toolName = String(payload.toolName ?? payload.name ?? "tool");
      const label = typeof payload.label === "string" ? payload.label : undefined;
      const target = typeof payload.target === "string" ? payload.target : undefined;
      const stepNum = typeof payload.step === "number" ? payload.step : undefined;
      const parallelGroup = typeof payload.parallelGroup === "string" ? payload.parallelGroup : undefined;
      const lane = typeof payload.lane === "string" ? payload.lane : undefined;
      const id =
        typeof payload.id === "string"
          ? payload.id
          : `tool-${stepNum ?? state.steps.length + 1}-${toolName}-${state.steps.length}`;
      const newStep: RichActivityStep = {
        id,
        toolName,
        label,
        target,
        lane,
        parallelGroup,
        title: formatToolTitle(toolName, label, target),
        status: "running",
        stepNumber: stepNum,
        startedAt: now,
      };
      return {
        ...state,
        phase: "executing",
        steps: [...state.steps, newStep],
      };
    }

    case "tool.completed":
    case "tool.finished": {
      const toolName = typeof payload.toolName === "string" ? payload.toolName : undefined;
      const stepNum = typeof payload.step === "number" ? payload.step : undefined;
      const id = typeof payload.id === "string" ? payload.id : undefined;
      const statusFlag = payload.status === "err" || payload.status === "error" ? "failed" : "completed";
      const idx = stepMatchIndex(state.steps, id, toolName, stepNum);
      if (idx < 0) return state;
      const updated = [...state.steps];
      const target = updated[idx];
      updated[idx] = {
        ...target,
        status: statusFlag,
        durationMs: typeof payload.durationMs === "number" ? payload.durationMs : target.durationMs,
        finishedAt: now,
      };
      return {
        ...state,
        steps: updated,
      };
    }

    case "tool.failed": {
      const toolName = typeof payload.toolName === "string" ? payload.toolName : undefined;
      const stepNum = typeof payload.step === "number" ? payload.step : undefined;
      const id = typeof payload.id === "string" ? payload.id : undefined;
      const idx = stepMatchIndex(state.steps, id, toolName, stepNum);
      if (idx < 0) return state;
      const updated = [...state.steps];
      const target = updated[idx];
      updated[idx] = {
        ...target,
        status: "failed",
        message: typeof payload.error === "string" ? payload.error : target.message,
        finishedAt: now,
      };
      return {
        ...state,
        steps: updated,
      };
    }

    case "confirmation.required":
    case "approval.required": {
      const toolName = String(payload.tool ?? payload.toolName ?? "tool");
      const label = formatToolTitle(
        toolName,
        typeof payload.label === "string" ? payload.label : undefined,
        typeof payload.target === "string" ? payload.target : undefined,
      );
      return {
        ...state,
        phase: "awaiting_approval",
        pendingApproval: {
          approvalId: String(payload.approvalId ?? payload.approval_id ?? `appr-${now}`),
          toolName,
          label,
          target: typeof payload.target === "string" ? payload.target : undefined,
          reason: String(payload.reason ?? "User approval required before running this action."),
          argumentsHash:
            typeof (payload.argumentsHash ?? payload.arguments_hash) === "string"
              ? String(payload.argumentsHash ?? payload.arguments_hash)
              : undefined,
          scope: typeof payload.scope === "string" ? payload.scope : undefined,
        },
      };
    }

    case "artifact.ready": {
      const rawArt = payload.artifact && typeof payload.artifact === "object"
        ? (payload.artifact as Record<string, unknown>)
        : null;
      if (!rawArt) return state;
      const path = typeof rawArt.filePath === "string"
        ? rawArt.filePath
        : typeof rawArt.path === "string"
          ? rawArt.path
          : undefined;
      const downloadUrl = typeof rawArt.download_url === "string"
        ? rawArt.download_url
        : typeof rawArt.url === "string"
          ? rawArt.url
          : undefined;
      const kind = String(rawArt.kind || "file");
      const id = String(rawArt.id || path || downloadUrl || `art-${state.artifacts.length + 1}`);
      if (state.artifacts.some((a) => a.id === id)) return state;
      const label = String(
        rawArt.title ||
          rawArt.name ||
          (path ? path.split(/[\\/]/).pop() : undefined) ||
          kind,
      );
      return {
        ...state,
        artifacts: [
          ...state.artifacts,
          {
            id,
            kind,
            label,
            path,
            downloadUrl,
            mimeType: typeof rawArt.mime_type === "string" ? rawArt.mime_type : undefined,
          },
        ],
      };
    }

    case "text.delta":
    case "token": {
      const delta = String(payload.text ?? payload.delta ?? "");
      if (!delta) return state;
      return {
        ...state,
        phase: "streaming",
        streamedText: state.streamedText + delta,
      };
    }

    case "turn.done":
    case "agentic.completed":
    case "agentic.finalized": {
      return {
        ...state,
        phase: "done",
        pendingApproval: null,
        finishedAt: now,
        usage:
          payload.usage && typeof payload.usage === "object"
            ? (payload.usage as Record<string, number>)
            : state.usage,
      };
    }

    case "agent.run.cancelled": {
      return {
        ...state,
        phase: "cancelled",
        pendingApproval: null,
        finishedAt: now,
      };
    }

    case "turn.error":
    case "agent.run.failed":
    case "error": {
      return {
        ...state,
        phase: "error",
        error: String(payload.message ?? payload.summary ?? payload.error ?? "Execution error"),
        finishedAt: now,
      };
    }

    default:
      return state;
  }
}
