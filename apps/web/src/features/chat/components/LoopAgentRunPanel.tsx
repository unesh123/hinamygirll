import { useEffect, useRef, useState } from "react";
import { Radio, CircleStop, Pause, Play } from "lucide-react";

/**
 * Live view of an autonomous loop run (HINAA OS Loop Engineering Harness).
 *
 * Connects to the loop's SSE stream (`GET /api/loop/events/{taskId}`) and
 * renders each turn's thought, applied/blocked actions and provider/model
 * telemetry as they arrive. Mirrors the EventSource pattern already used by
 * AgentOrchestrationPanel, CodingTaskPanel and CreativeStudioPanel.
 */

export interface LoopTurnEvent {
  ts: string;
  event_type: string;
  data: {
    turn?: number;
    thought?: string;
    provider?: string;
    model?: string;
    latency_ms?: number;
    input_tokens?: number;
    output_tokens?: number;
    actions_applied?: number;
    actions_blocked?: number;
    status?: string;
    summary?: string;
    error?: string;
    agent_mode?: string;
    goal_title?: string;
    total_turns?: number;
    passed?: boolean;
    exit_code?: number | null;
    command?: string | null;
    stdout_snippet?: string;
    stderr_snippet?: string;
    duration_ms?: number;
    files_changed?: string[];
  };
}

export interface LoopAgentRunPanelProps {
  taskId: string | null;
  /** Called when the stream reports the loop finished or failed. */
  onFinished?: (status: string) => void;
}

const EVENT_COLORS: Record<string, string> = {
  loop_started: "text-sky-300",
  turn_completed: "text-emerald-300",
  turn_failed: "text-rose-300",
  loop_finished: "text-emerald-300",
  loop_failed: "text-rose-300",
  turn_verified: "text-amber-300",
  loop_paused: "text-amber-300",
  loop_cancelled: "text-slate-300",
};

