import { useEffect, useRef, useState } from "react";
import {
  Check,
  CircleStop,
  Download,
  ExternalLink,
  Monitor,
  Pause,
  Play,
  Radio,
  RotateCcw,
  ShieldAlert,
  Smartphone,
  X,
} from "lucide-react";

/**
 * Live view of an autonomous loop run (HINAA OS Loop Engineering Harness).
 *
 * Connects to the loop's SSE stream (`GET /api/loop/events/{taskId}`) and
 * renders each turn's thought, applied/blocked actions, live Preview-in-Chat,
 * server-bound Approve/Deny prompts, diff review verdicts, and provider/model
 * telemetry as they arrive.
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
    url?: string;
    site_id?: string;
    brand?: string;
    size_kb?: number;
    archetype?: string;
    screenshots?: string[];
    approval_id?: string;
    tool?: string;
    action?: Record<string, unknown>;
    approved?: boolean;
    severity?: string;
    findings?: string[];
    filename?: string;
    media_id?: string;
    kind?: string;
  };
}

export interface LoopAgentRunPanelProps {
  taskId: string | null;
  /** Called when the stream reports the loop finished or failed. */
  onFinished?: (status: string) => void;
}

interface PreviewState {
  url: string;
  siteId?: string;
  brand?: string;
  sizeKb?: number;
  archetype?: string;
}

interface PendingApprovalState {
  approvalId: string;
  tool: string;
  turn?: number;
  action?: Record<string, unknown>;
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
  preview_ready: "text-cyan-300",
  evidence_captured: "text-indigo-300",
  approval_required: "text-amber-300",
  approval_resolved: "text-emerald-300",
  turn_reviewed: "text-purple-300",
  media_attached: "text-teal-300",
};

