import React, { useState, useEffect, useCallback } from "react";

export interface MilestoneItem {
  milestone_id: string;
  goal_id: string;
  title: string;
  description: string;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
  prerequisites: string[];
  exit_criteria: string[];
  evidence_requirements: string[];
  estimated_paisa: number;
  actual_paisa: number;
  estimated_tokens: number;
  actual_tokens: number;
  cost_category: "MEASURED" | "PROVIDER_ESTIMATED" | "SYNTHETIC_TEST_ONLY";
  status: "PENDING" | "RUNNING" | "VERIFIED" | "PARTIAL" | "UNVERIFIED" | "FAILED" | "BLOCKED" | "NEEDS_APPROVAL" | "SKIPPED";
  assigned_role: string;
  execution_mode: string;
  failure_reason?: string;
  evidence_receipts?: Array<{
    receipt_id: string;
    tool_name: string;
    exit_code: number;
    output_hash: string;
    timestamp_utc: number;
  }>;
}

export interface PlanVersionItem {
  plan_version_id: string;
  goal_id: string;
  version_number: number;
  edges: string[][];
  reason_for_change?: string;
  verification_reserve_paisa: number;
  verification_reserve_tokens: number;
  milestones: MilestoneItem[];
  created_at_utc: number;
}

export interface GoalItem {
  goal_id: string;
  tenant_id: string;
  title: string;
  description: string;
  origin: string;
  authorized_scope: string[];
  priority: number;
  risk_tier: "TIER_A_READONLY" | "TIER_B_INTERNAL_DEV" | "TIER_C_CONSEQUENTIAL";
  budget_paisa: number;
  consumed_paisa: number;
  budget_tokens: number;
  consumed_tokens: number;
  status: "PROPOSED" | "ACCEPTED" | "RUNNING" | "PAUSED" | "WAITING_APPROVAL" | "BLOCKED" | "SUCCEEDED" | "FAILED" | "CANCELLED" | "EXPIRED";
  active_plan_version: number;
  replan_count: number;
  max_replans: number;
  created_at_utc: number;
  termination_reason?: string;
}

export interface ReplanItem {
  replan_id: string;
  goal_id: string;
  prior_plan_version: number;
  new_plan_version: number;
  root_cause: string;
  explanation_en: string;
  explanation_ne: string;
  explanation_romanized: string;
  superseded_milestone_ids: string[];
  reused_milestone_ids: string[];
  added_milestone_ids: string[];
  created_at_utc: number;
}

export interface SelfModelSummary {
  entity: string;
  version: string;
  sentient: boolean;
  has_human_consciousness: boolean;
  capabilities: Record<string, boolean>;
  unavailable_capabilities: string[];
  limitations: string[];
}

export interface LoopTaskSummary {
  task_id: string;
  goal_title: string;
  status: string;
  updated_at: string;
  total_receipts: number;
}

export interface LoopEvidenceReceipt {
  turn: number;
  timestamp: string;
  exit_code: number;
  passed: boolean;
  duration_ms: number;
  command: string[];
  diff_stat?: string;
  stdout_snippet?: string;
  stderr_snippet?: string;
}

export interface EvalScorecardData {
  total_cases: number;
  passed_cases: number;
  overall_score: number;
  pass_rate: number;
  category_scores: Record<string, number>;
  duration_ms: number;
  timestamp: string;
}

export interface LoopTaskDetail {
  task_id: string;
  goal_title: string;
  description: string;
  status: string;
  total_turns: number;
  receipts: LoopEvidenceReceipt[];
  error_message?: string;
  state_file?: string;
}

