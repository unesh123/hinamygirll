import React, { useState, useEffect, useRef } from "react";

export interface CodingTaskEvent {
  run_id: string;
  event_id: string;
  type: string;
  label: string;
  timestamp: string;
  extra?: Record<string, any>;
}

export interface CodingTaskPanelProps {
  taskId?: string;
  onCancel?: (taskId: string) => void;
  onRollback?: (taskId: string) => void;
}

export const CodingTaskPanel: React.FC<CodingTaskPanelProps> = ({
  taskId = "default-task",
  onCancel,
  onRollback,
}) => {
  const [events, setEvents] = useState<CodingTaskEvent[]>([]);
  const [activeModel, setActiveModel] = useState<string>("Analyzing model routing...");
  const [taskState, setTaskState] = useState<string>("INITIALIZING");
  const [diffSummary, setDiffSummary] = useState<string>("");
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [requiresApproval, setRequiresApproval] = useState<boolean>(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!taskId) return;

    // Connect to genuine Server-Sent Events (SSE) stream
    const eventSource = new EventSource(`/api/coding/tasks/${taskId}/events`);

    eventSource.addEventListener("progress", (e: MessageEvent) => {
      try {
        const evt: CodingTaskEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, evt]);
        setIsLoading(false);

        if (evt.type === "model.selected") {
          setActiveModel(evt.label);
        } else if (evt.type === "run.started") {
          setTaskState("RUNNING");
        } else if (evt.type === "run.completed") {
          setTaskState("COMPLETED");
          if (evt.extra?.diff) {
            setDiffSummary(evt.extra.diff);
          }
        } else if (evt.type === "run.failed") {
          setTaskState("FAILED");
        }

        if (evt.extra?.diff) {
          setDiffSummary(evt.extra.diff);
        }
        if (evt.extra?.stdout || evt.extra?.stderr) {
          const log = evt.extra.stdout || evt.extra.stderr;
          setTerminalLogs((prev) => [...prev, log]);
        }
      } catch (err) {
        console.error("Failed parsing coding event:", err);
      }
    });

    eventSource.onerror = () => {
      eventSource.close();
      setIsLoading(false);
    };

    return () => {
      eventSource.close();
    };
  }, [taskId]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [terminalLogs]);

  return (
    <div className="flex flex-col h-full bg-[#151517] text-[#d2d2d4] font-sans border border-[#292a2e] rounded-xl overflow-hidden shadow-2xl">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#1b1c1f] border-b border-[#292a2e]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-gradient-to-tr from-purple-500 to-indigo-500 flex items-center justify-center text-xs font-bold text-white">
            H
          </div>
          <span className="font-semibold text-sm text-gray-200">HINAA Developer Workspace</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-[#242529] text-gray-400 border border-[#38393d]">
            {taskState}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-400">Sandbox:</span>
          <span className="text-emerald-400 font-mono bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
            RESTRICTED_HOST_PROCESS
          </span>
          {onRollback && (
            <button
              onClick={() => onRollback(taskId)}
              className="px-2.5 py-1 bg-[#25262a] hover:bg-[#323338] text-amber-300 rounded border border-[#3e3f45] transition-colors"
            >
              Rollback Edits
            </button>
          )}
          {onCancel && taskState === "RUNNING" && (
            <button
              onClick={() => onCancel(taskId)}
              className="px-2.5 py-1 bg-red-950/40 hover:bg-red-900/40 text-red-300 rounded border border-red-800/40 transition-colors"
            >
              Cancel Task
            </button>
          )}
        </div>
      </div>

      {/* Model & Router Status */}
      <div className="flex items-center gap-2 px-4 py-2 bg-[#18191c] border-b border-[#25262a] text-xs text-gray-400">
        <span className="text-indigo-400 font-bold">◎</span>
        <span>{activeModel}</span>
      </div>

      {/* Main Content Split: Activity Stream & Terminal / Diff */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-[#292a2e] overflow-hidden">
        {/* Left: Activity Status Stream */}
        <div className="flex flex-col p-4 overflow-y-auto space-y-3">
          <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-1">
            Activity Status Stream
          </div>

          {isLoading && events.length === 0 ? (
            /* Skeleton Shimmer Loading Animation */
            <div className="w-full space-y-3 animate-pulse p-2">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-[#202125]" />
                <div className="h-4 w-28 rounded bg-[#202125]" />
              </div>
              <div className="h-4 w-3/4 rounded bg-[#24477f]/40 ml-9" />
              <div className="h-4 w-1/2 rounded bg-[#20365c]/40 ml-9" />
            </div>
          ) : (
            events.map((evt, idx) => (
              <details
                key={evt.event_id || idx}
                open
                className="group border border-[#25262a] rounded-lg bg-[#191a1d] p-3 text-xs"
              >
                <summary className="cursor-pointer font-medium text-gray-300 flex items-center justify-between list-none">
                  <div className="flex items-center gap-2">
                    {evt.type.includes("failed") ? (
                      <span className="text-rose-400 font-bold">✗</span>
                    ) : evt.type.includes("completed") || evt.type.includes("ready") ? (
                      <span className="text-emerald-400 font-bold">✓</span>
                    ) : (
                      <span className="w-3 h-3 rounded-full border border-gray-500 border-t-transparent animate-spin inline-block" />
                    )}
                    <span>{evt.label}</span>
                  </div>
                  <span className="text-gray-500 font-mono text-[10px]">
                    {new Date(evt.timestamp).toLocaleTimeString()}
                  </span>
                </summary>

                {evt.extra && Object.keys(evt.extra).length > 0 && (
                  <div className="mt-2 pl-5 pt-2 border-t border-[#232428] text-gray-400 space-y-1">
                    {evt.extra.tool && (
                      <div className="flex gap-2">
                        <span className="text-gray-500">Tool:</span>
                        <span className="text-gray-200 font-mono bg-[#202125] px-1.5 py-0.5 rounded">
                          {evt.extra.tool}
                        </span>
                      </div>
                    )}
                    {evt.extra.command && (
                      <div className="text-gray-300 font-mono bg-[#111214] p-1.5 rounded text-[11px] overflow-x-auto">
                        $ {Array.isArray(evt.extra.command) ? evt.extra.command.join(" ") : evt.extra.command}
                      </div>
                    )}
                    {evt.extra.error && (
                      <div className="text-rose-400 bg-rose-950/20 border border-rose-900/30 p-2 rounded">
                        {evt.extra.error}
                      </div>
                    )}
                  </div>
                )}
              </details>
            ))
          )}
        </div>

        {/* Right: Unified Diff Viewer & Terminal */}
        <div className="flex flex-col h-full bg-[#111214]">
          {/* Section: Diff Viewer */}
          {diffSummary ? (
            <div className="flex-1 flex flex-col border-b border-[#292a2e] overflow-hidden">
              <div className="px-3 py-2 bg-[#18191c] text-xs font-semibold text-gray-300 border-b border-[#25262a] flex justify-between">
                <span>Verified Code Patch (Diff)</span>
                <span className="text-emerald-400 text-[11px]">Ready for Review</span>
              </div>
              <pre className="flex-1 p-3 font-mono text-xs overflow-auto text-gray-300 bg-[#0d0e10]">
                {diffSummary.split("\n").map((line, i) => {
                  let color = "text-gray-400";
                  if (line.startsWith("+") && !line.startsWith("+++")) color = "text-emerald-400 bg-emerald-950/20";
                  if (line.startsWith("-") && !line.startsWith("---")) color = "text-rose-400 bg-rose-950/20";
                  if (line.startsWith("@")) color = "text-indigo-400 font-bold";
                  return (
                    <div key={i} className={`${color} px-1 leading-5 whitespace-pre`}>
                      {line}
                    </div>
                  );
                })}
              </pre>
            </div>
          ) : null}

          {/* Section: Terminal Logs */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-3 py-2 bg-[#18191c] text-xs font-semibold text-gray-300 border-b border-[#25262a] flex justify-between">
              <span>Terminal & Build Execution</span>
              <span className="text-gray-500 font-mono text-[11px]">stdout/stderr</span>
            </div>
            <div
              ref={terminalRef}
              className="flex-1 p-3 font-mono text-xs overflow-y-auto bg-[#0a0a0c] text-gray-300 space-y-1"
            >
              {terminalLogs.length === 0 ? (
                <div className="text-gray-600 italic">No command output yet. Sandbox idle.</div>
              ) : (
                terminalLogs.map((log, i) => (
                  <div key={i} className="whitespace-pre-wrap leading-relaxed">
                    {log}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