export function LoopAgentRunPanel({ taskId, onFinished }: LoopAgentRunPanelProps) {
  const [events, setEvents] = useState<LoopTurnEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [running, setRunning] = useState(true);
  const [acting, setActing] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [previewViewport, setPreviewViewport] = useState<"desktop" | "mobile">("desktop");
  const [pendingApproval, setPendingApproval] = useState<PendingApprovalState | null>(null);
  const [approvalFeedback, setApprovalFeedback] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement | null>(null);
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;

  useEffect(() => {
    setEvents([]);
    setConnected(false);
    setRunning(true);
    setPreview(null);
    setPendingApproval(null);
    setApprovalFeedback(null);
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
        const eventType = event.type || parsed.event_type || "message";
        setEvents((prev) => [
          ...prev,
          { ts: new Date().toISOString(), event_type: eventType, data: payload },
        ]);
        if (eventType === "preview_ready" && payload.url) {
          setPreview({
            url: payload.url,
            siteId: payload.site_id,
            brand: payload.brand,
            sizeKb: payload.size_kb,
            archetype: payload.archetype,
          });
        }
        if (eventType === "approval_required" && payload.approval_id) {
          setApprovalFeedback(null);
          setPendingApproval({
            approvalId: payload.approval_id,
            tool: payload.tool ?? "action",
            turn: payload.turn,
            action: payload.action,
          });
        }
        if (eventType === "approval_resolved") {
          setPendingApproval(null);
        }
        if (eventType === "loop_finished") {
          setPendingApproval(null);
          finishedRef.current?.("COMPLETED");
          setRunning(false);
        }
        if (eventType === "loop_failed") {
          setPendingApproval(null);
          finishedRef.current?.(String(payload.status ?? "FAILED"));
          setRunning(false);
        }
        if (eventType === "loop_paused" || eventType === "loop_cancelled") {
          setPendingApproval(null);
          finishedRef.current?.(String(payload.status ?? "STOPPED"));
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
      "preview_ready",
      "evidence_captured",
      "approval_required",
      "approval_resolved",
      "turn_reviewed",
      "media_attached",
    ]) {
      source.addEventListener(type, handler as EventListener);
    }
    return () => source.close();
  }, [taskId, streamKey]);

  useEffect(() => {
    const feed = feedRef.current;
    if (feed) feed.scrollTop = feed.scrollHeight;
  }, [events.length]);

  const govern = async (action: "stop" | "pause" | "resume") => {
    if (!taskId || acting) return;
    setActing(true);
    try {
      const resp = await fetch(`/api/loop/${action}/${encodeURIComponent(taskId)}`, { method: "POST" });
      if (action === "resume" && resp.ok) {
        setRunning(true);
        setStreamKey((k) => k + 1);
      }
    } finally {
      setActing(false);
    }
  };

  const resolvePendingApproval = async (approved: boolean) => {
    if (!taskId || !pendingApproval || acting) return;
    setActing(true);
    setApprovalFeedback(null);
    try {
      const resp = await fetch(`/api/loop/${encodeURIComponent(taskId)}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: pendingApproval.approvalId, approved }),
      });
      if (!resp.ok) {
        const body = (await resp.json().catch(() => ({}))) as { detail?: string };
        setApprovalFeedback(body.detail || `Approval failed (${resp.status})`);
        return;
      }
      setPendingApproval(null);
    } catch {
      setApprovalFeedback("Network error while sending approval decision.");
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
          {running ? (
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
          ) : (
            <button
              type="button"
              onClick={() => govern("resume")}
              disabled={acting}
              title="Resume this loop run"
              className="flex items-center gap-1 rounded-lg border border-slate-600/60 px-2 py-0.5 text-xs text-cyan-300 hover:bg-slate-800 disabled:opacity-40"
            >
              <RotateCcw size={11} aria-hidden /> Resume
            </button>
          )}
        </span>
      </header>

      {pendingApproval && (
        <div
          role="alert"
          aria-label="Pending tool approval"
          className="mb-2 rounded-lg border border-amber-400/50 bg-amber-950/40 p-2.5 text-xs"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 font-semibold text-amber-200">
              <ShieldAlert size={13} aria-hidden />
              Approval needed · {pendingApproval.tool}
              {pendingApproval.turn !== undefined ? ` · turn ${pendingApproval.turn}` : ""}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => resolvePendingApproval(true)}
                disabled={acting}
                className="flex items-center gap-1 rounded bg-emerald-400 px-2 py-0.5 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:opacity-40"
              >
                <Check size={11} aria-hidden /> Approve
              </button>
              <button
                type="button"
                onClick={() => resolvePendingApproval(false)}
                disabled={acting}
                className="flex items-center gap-1 rounded border border-slate-500 px-2 py-0.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-40"
              >
                <X size={11} aria-hidden /> Deny
              </button>
            </div>
          </div>
          {approvalFeedback && <p className="mt-1 text-[11px] text-rose-300">{approvalFeedback}</p>}
        </div>
      )}

      {preview && (
        <div className="mb-2 rounded-lg border border-cyan-500/40 bg-slate-950/80 p-2">
          <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="font-medium text-cyan-300">
              {preview.brand || "Foundry Preview"}
              {preview.sizeKb !== undefined ? ` · ${preview.sizeKb} KB` : ""}
              {preview.archetype ? ` · ${preview.archetype}` : ""}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setPreviewViewport("desktop")}
                className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] ${
                  previewViewport === "desktop" ? "bg-cyan-500/20 text-cyan-200" : "text-slate-400"
                }`}
              >
                <Monitor size={11} aria-hidden /> 1280px
              </button>
              <button
                type="button"
                onClick={() => setPreviewViewport("mobile")}
                className={`flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] ${
                  previewViewport === "mobile" ? "bg-cyan-500/20 text-cyan-200" : "text-slate-400"
                }`}
              >
                <Smartphone size={11} aria-hidden /> 390px
              </button>
              <a
                href={preview.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 rounded border border-slate-700 px-1.5 py-0.5 text-[11px] text-slate-200 hover:bg-slate-800"
              >
                <ExternalLink size={11} aria-hidden /> Open Tab
              </a>
              {preview.siteId && (
                <a
                  href={`/api/v1/foundry/sites/${encodeURIComponent(preview.siteId)}/download`}
                  download
                  className="flex items-center gap-1 rounded border border-slate-700 px-1.5 py-0.5 text-[11px] text-slate-200 hover:bg-slate-800"
                >
                  <Download size={11} aria-hidden /> ZIP
                </a>
              )}
            </div>
          </div>
          <div className="flex justify-center overflow-hidden rounded bg-slate-900">
            <iframe
              title="Foundry Preview"
              src={preview.url}
              sandbox="allow-scripts"
              style={{ width: previewViewport === "mobile" ? "390px" : "100%", height: "320px", border: 0 }}
            />
          </div>
        </div>
      )}

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
            {event.event_type === "evidence_captured" && event.data.screenshots && (
              <p className="mt-1 text-[11px] text-indigo-300">
                screenshots: {event.data.screenshots.join(" · ")}
              </p>
            )}
            {event.event_type === "turn_reviewed" && (
              <p className={`mt-1 text-[11px] ${event.data.approved ? "text-emerald-300" : "text-amber-300"}`}>
                review {event.data.approved ? "APPROVED" : "CHANGES REQUESTED"}
                {event.data.severity ? ` · severity ${event.data.severity}` : ""}
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
            Run ended. Use Resume or start a new Agent Run to continue.
          </>
        )}
      </footer>
    </section>
  );
}
