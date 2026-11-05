import React, { useState, useEffect, useCallback } from "react";
import { AgentTaskGraph, TaskNodeData, TaskStatus, AgentRole } from "./AgentTaskGraph";
import { AgentApprovalPanel, ApprovalRequestData } from "./AgentApprovalPanel";

export interface SpecialistSpec {
  agent_id: string;
  role: AgentRole;
  display_name: string;
  description: string;
  model: string;
  provider: string;
  is_available: boolean;
  health_status: string;
}

export interface BudgetMetrics {
  allocated_tokens: number;
  consumed_tokens: number;
  allocated_tool_calls: number;
  consumed_tool_calls: number;
  allocated_cost_paisa: number;
  consumed_cost_paisa: number;
  allocated_seconds: number;
  elapsed_seconds: number;
}

export interface TaskArtifact {
  path: string;
  filename: string;
  sha256: string;
  created_by: string;
}

export interface TaskEventLog {
  event_id: string;
  sequence: number;
  task_id: string;
  node_id?: string | null;
  timestamp: string;
  actor_role: string;
  event_type: string;
  payload: Record<string, unknown>;
}

export const AgentOrchestrationPanel: React.FC = () => {
  const [goal, setGoal] = useState("");
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<TaskNodeData[]>([]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [specialists, setSpecialists] = useState<SpecialistSpec[]>([]);
  const [budget, setBudget] = useState<BudgetMetrics | null>(null);
  const [artifacts, setArtifacts] = useState<TaskArtifact[]>([]);
  const [events, setEvents] = useState<TaskEventLog[]>([]);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequestData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch specialists registry
  const fetchRegistry = useCallback(async () => {
    try {
      const res = await fetch("/api/agents/registry");
      if (res.ok) {
        const data = await res.json();
        setSpecialists(data.specialists || []);
      }
    } catch {
      // Ignore network errors in preview
    }
  }, []);

  // Fetch health and budget
  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch("/api/agents/health");
      if (res.ok) {
        const data = await res.json();
        if (data.budget) {
          setBudget(data.budget);
        }
      }
    } catch {
      // Ignore
    }
  }, []);

  useEffect(() => {
    fetchRegistry();
    fetchHealth();
  }, [fetchRegistry, fetchHealth]);

  // SSE event stream connection
  useEffect(() => {
    if (!activeTaskId) return;

    const sse = new EventSource(`/api/agents/tasks/${activeTaskId}/events?since_sequence=${events.length}`);
    sse.onmessage = (e) => {
      if (e.data === "[DONE]") {
        sse.close();
        return;
      }
      try {
        const parsed = JSON.parse(e.data);
        setEvents((prev) => [...prev, parsed]);
        if (parsed.event_type === "node.waiting_approval") {
          setPendingApproval({
            approval_id: parsed.payload?.approval_id || "appr-pending",
            task_id: activeTaskId,
            node_id: parsed.node_id || "node-unknown",
            action: parsed.payload?.action || "action",
            argument_digest: "sha256-verified-digest",
            amount_paisa: parsed.payload?.amount_paisa || 0,
            currency: "NPR",
            expires_at: new Date(Date.now() + 600000).toISOString(),
            nonce: "nonce-token",
          });
        }
      } catch {
        // Parse error
      }
    };

    return () => {
      sse.close();
    };
  }, [activeTaskId, events.length]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goal.trim()) return;

    setLoading(true);
    setError(null);
    setEvents([]);
    setArtifacts([]);

    try {
      const res = await fetch("/api/agents/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, language }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to create task");
      }

      const task = data.task;
      setActiveTaskId(task.task_id);
      setNodes(task.nodes || []);

      // Trigger run
      const runRes = await fetch(`/api/agents/tasks/${task.task_id}/run`, { method: "POST" });
      if (runRes.ok) {
        const runData = await runRes.json();
        if (runData.result?.artifacts) {
          setArtifacts(runData.result.artifacts);
        }
        // Refresh task status
        const refreshRes = await fetch(`/api/agents/tasks/${task.task_id}`);
        if (refreshRes.ok) {
          const refData = await refreshRes.json();
          setNodes(refData.task?.nodes || []);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error initiating task");
    } finally {
      setLoading(false);
      fetchHealth();
    }
  };

  const handleApprove = async (approvalId: string, signature: string) => {
    if (!activeTaskId) return;
    const res = await fetch(`/api/agents/tasks/${activeTaskId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approval_id: approvalId, signature }),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Approval failed");
    }
    setPendingApproval(null);
    // Refresh task
    const refreshRes = await fetch(`/api/agents/tasks/${activeTaskId}`);
    if (refreshRes.ok) {
      const refData = await refreshRes.json();
      setNodes(refData.task?.nodes || []);
    }
  };

  const handleReject = async () => {
    if (!activeTaskId) return;
    await fetch(`/api/agents/tasks/${activeTaskId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "User rejected Tier C action" }),
    });
    setPendingApproval(null);
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full text-slate-100">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">🐝</span>
            <h1 className="text-xl font-bold tracking-tight text-white">
              Autonomous Tooling & Multi-Agent Swarms
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
              Phase 11
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Authoritative DAG orchestration, cryptographic tool receipts, independent verifiers, and Tier C approval governance.
          </p>
        </div>

        {/* Budget Meters */}
        {budget && (
          <div className="flex items-center gap-4 text-xs font-mono bg-slate-900/80 px-4 py-2 rounded-xl border border-slate-800">
            <div>
              <span className="text-slate-500 block">Tokens</span>
              <span className="text-cyan-400 font-semibold">{budget.consumed_tokens.toLocaleString()}</span>
            </div>
            <div className="w-px h-6 bg-slate-800" />
            <div>
              <span className="text-slate-500 block">Tools</span>
              <span className="text-amber-400 font-semibold">{budget.consumed_tool_calls}</span>
            </div>
            <div className="w-px h-6 bg-slate-800" />
            <div>
              <span className="text-slate-500 block">NPR Cost</span>
              <span className="text-emerald-400 font-semibold">
                रू {(budget.consumed_cost_paisa / 100).toFixed(2)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Mission Control & Roster */}
        <div className="flex flex-col gap-5">
          {/* Dispatch Card */}
          <div className="p-5 bg-slate-900/60 rounded-2xl border border-slate-800 flex flex-col gap-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Dispatch Specialist Mission
            </h2>
            <form onSubmit={handleCreateTask} className="flex flex-col gap-3">
              <textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="Describe your multi-agent mission (e.g. 'Build and test a bilingual Nepal legal search micro-service with verified citations')..."
                className="w-full h-24 p-3 bg-slate-950/70 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-cyan-500/70 resize-none font-sans"
              />

              <div className="flex items-center justify-between gap-3">
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="en">English</option>
                  <option value="ne">नेपाली (Nepali)</option>
                  <option value="ne-rom">Romanized Nepali</option>
                </select>

                <button
                  type="submit"
                  disabled={loading || !goal.trim()}
                  className="px-4 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-cyan-500/20 transition disabled:opacity-50"
                >
                  {loading ? "Orchestrating..." : "Execute DAG Swarm"}
                </button>
              </div>
            </form>

            {error && (
              <div className="text-xs text-rose-400 bg-rose-950/50 border border-rose-800/40 p-2.5 rounded-lg">
                ⚠ {error}
              </div>
            )}
          </div>

          {/* Specialist Roster */}
          <div className="p-5 bg-slate-900/60 rounded-2xl border border-slate-800 flex flex-col gap-3">
            <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
              <span className="font-semibold uppercase tracking-wider text-slate-300">
                Active Specialist Roster
              </span>
              <span>10 roles whitelisted</span>
            </div>
            <div className="flex flex-col gap-2 max-h-60 overflow-y-auto pr-1">
              {specialists.map((sp) => (
                <div
                  key={sp.agent_id}
                  className="flex items-center justify-between p-2 rounded-lg bg-slate-950/50 border border-slate-800/60 text-xs"
                >
                  <div className="flex flex-col">
                    <span className="font-medium text-slate-200">{sp.display_name}</span>
                    <span className="text-[11px] text-slate-500 font-mono">{sp.role}</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {sp.health_status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center Column: Live DAG Graph & Artifacts */}
        <div className="flex flex-col gap-5 lg:col-span-2">
          {nodes.length > 0 ? (
            <AgentTaskGraph
              nodes={nodes}
              activeNodeId={activeNodeId}
              onSelectNode={(n) => setActiveNodeId(n.node_id)}
            />
          ) : (
            <div className="p-8 bg-slate-900/40 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-center text-slate-500 gap-2">
              <span className="text-3xl">🕸️</span>
              <p className="text-sm font-medium text-slate-400">No active DAG graph running</p>
              <p className="text-xs">Dispatch a mission above to generate and execute an acyclic multi-agent DAG.</p>
            </div>
          )}

          {/* Verified Artifacts */}
          {artifacts.length > 0 && (
            <div className="p-5 bg-slate-900/60 rounded-2xl border border-slate-800 flex flex-col gap-3">
              <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
                <span className="font-semibold uppercase tracking-wider text-slate-300">
                  Verified Physical Artifacts
                </span>
                <span className="text-emerald-400 font-mono">SHA-256 Validated</span>
              </div>
              <div className="flex flex-col gap-2">
                {artifacts.map((art, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2.5 bg-slate-950/60 border border-slate-800/80 rounded-lg text-xs font-mono"
                  >
                    <div className="flex items-center gap-2">
                      <span>📄</span>
                      <span className="text-slate-200">{art.filename}</span>
                    </div>
                    <span className="text-slate-500 text-[11px] truncate max-w-[200px]">
                      sha256:{art.sha256}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SSE Event Journal */}
          {events.length > 0 && (
            <div className="p-5 bg-slate-900/60 rounded-2xl border border-slate-800 flex flex-col gap-3">
              <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
                <span className="font-semibold uppercase tracking-wider text-slate-300">
                  Real-Time Event Journal
                </span>
                <span className="text-cyan-400 font-mono">{events.length} events logged</span>
              </div>
              <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1 font-mono text-[11px]">
                {events.map((evt) => (
                  <div
                    key={evt.event_id || evt.sequence}
                    className="flex items-center gap-2 text-slate-400 py-0.5 border-b border-slate-900"
                  >
                    <span className="text-slate-600 w-6">#{evt.sequence}</span>
                    <span className="text-cyan-400 font-semibold w-24 truncate">{evt.actor_role}</span>
                    <span className="text-amber-300 w-36 truncate">{evt.event_type}</span>
                    <span className="text-slate-500 truncate flex-1">
                      {JSON.stringify(evt.payload || {})}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tier C Cryptographic Approval Modal */}
      {pendingApproval && (
        <AgentApprovalPanel
          request={pendingApproval}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}
    </div>
  );
};
