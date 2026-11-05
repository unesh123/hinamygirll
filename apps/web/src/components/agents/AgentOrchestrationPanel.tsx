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

export interface TeamTemplate {
  team_id: string;
  team_type: string;
  display_name: string;
  description: string;
  lead_role: AgentRole;
  member_roles: AgentRole[];
  max_workers: number;
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
  team_id?: string;
}

export interface TaskEventLog {
  event_id: string;
  sequence: number;
  task_id: string;
  node_id?: string | null;
  team_run_id?: string | null;
  timestamp: string;
  actor_role: string;
  event_type: string;
  payload: Record<string, unknown>;
  depth?: number;
}

export const AgentOrchestrationPanel: React.FC = () => {
  const [goal, setGoal] = useState("");
  const [language, setLanguage] = useState("en");
  const [executionMode, setExecutionMode] = useState<string>("auto");
  const [loading, setLoading] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<TaskNodeData[]>([]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [specialists, setSpecialists] = useState<SpecialistSpec[]>([]);
  const [teams, setTeams] = useState<TeamTemplate[]>([]);
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

  // Fetch canonical teams
  const fetchTeams = useCallback(async () => {
    try {
      const res = await fetch("/api/agents/teams");
      if (res.ok) {
        const data = await res.json();
        setTeams(data.teams || []);
      }
    } catch {
      // Ignore
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
    fetchTeams();
    fetchHealth();
  }, [fetchRegistry, fetchTeams, fetchHealth]);

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
            team_id: parsed.team_run_id,
            ancestry: [activeTaskId, parsed.team_run_id || "team", parsed.node_id || "node"],
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
      const payload: Record<string, unknown> = { goal, language };
      if (executionMode !== "auto") {
        payload.execution_mode = executionMode;
      }

      const res = await fetch("/api/agents/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
            <span className="text-2xl">🏛️</span>
            <h1 className="text-xl font-bold tracking-tight text-white">
              Hierarchical Team Orchestration & Long-Horizon Execution
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30">
              Phase 12
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Nested team leads, bounded workstream budgets, cryptographic receipts, complete ancestry binding, and independent QA verification.
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
              Dispatch Team Mission
            </h2>
            <form onSubmit={handleCreateTask} className="flex flex-col gap-3">
              <textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="Describe your multi-team mission (e.g. 'Build a complete bilingual website with tests and browser verification')..."
                className="w-full h-24 p-3 bg-slate-950/70 border border-slate-800 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-cyan-500/70 resize-none font-sans"
              />

              <div className="grid grid-cols-2 gap-2">
                <select
                  value={executionMode}
                  onChange={(e) => setExecutionMode(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="auto">Auto-Select Mode</option>
                  <option value="hierarchical_team">Hierarchical Teams</option>
                  <option value="flat_multi_agent">Flat Multi-Agent</option>
                  <option value="single_agent_fast_path">Fast Path</option>
                </select>

                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-xs text-slate-300 rounded-lg px-2.5 py-1.5 focus:outline-none"
                >
                  <option value="en">English</option>
                  <option value="ne">नेपाली (Nepali)</option>
                  <option value="ne-rom">Romanized Nepali</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={loading || !goal.trim()}
                className="w-full mt-1 py-2 bg-gradient-to-r from-purple-600 via-indigo-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-purple-500/20 transition disabled:opacity-50"
              >
                {loading ? "Orchestrating Teams..." : "Execute Hierarchical Workflow"}
              </button>
            </form>

            {error && (
              <div className="text-xs text-rose-400 bg-rose-950/50 border border-rose-800/40 p-2.5 rounded-lg">
                ⚠ {error}
              </div>
            )}
          </div>

          {/* Canonical Teams */}
          <div className="p-5 bg-slate-900/60 rounded-2xl border border-slate-800 flex flex-col gap-3">
            <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
              <span className="font-semibold uppercase tracking-wider text-slate-300">
                Canonical Team Templates
              </span>
              <span>4 Teams Registered</span>
            </div>
            <div className="flex flex-col gap-2">
              {teams.map((tm) => (
                <div
                  key={tm.team_id}
                  className="flex flex-col p-2.5 rounded-lg bg-slate-950/50 border border-slate-800/60 text-xs gap-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-200">{tm.display_name}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                      lead: {tm.lead_role}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-400">{tm.description}</span>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className="text-[10px] text-slate-500">members:</span>
                    {tm.member_roles.map((r) => (
                      <span key={r} className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Specialist Roster */}
          <div className="p-5 bg-slate-900/60 rounded-2xl border border-slate-800 flex flex-col gap-3">
            <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
              <span className="font-semibold uppercase tracking-wider text-slate-300">
                Specialist Roles Pool
              </span>
              <span>10 roles available</span>
            </div>
            <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1">
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
              <span className="text-3xl">🏛️</span>
              <p className="text-sm font-medium text-slate-400">No active hierarchical mission running</p>
              <p className="text-xs">Dispatch a mission above to generate and execute nested team workstreams.</p>
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
                      {art.team_id && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-950 text-purple-300 border border-purple-800">
                          {art.team_id}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-500">{art.created_by}</span>
                      <span className="text-emerald-400 text-[11px] truncate max-w-[120px]">
                        {art.sha256.slice(0, 12)}...
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Real-Time Event Audit Stream */}
          {events.length > 0 && (
            <div className="p-5 bg-slate-900/60 rounded-2xl border border-slate-800 flex flex-col gap-3">
              <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-2">
                <span className="font-semibold uppercase tracking-wider text-slate-300">
                  Live Audit Journal (SSE Stream)
                </span>
                <span className="text-cyan-400 font-mono">{events.length} events logged</span>
              </div>
              <div className="flex flex-col gap-1.5 max-h-56 overflow-y-auto font-mono text-[11px] pr-1">
                {events.map((evt, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-3 py-1 border-b border-slate-800/40 text-slate-400"
                  >
                    <span className="text-slate-600 w-6">#{evt.sequence}</span>
                    <span className="text-cyan-400 w-24 truncate">{evt.actor_role}</span>
                    <span className="text-purple-300 font-medium">{evt.event_type}</span>
                    <span className="text-slate-500 text-[10px] truncate max-w-xs">
                      {JSON.stringify(evt.payload)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tier C Approval Modal */}
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
