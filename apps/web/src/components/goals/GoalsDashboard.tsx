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

export const GoalsDashboard: React.FC = () => {
  const [goals, setGoals] = useState<GoalItem[]>([]);
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
  const [activePlan, setActivePlan] = useState<PlanVersionItem | null>(null);
  const [replans, setReplans] = useState<ReplanItem[]>([]);
  const [selfModel, setSelfModel] = useState<SelfModelSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [language, setLanguage] = useState<"en" | "ne" | "rom">("en");
  const [newGoalTitle, setNewGoalTitle] = useState("");
  const [newGoalDesc, setNewGoalDesc] = useState("");

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

  useEffect(() => {
    fetchGoals();
    fetchSelfModel();
    const interval = setInterval(() => {
      fetchGoals();
      if (selectedGoalId) fetchGoalDetails(selectedGoalId);
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchGoals, fetchSelfModel, fetchGoalDetails, selectedGoalId]);

  useEffect(() => {
    if (selectedGoalId) {
      fetchGoalDetails(selectedGoalId);
    }
  }, [selectedGoalId, fetchGoalDetails]);

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

  const selectedGoal = goals.find((g) => g.goal_id === selectedGoalId);

  return (
    <div style={{ padding: "24px", color: "#f1f5f9", fontFamily: "sans-serif", background: "#0b0f19", minHeight: "100vh" }}>
      {/* Header & Linguistic Selector */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", borderBottom: "1px solid #1e293b", paddingBottom: "16px" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "24px", fontWeight: "bold", background: "linear-gradient(90deg, #38bdf8, #818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            HINAA OS — Phase 14: Autonomous Goal Planner & Continuous Self-Correction
          </h1>
          <p style={{ margin: "4px 0 0", color: "#94a3b8", fontSize: "14px" }}>
            Bounded Multi-Stage Objectives • Evidence-Grounded Replanning • Zero Consciousness Self-Model
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
              {/* Goal Header & Controls */}
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

                {/* Telemetry Strip */}
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

              {/* Milestones DAG View */}
              <h3 style={{ fontSize: "15px", color: "#e2e8f0", margin: "0 0 12px" }}>
                Active Plan Milestones ({activePlan?.milestones.length || 0})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "24px" }}>
                {activePlan?.milestones.map((ms, idx) => {
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

                      {/* Evidence Receipts */}
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

              {/* Replanning & Self-Correction History */}
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
    </div>
  );
};
export default GoalsDashboard;