export function LoopAgentRunPanel({ taskId, onFinished }: LoopAgentRunPanelProps) {
  const [events, setEvents] = useState<LoopTurnEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [running, setRunning] = useState(true);
  const [acting, setActing] = useState(false);
  const feedRef = useRef<HTMLDivElement | null>(null);
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;

  useEffect(() => {
    setEvents([]);
    setConnected(false);
    setRunning(true);
    if (!taskId) return;

    const source = new EventSource(`/api/loop/events/${encodeURIComponent(taskId)}`);
    source.onopen = () => setConnected(true);

    const handler = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data) as LoopTurnEvent["data"] & {
          event_type?: string;
          data?: LoopTurnEvent["data"];
        };
        // SSE frames carry the full envelope {ts, event_type, data}; unwrap it
        // so the payload fields (turn, passed, provider, …) are at top level.
        const payload = (parsed.data && parsed.event_type ? parsed.data : parsed) as LoopTurnEvent["data"];
        setEvents((prev) => [
          ...prev,
          { ts: new Date().toISOString(), event_type: event.type || parsed.event_type || "message", data: payload },
        ]);
        if (event.type === "loop_finished") {
          finishedRef.current?.("COMPLETED");
          setRunning(false);
        }
        if (event.type === "loop_failed") {
          finishedRef.current?.(String(parsed.status ?? "FAILED"));
          setRunning(false);
        }
        if (event.type === "loop_paused" || event.type === "loop_cancelled") {
          finishedRef.current?.(String(parsed.status ?? "STOPPED"));
          setRunning(false);
        }
      } catch {
        // keep-alive comments and malformed frames are ignored
      }
    };
    for (const type of [
      "loop_started",
      "turn_completed",
      "turn_failed",
      "turn_verified",
      "loop_finished",
      "loop_failed",
      "loop_paused",
      "loop_cancelled",
    ]) {
      source.addEventListener(type, handler as EventListener);
    }
    return () => source.close();
  }, [taskId]);

  useEffect(() => {
    const feed = feedRef.current;
    if (feed) feed.scrollTop = feed.scrollHeight;
  }, [events.length]);

  const govern = async (action: "stop" | "pause") => {
    if (!taskId || acting) return;
    setActing(true);
    try {
      await fetch(`/api/loop/${action}/${encodeURIComponent(taskId)}`, { method: "POST" });
    } finally {
      setActing(false);
    }
  };

  if (!taskId) return null;

  return (
    <section
      aria-label="Agent run live feed"
      className="rounded-xl border border-slate-700/60 bg-slate-900/70 p-3 text-sm text-slate-200"
    >
      <header className="mb-2 flex items-center justify-between">
        <span className="flex items-center gap-2 font-medium">
          <Radio size={14} className={connected ? "text-emerald-400" : "text-slate-500"} aria-hidden />
          Agent run · {taskId}
        </span>
        <span className="flex items-center gap-2">
          {connected ? (
            <span className="text-xs text-emerald-400">live</span>
          ) : (
            <span className="text-xs text-slate-500">connecting…</span>
          )}
          {running && (
            <span className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => govern("pause")}
                disabled={acting}
                title="Pause the loop after the current turn"
                className="flex items-center gap-1 rounded-lg border border-slate-600/60 px-2 py-0.5 text-xs text-amber-300 hover:bg-slate-800 disabled:opacity-40"
              >
                <Pause size={11} aria-hidden /> Pause
              </button>
              <button
                type="button"
                onClick={() => govern("stop")}
                disabled={acting}
                title="Stop the loop now"
                className="flex items-center gap-1 rounded-lg border border-slate-600/60 px-2 py-0.5 text-xs text-rose-300 hover:bg-slate-800 disabled:opacity-40"
              >
                <CircleStop size={11} aria-hidden /> Stop
              </button>
            </span>
          )}
        </span>
      </header>
      <div ref={feedRef} className="max-h-64 space-y-2 overflow-y-auto pr-1">
        {events.length === 0 && (
          <p className="text-xs text-slate-400">Waiting for the first turn…</p>
        )}
        {events.map((event, index) => (
          <article key={index} className="rounded-lg bg-slate-800/60 p-2">
            <p className={`text-xs font-semibold ${EVENT_COLORS[event.event_type] ?? "text-slate-300"}`}>
              {event.event_type.replace(/_/g, " ")}
              {event.data.turn !== undefined ? ` · turn ${event.data.turn}` : ""}
            </p>
            {event.data.thought && <p className="mt-1 text-xs">{event.data.thought}</p>}
            {event.data.summary && <p className="mt-1 text-xs text-slate-300">{event.data.summary}</p>}
            {event.event_type === "turn_verified" && (
              <p className={`mt-1 text-[11px] ${event.data.passed ? "text-emerald-300" : "text-rose-300"}`}>
                gate {event.data.passed ? "PASSED" : "FAILED"}
                {event.data.exit_code !== null && event.data.exit_code !== undefined ? ` · exit ${event.data.exit_code}` : ""}
                {event.data.command ? ` · ${event.data.command}` : ""}
                {event.data.files_changed && event.data.files_changed.length > 0
                  ? ` · touched ${event.data.files_changed.join(", ")}`
                  : ""}
              </p>
            )}
            {(event.data.provider || event.data.latency_ms !== undefined) && (
              <p className="mt-1 text-[11px] text-slate-400">
                {event.data.provider}
                {event.data.model ? ` · ${event.data.model}` : ""}
                {event.data.latency_ms !== undefined ? ` · ${event.data.latency_ms} ms` : ""}
                {event.data.input_tokens ? ` · ${event.data.input_tokens} in` : ""}
                {event.data.output_tokens ? ` · ${event.data.output_tokens} out` : ""}
              </p>
            )}
            {(event.data.actions_applied !== undefined || event.data.actions_blocked !== undefined) && (
              <p className="mt-1 text-[11px] text-slate-400">
                {event.data.actions_applied ?? 0} applied · {event.data.actions_blocked ?? 0} blocked
              </p>
            )}
            {event.data.error && <p className="mt-1 text-[11px] text-rose-300">{event.data.error}</p>}
          </article>
        ))}
      </div>
      <footer className="mt-2 flex items-center gap-1 text-[11px] text-slate-500">
        {running ? (
          <>
            <Pause size={12} aria-hidden />
            Pause stops after the current turn; Stop cancels immediately. Commands stay disabled unless enabled.
          </>
        ) : (
          <>
            <Play size={12} aria-hidden />
            Run ended. Start a new Agent Run to continue with the same goal.
          </>
        )}
      </footer>
    </section>
  );
}