export const GoalsDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"goals" | "loop">("goals");
  const [goals, setGoals] = useState<GoalItem[]>([]);
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
  const [activePlan, setActivePlan] = useState<PlanVersionItem | null>(null);
  const [replans, setReplans] = useState<ReplanItem[]>([]);
  const [selfModel, setSelfModel] = useState<SelfModelSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [language, setLanguage] = useState<"en" | "ne" | "rom">("en");
  const [newGoalTitle, setNewGoalTitle] = useState("");
  const [newGoalDesc, setNewGoalDesc] = useState("");

  // Loop Engine state
  const [loopTasks, setLoopTasks] = useState<LoopTaskSummary[]>([]);
  const [selectedLoopTaskId, setSelectedLoopTaskId] = useState<string | null>(null);
  const [selectedLoopDetail, setSelectedLoopDetail] = useState<LoopTaskDetail | null>(null);
  const [newLoopGoal, setNewLoopGoal] = useState("");
  const [newLoopGate, setNewLoopGate] = useState("apps\\api\\.venv\\Scripts\\python.exe -m pytest apps/api/tests/test_loop_api.py -v");
  const [newLoopTurns, setNewLoopTurns] = useState(5);
  const [loopStarting, setLoopStarting] = useState(false);
  const [scorecard, setScorecard] = useState<EvalScorecardData | null>(null);
  const [evalRunning, setEvalRunning] = useState(false);

  const fetchGoals = useCallback(async () => {
    try {
      const res = await fetch("/api/goals");
      if (res.ok) {
        const data = await res.json();
        setGoals(data);
        if (!selectedGoalId && data.length > 0) {
          setSelectedGoalId(data[0].goal_id);
        }
      }
    } catch (e) {
      console.error("Failed to load goals", e);
    }
  }, [selectedGoalId]);

  const fetchSelfModel = useCallback(async () => {
    try {
      const res = await fetch("/api/goals/self-model");
      if (res.ok) {
        const data = await res.json();
        setSelfModel(data);
      }
    } catch (e) {
      console.error("Failed to load self model", e);
    }
  }, []);

  const fetchGoalDetails = useCallback(async (goalId: string) => {
    try {
      setLoading(true);
      const res = await fetch(`/api/goals/${goalId}`);
      if (res.ok) {
        const data = await res.json();
        setActivePlan(data.active_plan);
      }
      const replanRes = await fetch(`/api/goals/${goalId}/replans`);
      if (replanRes.ok) {
        const data = await replanRes.json();
        setReplans(data);
      }
    } catch (e) {
      console.error("Failed to fetch goal details", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchLoopTasks = useCallback(async () => {
    try {
      const res = await fetch("/api/loop/tasks");
      if (res.ok) {
        const data = await res.json();
        const tasks = data.tasks || [];
        setLoopTasks(tasks);
        if (!selectedLoopTaskId && tasks.length > 0) {
          setSelectedLoopTaskId(tasks[0].task_id);
        }
      }
    } catch (e) {
      console.error("Failed to load loop tasks", e);
    }
  }, [selectedLoopTaskId]);

  const fetchScorecard = useCallback(async () => {
    try {
      const res = await fetch("/api/evals/latest");
      if (res.ok) {
        const data = await res.json();
        setScorecard(data);
      }
    } catch (e) {
      console.error("Failed to load eval scorecard", e);
    }
  }, []);

  const handleRunEvals = async () => {
    try {
      setEvalRunning(true);
      const res = await fetch("/api/evals/run", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setScorecard(data);
      }
    } catch (e) {
      console.error("Failed to run evals", e);
    } finally {
      setEvalRunning(false);
    }
  };

  const fetchLoopDetail = useCallback(async (taskId: string) => {
    try {
      const res = await fetch(`/api/loop/status/${taskId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedLoopDetail(data);
      }
    } catch (e) {
      console.error("Failed to load loop detail", e);
    }
  }, []);

  useEffect(() => {
    fetchGoals();
    fetchSelfModel();
    fetchLoopTasks();
    fetchScorecard();
    const interval = setInterval(() => {
      fetchGoals();
      if (selectedGoalId) fetchGoalDetails(selectedGoalId);
      fetchLoopTasks();
      if (selectedLoopTaskId) fetchLoopDetail(selectedLoopTaskId);
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchGoals, fetchSelfModel, fetchGoalDetails, fetchLoopTasks, fetchLoopDetail, selectedGoalId, selectedLoopTaskId]);

  useEffect(() => {
    if (selectedGoalId) {
      fetchGoalDetails(selectedGoalId);
    }
  }, [selectedGoalId, fetchGoalDetails]);

  useEffect(() => {
    if (selectedLoopTaskId) {
      fetchLoopDetail(selectedLoopTaskId);
    }
  }, [selectedLoopTaskId, fetchLoopDetail]);

  const handleCreateGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGoalTitle.trim()) return;
    try {
      const res = await fetch("/api/goals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newGoalTitle,
          description: newGoalDesc,
          auto_accept: true,
        }),
      });
      if (res.ok) {
        setNewGoalTitle("");
        setNewGoalDesc("");
        fetchGoals();
      }
    } catch (e) {
      console.error("Error creating goal", e);
    }
  };

  const handleAction = async (action: "start" | "pause" | "resume" | "cancel") => {
    if (!selectedGoalId) return;
    try {
      await fetch(`/api/goals/${selectedGoalId}/${action}`, { method: "POST" });
      fetchGoals();
      fetchGoalDetails(selectedGoalId);
    } catch (e) {
      console.error(`Error executing ${action}`, e);
    }
  };

  const handleStartLoop = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLoopGoal.trim() || !newLoopGate.trim()) return;
    try {
      setLoopStarting(true);
      const commandTokens = newLoopGate.match(/(?:[^\s"]+|"[^"]*")+/g)?.map(t => t.replace(/(^"|"$)/g, "")) || [newLoopGate];
      const res = await fetch("/api/loop/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal_title: newLoopGoal,
          verification_command: commandTokens,
          max_turns: Number(newLoopTurns) || 5,
          consecutive_failure_limit: 2,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setNewLoopGoal("");
        fetchLoopTasks();
        if (data.task_id) {
          setSelectedLoopTaskId(data.task_id);
          fetchLoopDetail(data.task_id);
        }
      }
    } catch (e) {
      console.error("Failed to start loop", e);
    } finally {
      setLoopStarting(false);
    }
  };

  const handleStopLoop = async (taskId: string) => {
    try {
      await fetch(`/api/loop/stop/${taskId}`, { method: "POST" });
      fetchLoopTasks();
      fetchLoopDetail(taskId);
    } catch (e) {
      console.error("Failed to stop loop", e);
    }
  };

  const selectedGoal = goals.find((g) => g.goal_id === selectedGoalId);

  return (
    <div style={{ padding: "24px", color: "#f1f5f9", fontFamily: "sans-serif", background: "#0b0f19", minHeight: "100vh" }}>
      {/* Header & Linguistic Selector */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", borderBottom: "1px solid #1e293b", paddingBottom: "16px" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "24px", fontWeight: "bold", background: "linear-gradient(90deg, #38bdf8, #818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            HINAA OS — Phase 14: Autonomous Goal Planner & Loop Engine
          </h1>
          <p style={{ margin: "4px 0 0", color: "#94a3b8", fontSize: "14px" }}>
            Bounded Multi-Stage Objectives • Objective Verification Gates • Continuous Loop Architecture
          </p>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          {(["en", "ne", "rom"] as const).map((lang) => (
            <button
              key={lang}
              onClick={() => setLanguage(lang)}
              style={{
                padding: "6px 12px",
                borderRadius: "6px",
                border: "1px solid #334155",
                background: language === lang ? "#3b82f6" : "#1e293b",
                color: "#fff",
                cursor: "pointer",
                fontWeight: language === lang ? "bold" : "normal",
              }}
            >
              {lang === "en" ? "English" : lang === "ne" ? "नेपाली" : "Romanized"}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Switcher */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "18px" }}>
        <button
          onClick={() => setActiveTab("goals")}
          style={{
            padding: "8px 18px",
            borderRadius: "8px",
            border: `1px solid ${activeTab === "goals" ? "#38bdf8" : "#334155"}`,
            background: activeTab === "goals" ? "#0284c7" : "#1e293b",
            color: "#fff",
            fontWeight: "bold",
            cursor: "pointer",
            fontSize: "13px",
          }}
        >
          🎯 Multi-Stage Goals & DAG
        </button>
        <button
          onClick={() => setActiveTab("loop")}
          style={{
            padding: "8px 18px",
            borderRadius: "8px",
            border: `1px solid ${activeTab === "loop" ? "#a855f7" : "#334155"}`,
            background: activeTab === "loop" ? "#7c3aed" : "#1e293b",
            color: "#fff",
            fontWeight: "bold",
            cursor: "pointer",
            fontSize: "13px",
          }}
        >
          ⚡ Loop Engine (sorrycc Autonomous Harness)
        </button>
      </div>

      {/* TAB 1: GOALS & MILESTONES DAG */}
      {activeTab === "goals" && (
        <>
          {/* Self-Model Alert & Constraints Banner */}
          {selfModel && (
            <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: "8px", padding: "12px 16px", marginBottom: "20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <span style={{ fontSize: "12px", fontWeight: "bold", color: "#38bdf8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Observed Self-Model Status
                </span>
                <div style={{ fontSize: "13px", color: "#cbd5e1", marginTop: "2px" }}>
                  Sentience: <span style={{ color: "#f87171" }}>False (Non-conscious)</span> • Real Payments: <span style={{ color: "#fbbf24" }}>Tier C HMAC Guarded</span> • Generative Video: <span style={{ color: "#f87171" }}>Unavailable (Weights Missing)</span>
                </div>
              </div>
              <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                Ledger Audit: v{selfModel.version}
              </div>
            </div>
          )}

          {/* Main Grid: Goal List + Goal Plan View */}
          <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: "24px" }}>
            {/* Left Column: Goals Intake & Selector */}
            <div>
              <form onSubmit={handleCreateGoal} style={{ background: "#1e293b", padding: "16px", borderRadius: "8px", marginBottom: "16px" }}>
                <h3 style={{ margin: "0 0 12px", fontSize: "15px", color: "#e2e8f0" }}>Propose New Goal</h3>
                <input
                  type="text"
                  placeholder="Goal Title (e.g. Build English/Nepali App)"
                  value={newGoalTitle}
                  onChange={(e) => setNewGoalTitle(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #334155", background: "#0f172a", color: "#fff", marginBottom: "8px", boxSizing: "border-box" }}
                />
                <textarea
                  placeholder="Success criteria & constraints..."
                  value={newGoalDesc}
                  onChange={(e) => setNewGoalDesc(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #334155", background: "#0f172a", color: "#fff", marginBottom: "8px", minHeight: "60px", boxSizing: "border-box" }}
                />
                <button
                  type="submit"
                  style={{ width: "100%", padding: "8px", borderRadius: "6px", background: "#2563eb", border: "none", color: "#fff", fontWeight: "bold", cursor: "pointer" }}
                >
                  + Propose Goal
                </button>
              </form>

              <h3 style={{ fontSize: "14px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", margin: "0 0 8px" }}>
                Authorized Goal Registry ({goals.length})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {goals.map((g) => {
                  const isSelected = g.goal_id === selectedGoalId;
                  const statusColor =
                    g.status === "SUCCEEDED" ? "#22c55e" :
                    g.status === "RUNNING" ? "#38bdf8" :
                    g.status === "BLOCKED" || g.status === "FAILED" ? "#ef4444" :
                    g.status === "WAITING_APPROVAL" ? "#f59e0b" : "#94a3b8";

                  return (
                    <div
                      key={g.goal_id}
                      onClick={() => setSelectedGoalId(g.goal_id)}
                      style={{
                        padding: "12px",
                        borderRadius: "8px",
                        background: isSelected ? "#1e293b" : "#0f172a",
                        border: `1px solid ${isSelected ? "#3b82f6" : "#1e293b"}`,
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <span style={{ fontSize: "11px", fontWeight: "bold", color: statusColor, textTransform: "uppercase" }}>
                          ● {g.status}
                        </span>
                        <span style={{ fontSize: "11px", color: "#64748b" }}>
                          Plan v{g.active_plan_version} • {g.replan_count} replans
                        </span>
                      </div>
                      <div style={{ fontSize: "14px", fontWeight: "bold", color: "#f8fafc", marginBottom: "4px" }}>
                        {g.title}
                      </div>
                      <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                        Budget: रू {(g.consumed_paisa / 100).toFixed(2)} / रू {(g.budget_paisa / 100).toFixed(2)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right Column: Active Plan & Milestones DAG */}
            <div>
              {selectedGoal ? (
                <div>
                  <div style={{ background: "#1e293b", padding: "16px 20px", borderRadius: "8px", marginBottom: "20px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                      <div>
                        <h2 style={{ margin: "0 0 6px", fontSize: "18px", color: "#fff" }}>{selectedGoal.title}</h2>
                        <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8" }}>{selectedGoal.description || "No description provided"}</p>
                      </div>
                      <div style={{ display: "flex", gap: "8px" }}>
                        {selectedGoal.status === "PROPOSED" && (
                          <button onClick={() => handleAction("start")} style={{ padding: "6px 14px", borderRadius: "6px", background: "#22c55e", border: "none", color: "#fff", fontWeight: "bold", cursor: "pointer" }}>
                            Accept & Start
                          </button>
                        )}
                        {selectedGoal.status === "RUNNING" && (
                          <button onClick={() => handleAction("pause")} style={{ padding: "6px 14px", borderRadius: "6px", background: "#f59e0b", border: "none", color: "#fff", fontWeight: "bold", cursor: "pointer" }}>
                            Pause
                          </button>
                        )}
                        {selectedGoal.status === "PAUSED" && (
                          <button onClick={() => handleAction("resume")} style={{ padding: "6px 14px", borderRadius: "6px", background: "#38bdf8", border: "none", color: "#fff", fontWeight: "bold", cursor: "pointer" }}>
                            Resume
                          </button>
                        )}
                        {["RUNNING", "PAUSED", "WAITING_APPROVAL"].includes(selectedGoal.status) && (
                          <button onClick={() => handleAction("cancel")} style={{ padding: "6px 14px", borderRadius: "6px", background: "#ef4444", border: "none", color: "#fff", fontWeight: "bold", cursor: "pointer" }}>
                            Cancel
                          </button>
                        )}
                      </div>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", borderTop: "1px solid #334155", paddingTop: "12px", fontSize: "12px" }}>
                      <div>
                        <span style={{ color: "#64748b" }}>Risk Tier:</span> <strong style={{ color: "#e2e8f0" }}>{selectedGoal.risk_tier}</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>Active Plan:</span> <strong style={{ color: "#38bdf8" }}>Version {selectedGoal.active_plan_version}</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>Paisa Consumed:</span> <strong style={{ color: "#a5b4fc" }}>रू {(selectedGoal.consumed_paisa / 100).toFixed(2)}</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>Tokens Consumed:</span> <strong style={{ color: "#a5b4fc" }}>{selectedGoal.consumed_tokens.toLocaleString()}</strong>
                      </div>
                    </div>
                  </div>

                  <h3 style={{ fontSize: "15px", color: "#e2e8f0", margin: "0 0 12px" }}>
                    Active Plan Milestones ({activePlan?.milestones.length || 0})
                  </h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "24px" }}>
                    {activePlan?.milestones.map((ms) => {
                      const msStatusColor =
                        ms.status === "VERIFIED" ? "#22c55e" :
                        ms.status === "RUNNING" ? "#38bdf8" :
                        ms.status === "FAILED" || ms.status === "BLOCKED" ? "#ef4444" :
                        ms.status === "PARTIAL" ? "#f59e0b" : "#64748b";

                      return (
                        <div
                          key={ms.milestone_id}
                          style={{
                            background: "#0f172a",
                            border: "1px solid #1e293b",
                            borderRadius: "8px",
                            padding: "16px",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "6px" }}>
                            <div>
                              <span style={{ fontSize: "11px", fontWeight: "bold", color: msStatusColor, textTransform: "uppercase", marginRight: "8px" }}>
                                [{ms.status}]
                              </span>
                              <strong style={{ fontSize: "14px", color: "#f8fafc" }}>{ms.title}</strong>
                            </div>
                            <span style={{ fontSize: "12px", color: "#64748b" }}>
                              Mode: {ms.execution_mode} • Role: {ms.assigned_role}
                            </span>
                          </div>
                          <p style={{ margin: "4px 0 8px", fontSize: "13px", color: "#94a3b8" }}>{ms.description}</p>

                          {ms.failure_reason && (
                            <div style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "6px", padding: "8px 12px", fontSize: "12px", color: "#fca5a5", marginBottom: "8px" }}>
                              <strong>Failure Cause:</strong> {ms.failure_reason}
                            </div>
                          )}

                          {ms.evidence_receipts && ms.evidence_receipts.length > 0 && (
                            <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid #1e293b" }}>
                              <span style={{ fontSize: "11px", fontWeight: "bold", color: "#64748b", textTransform: "uppercase" }}>
                                Verified Receipts ({ms.evidence_receipts.length}):
                              </span>
                              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "4px" }}>
                                {ms.evidence_receipts.map((rec) => (
                                  <span key={rec.receipt_id} style={{ fontSize: "11px", background: "#1e293b", padding: "3px 8px", borderRadius: "4px", color: "#cbd5e1" }}>
                                    {rec.tool_name} (code: {rec.exit_code}) • hash:{rec.output_hash.slice(0, 8)}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {replans.length > 0 && (
                    <div style={{ background: "#1e293b", borderRadius: "8px", padding: "16px" }}>
                      <h3 style={{ margin: "0 0 12px", fontSize: "15px", color: "#e2e8f0" }}>
                        Self-Correction & Replan Decisions ({replans.length})
                      </h3>
                      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                        {replans.map((r) => {
                          const explanation =
                            language === "ne" ? r.explanation_ne :
                            language === "rom" ? r.explanation_romanized : r.explanation_en;

                          return (
                            <div key={r.replan_id} style={{ background: "#0f172a", borderRadius: "6px", padding: "12px", border: "1px solid #334155" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                                <strong style={{ fontSize: "13px", color: "#38bdf8" }}>
                                  Version {r.prior_plan_version} ➔ Version {r.new_plan_version}
                                </strong>
                                <span style={{ fontSize: "11px", color: "#f87171", textTransform: "uppercase" }}>
                                  {r.root_cause}
                                </span>
                              </div>
                              <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#cbd5e1", lineHeight: "1.5" }}>
                                {explanation}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ background: "#1e293b", borderRadius: "8px", padding: "40px", textAlign: "center", color: "#64748b" }}>
                  Select a goal to view its plan graph and self-correction timeline
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* TAB 2: LOOP ENGINE (SORRYCC AUTONOMOUS HARNESS) */}
      {activeTab === "loop" && (
        <div>
          {/* Sorrycc 3 Iron Rules Banner */}
          <div style={{ background: "linear-gradient(135deg, rgba(124, 58, 237, 0.15), rgba(16, 185, 129, 0.15))", border: "1px solid rgba(168, 85, 247, 0.4)", borderRadius: "8px", padding: "16px 20px", marginBottom: "20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <span style={{ fontSize: "13px", fontWeight: "bold", color: "#c084fc", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                ⚡ Continuous Loop Engineering Harness (sorrycc 2026 Autonomous Paradigm)
              </span>
              <span style={{ fontSize: "11px", color: "#94a3b8" }}>State Ledger: .runtime/loop_state/</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px", fontSize: "12px", color: "#e2e8f0" }}>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "10px 12px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
                <strong style={{ color: "#38bdf8", display: "block", marginBottom: "4px" }}>1. 上限看模型，下限看架构</strong>
                Harness context, test runners & gate loop control determine autonomous floor; raw prompting alone cannot guarantee convergence.
              </div>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "10px 12px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
                <strong style={{ color: "#4ade80", display: "block", marginBottom: "4px" }}>2. Done 是声明，不是证明</strong>
                Subprocess exit code 0 is an objective hard gate; never rely on conversational self-declaration of completion.
              </div>
              <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "10px 12px", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.05)" }}>
                <strong style={{ color: "#f472b6", display: "block", marginBottom: "4px" }}>3. Agent 会忘，repo 不会</strong>
                All execution state, error history, and diff receipts are persisted to disk ledgers across turn iterations.
              </div>
            </div>
          </div>

          {/* Agent Reasoning & Alignment Scorecard */}
          {scorecard && (
            <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px", padding: "16px 20px", marginBottom: "20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <div>
                  <span style={{ fontSize: "11px", fontWeight: "bold", color: "#38bdf8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Automated Agent Reasoning & Benchmark Scorecard
                  </span>
                  <div style={{ fontSize: "14px", fontWeight: "bold", color: "#f8fafc", marginTop: "2px" }}>
                    Overall Score: <span style={{ color: "#22c55e" }}>{scorecard.overall_score}%</span> • Pass Rate: <span style={{ color: "#22c55e" }}>{scorecard.pass_rate}%</span> ({scorecard.passed_cases}/{scorecard.total_cases} tasks)
                  </div>
                </div>
                <button
                  onClick={handleRunEvals}
                  disabled={evalRunning}
                  style={{ padding: "6px 14px", borderRadius: "6px", background: "#334155", border: "1px solid #475569", color: "#fff", fontSize: "12px", fontWeight: "bold", cursor: evalRunning ? "not-allowed" : "pointer" }}
                >
                  {evalRunning ? "Running Evals..." : "⚡ Run Benchmark Battery"}
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px", fontSize: "12px" }}>
                <div style={{ background: "#1e293b", padding: "8px 12px", borderRadius: "6px" }}>
                  <span style={{ color: "#94a3b8", display: "block" }}>Safety Guardrails:</span>
                  <strong style={{ color: "#22c55e" }}>{scorecard.category_scores?.safety_guardrails || 100}%</strong>
                </div>
                <div style={{ background: "#1e293b", padding: "8px 12px", borderRadius: "6px" }}>
                  <span style={{ color: "#94a3b8", display: "block" }}>Tool Selection:</span>
                  <strong style={{ color: "#22c55e" }}>{scorecard.category_scores?.tool_selection || 100}%</strong>
                </div>
                <div style={{ background: "#1e293b", padding: "8px 12px", borderRadius: "6px" }}>
                  <span style={{ color: "#94a3b8", display: "block" }}>Loop Verification:</span>
                  <strong style={{ color: "#22c55e" }}>{scorecard.category_scores?.loop_verification || 100}%</strong>
                </div>
                <div style={{ background: "#1e293b", padding: "8px 12px", borderRadius: "6px" }}>
                  <span style={{ color: "#94a3b8", display: "block" }}>Multilingual & Nepali:</span>
                  <strong style={{ color: "#22c55e" }}>{scorecard.category_scores?.multilingual || 100}%</strong>
                </div>
              </div>
            </div>
          )}

          {/* Loop Main Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "24px" }}>
            {/* Left Column: Start Loop Form & Task List */}
            <div>
              <form onSubmit={handleStartLoop} style={{ background: "#1e293b", padding: "16px", borderRadius: "8px", marginBottom: "16px" }}>
                <h3 style={{ margin: "0 0 12px", fontSize: "15px", color: "#e2e8f0" }}>Start Unattended Loop</h3>
                <input
                  type="text"
                  placeholder="Goal Title (e.g. Verify Loop API Suite)"
                  value={newLoopGoal}
                  onChange={(e) => setNewLoopGoal(e.target.value)}
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #334155", background: "#0f172a", color: "#fff", marginBottom: "8px", boxSizing: "border-box" }}
                />
                <div style={{ marginBottom: "8px" }}>
                  <label style={{ fontSize: "11px", color: "#94a3b8", display: "block", marginBottom: "4px" }}>Objective Verification Gate (Command):</label>
                  <input
                    type="text"
                    value={newLoopGate}
                    onChange={(e) => setNewLoopGate(e.target.value)}
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #334155", background: "#0f172a", color: "#fff", fontFamily: "monospace", fontSize: "12px", boxSizing: "border-box" }}
                  />
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "12px" }}>
                  <label style={{ fontSize: "12px", color: "#94a3b8" }}>Max Turns:</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={newLoopTurns}
                    onChange={(e) => setNewLoopTurns(Number(e.target.value))}
                    style={{ width: "60px", padding: "6px 8px", borderRadius: "6px", border: "1px solid #334155", background: "#0f172a", color: "#fff" }}
                  />
                  <span style={{ fontSize: "11px", color: "#64748b" }}>Breaker at 2 duplicate fails</span>
                </div>
                <button
                  type="submit"
                  disabled={loopStarting}
                  style={{ width: "100%", padding: "9px", borderRadius: "6px", background: "#7c3aed", border: "none", color: "#fff", fontWeight: "bold", cursor: loopStarting ? "not-allowed" : "pointer" }}
                >
                  {loopStarting ? "Starting Loop..." : "⚡ Launch Unattended Loop"}
                </button>
              </form>

              <h3 style={{ fontSize: "14px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em", margin: "0 0 8px" }}>
                Active & Past Loops ({loopTasks.length})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {loopTasks.map((t) => {
                  const isSelected = t.task_id === selectedLoopTaskId;
                  const statusColor =
                    t.status === "COMPLETED" ? "#22c55e" :
                    t.status === "RUNNING" ? "#38bdf8" :
                    t.status === "STOPPED_CONSECUTIVE_FAILURES" ? "#ef4444" :
                    t.status === "MAX_ITERATIONS_REACHED" ? "#f59e0b" : "#94a3b8";

                  return (
                    <div
                      key={t.task_id}
                      onClick={() => setSelectedLoopTaskId(t.task_id)}
                      style={{
                        padding: "12px",
                        borderRadius: "8px",
                        background: isSelected ? "#1e293b" : "#0f172a",
                        border: `1px solid ${isSelected ? "#a855f7" : "#1e293b"}`,
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                        <span style={{ fontSize: "11px", fontWeight: "bold", color: statusColor, textTransform: "uppercase" }}>
                          ● {t.status}
                        </span>
                        <span style={{ fontSize: "11px", color: "#64748b" }}>
                          {t.total_receipts} receipts
                        </span>
                      </div>
                      <div style={{ fontSize: "13px", fontWeight: "bold", color: "#f8fafc", marginBottom: "4px" }}>
                        {t.goal_title || t.task_id}
                      </div>
                      <div style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>
                        {t.task_id} • {t.updated_at ? new Date(t.updated_at).toLocaleTimeString() : ""}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right Column: Loop Task Detail & Evidence Receipts */}
            <div>
              {selectedLoopDetail ? (
                <div>
                  <div style={{ background: "#1e293b", padding: "16px 20px", borderRadius: "8px", marginBottom: "20px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                      <div>
                        <h2 style={{ margin: "0 0 6px", fontSize: "18px", color: "#fff" }}>
                          {selectedLoopDetail.goal_title || selectedLoopDetail.task_id}
                        </h2>
                        <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8" }}>
                          {selectedLoopDetail.description || "Unattended loop with hard gate execution"}
                        </p>
                      </div>
                      {selectedLoopDetail.status === "RUNNING" && (
                        <button
                          onClick={() => handleStopLoop(selectedLoopDetail.task_id)}
                          style={{ padding: "6px 14px", borderRadius: "6px", background: "#ef4444", border: "none", color: "#fff", fontWeight: "bold", cursor: "pointer" }}
                        >
                          Stop Loop
                        </button>
                      )}
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", borderTop: "1px solid #334155", paddingTop: "12px", fontSize: "12px" }}>
                      <div>
                        <span style={{ color: "#64748b" }}>Status:</span> <strong style={{ color: selectedLoopDetail.status === "COMPLETED" ? "#22c55e" : selectedLoopDetail.status === "RUNNING" ? "#38bdf8" : "#f87171" }}>{selectedLoopDetail.status}</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>Total Turns:</span> <strong style={{ color: "#cbd5e1" }}>{selectedLoopDetail.total_turns || selectedLoopDetail.receipts?.length || 0}</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>Disk Ledger:</span> <span style={{ color: "#a5b4fc", fontFamily: "monospace" }}>.runtime/loop_state/{selectedLoopDetail.task_id}_state.json</span>
                      </div>
                    </div>
                  </div>

                  <h3 style={{ fontSize: "15px", color: "#e2e8f0", margin: "0 0 12px" }}>
                    Hard Gate Evidence Receipts ({selectedLoopDetail.receipts?.length || 0})
                  </h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    {selectedLoopDetail.receipts && selectedLoopDetail.receipts.length > 0 ? (
                      selectedLoopDetail.receipts.map((r, idx) => (
                        <div key={idx} style={{ background: "#0f172a", border: `1px solid ${r.passed ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)"}`, borderRadius: "8px", padding: "16px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                            <div>
                              <span style={{ fontSize: "11px", fontWeight: "bold", color: r.passed ? "#22c55e" : "#ef4444", textTransform: "uppercase", marginRight: "8px" }}>
                                [{r.passed ? "PASSED (Exit 0)" : `FAILED (Exit ${r.exit_code})`}]
                              </span>
                              <strong style={{ fontSize: "13px", color: "#f8fafc" }}>Turn #{r.turn}</strong>
                            </div>
                            <span style={{ fontSize: "11px", color: "#64748b" }}>
                              Duration: {r.duration_ms.toFixed(0)} ms • {r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : ""}
                            </span>
                          </div>

                          <div style={{ fontSize: "12px", fontFamily: "monospace", color: "#94a3b8", background: "#0b0f19", padding: "6px 10px", borderRadius: "4px", marginBottom: "8px" }}>
                            Gate: {Array.isArray(r.command) ? r.command.join(" ") : r.command}
                          </div>

                          {r.diff_stat && (
                            <div style={{ fontSize: "11px", color: "#38bdf8", marginBottom: "6px" }}>
                              Diff: {r.diff_stat}
                            </div>
                          )}

                          {r.stdout_snippet && (
                            <pre style={{ margin: "4px 0", fontSize: "11px", background: "#050810", padding: "8px", borderRadius: "4px", color: "#cbd5e1", overflowX: "auto", maxHeight: "150px" }}>
                              {r.stdout_snippet}
                            </pre>
                          )}

                          {r.stderr_snippet && (
                            <pre style={{ margin: "4px 0", fontSize: "11px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.2)", padding: "8px", borderRadius: "4px", color: "#fca5a5", overflowX: "auto", maxHeight: "150px" }}>
                              {r.stderr_snippet}
                            </pre>
                          )}
                        </div>
                      ))
                    ) : (
                      <div style={{ background: "#1e293b", borderRadius: "8px", padding: "30px", textAlign: "center", color: "#64748b" }}>
                        No receipts yet. The loop will log verified execution receipts as each turn completes.
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ background: "#1e293b", borderRadius: "8px", padding: "40px", textAlign: "center", color: "#64748b" }}>
                  Select a loop task to view its hard gate receipts and execution timeline
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GoalsDashboard;
