import React, { useState, useEffect, useCallback } from "react";

export type MissionStatusType =
  | "CREATED"
  | "SCOPING"
  | "PLANNING"
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "PAUSED_OFFLINE"
  | "RECOVERING"
  | "VERIFYING"
  | "COMPLETED_VERIFIED"
  | "PARTIAL"
  | "BLOCKED_UNAVAILABLE"
  | "FAILED"
  | "CANCELLED";

export type AutonomousModeType = "REACTIVE" | "BOUNDED_DELEGATED" | "SCHEDULED" | "PROACTIVE_SUGGESTION";

export interface TypedArtifact {
  artifact_id: string;
  artifact_type: string;
  title: string;
  content_digest: string;
  tenant_id: string;
  producer_role: string;
  confidence: number;
  limitations: string[];
  created_at: number;
  payload: Record<string, any>;
  file_path?: string | null;
  file_size_bytes: number;
  is_verified: boolean;
  verification_method: string;
}

export interface UnifiedMission {
  mission_id: string;
  tenant_id: string;
  authenticated_actor: string;
  objective: string;
  success_rubric: string;
  constraints: string[];
  deployment_profile: string;
  capability_snapshot: Record<string, string>;
  budget: {
    max_tokens: number;
    max_cost_paisa: number;
    spent_tokens: number;
    spent_cost_paisa: number;
    spent_duration_seconds: number;
  };
  consent_state: string;
  goal_dag_version: number;
  evidence_refs: Array<{ artifact_id: string; type: string; digest: string; verified: boolean }>;
  output_artifacts: TypedArtifact[];
  run_state: MissionStatusType;
  autonomous_mode: AutonomousModeType;
  audit_correlation_id: string;
  status_reason?: string | null;
  reason_code?: string | null;
  created_at: number;
  updated_at: number;
}

export interface CapabilityItem {
  status: "AVAILABLE_VERIFIED" | "AVAILABLE_DEGRADED" | "CONFIG_REQUIRED" | "BLOCKED_UNAVAILABLE" | "APPROVAL_REQUIRED";
  provider: string;
  evidence: string;
  limitations: string[];
}

export interface MissionCenterPanelProps {
  apiBaseUrl?: string;
  onRefresh?: () => void;
}

export const MissionCenterPanel: React.FC<MissionCenterPanelProps> = ({
  apiBaseUrl = "/api",
  onRefresh,
}) => {
  const [missions, setMissions] = useState<UnifiedMission[]>([]);
  const [selectedMission, setSelectedMission] = useState<UnifiedMission | null>(null);
  const [capabilities, setCapabilities] = useState<Record<string, CapabilityItem>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // New Mission Form State
  const [objective, setObjective] = useState("");
  const [mode, setMode] = useState<AutonomousModeType>("BOUNDED_DELEGATED");
  const [budgetCentsPaisa, setBudgetCentsPaisa] = useState<number>(5000); // 50 NPR

  // Trilingual toggle: 'en' | 'np' | 'np-roman'
  const [lang, setLang] = useState<"en" | "np" | "np-roman">("en");

  const t = {
    title: {
      en: "Mission Center & Autonomous Convergence",
      np: "अभियान केन्द्र तथा स्वायत्त अभिसरण",
      "np-roman": "Mission Kendra tatha Swayatta Abhisaran",
    },
    subtitle: {
      en: "Phase 18 Capstone — Cross-Domain Outcomes, Verifiable Artifacts & Honest Capability Governance",
      np: "चरण १८ क्यापस्टोन — बहु-क्षेत्र नतिजा, प्रमाणित कलाकृति र पारदर्शी क्षमता व्यवस्थापन",
      "np-roman": "Charan 18 Capstone — Bahu-kshetra Natija, Pramanit Kalakriti ra Pardarshi Kshamata",
    },
    newMissionTitle: {
      en: "Launch Autonomous Mission",
      np: "नयाँ स्वायत्त अभियान सुरु गर्नुहोस्",
      "np-roman": "Naya Swayatta Mission Suru Garnuhos",
    },
    objectivePlaceholder: {
      en: "Describe your goal (e.g., 'Research latest AI papers, build a Python parser, test and verify')...",
      np: "आफ्नो लक्ष्य विवरण गर्नुहोस् (उदा: 'नयाँ एआई अनुसन्धान खोज्नुहोस्, कोड लेख्नुहोस् र परीक्षण गर्नुहोस्')...",
      "np-roman": "Aafno lakshya bibaran garnuhos...",
    },
    launchBtn: {
      en: "Dispatch Mission",
      np: "अभियान प्रेषण गर्नुहोस्",
      "np-roman": "Mission Preshan Garnuhos",
    },
    activeMissionsTitle: {
      en: "Active & Historic Missions",
      np: "सक्रिय तथा विगतका अभियानहरू",
      "np-roman": "Sakriya tatha Bigatka Missionharu",
    },
    capabilityTruthTitle: {
      en: "Empirical Capability Truth Matrix",
      np: "वास्तविक क्षमता सत्यता तालिका",
      "np-roman": "Bastabik Kshamata Satyata Talika",
    },
    artifactsTitle: {
      en: "Verified Output Artifacts",
      np: "प्रमाणित उत्पादित सामग्री तथा कलाकृतिहरू",
      "np-roman": "Pramanit Utpadit Samagri ra Kalakritiharu",
    },
    approvalNotice: {
      en: "Tier C Action Awaiting Human Authorization",
      np: "टियर सी कार्य मानव स्वीकृतिको प्रतीक्षामा छ",
      "np-roman": "Tier C Karye Manav Swikritiko Pratikshama Chha",
    },
    approveBtn: {
      en: "Approve Exact Parameters",
      np: "निश्चित प्यारामिटरहरू स्वीकृत गर्नुहोस्",
      "np-roman": "Swikrit Garnuhos",
    },
    rejectBtn: {
      en: "Reject Action",
      np: "अस्वीकार गर्नुहोस्",
      "np-roman": "Aswikar Garnuhos",
    },
  };

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      // 1. Fetch missions
      const mRes = await fetch(`${apiBaseUrl}/convergence/missions`).catch(() => null);
      if (mRes && mRes.ok) {
        const mData: UnifiedMission[] = await mRes.json();
        setMissions(mData);
        if (mData.length > 0 && !selectedMission) {
          setSelectedMission(mData[0]);
        } else if (selectedMission) {
          const updated = mData.find((m) => m.mission_id === selectedMission.mission_id);
          if (updated) setSelectedMission(updated);
        }
      }

      // 2. Fetch capabilities
      const cRes = await fetch(`${apiBaseUrl}/convergence/capabilities`).catch(() => null);
      if (cRes && cRes.ok) {
        setCapabilities(await cRes.json());
      }
    } catch (err) {
      console.warn("Error fetching convergence data:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl, selectedMission]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleCreateMission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!objective.trim()) return;

    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/convergence/missions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          objective: objective.trim(),
          autonomous_mode: mode,
          budget_paisa: budgetCentsPaisa,
        }),
      });
      if (res.ok) {
        const created: UnifiedMission = await res.json();
        setObjective("");
        setSelectedMission(created);
        setActionNotice(`Mission ${created.mission_id} created successfully.`);
        fetchData();
      } else {
        setActionNotice("Failed to launch mission.");
      }
    } catch (err: any) {
      setActionNotice(`Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAction = async (action: string) => {
    if (!selectedMission) return;
    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/convergence/missions/${selectedMission.mission_id}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedMission(updated);
        setActionNotice(`Action '${action}' applied to mission ${selectedMission.mission_id}.`);
        fetchData();
      } else {
        const err = await res.json().catch(() => ({ detail: "Action failed" }));
        setActionNotice(`Failed: ${err.detail}`);
      }
    } catch (err: any) {
      setActionNotice(`Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleApproval = async (approved: boolean) => {
    if (!selectedMission) return;
    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/convergence/missions/${selectedMission.mission_id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ceremony_id: "ceremony_p18_user",
          action: "MUTATING_OPERATION",
          parameters: { target: "user_approval" },
          approved,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedMission(updated);
        setActionNotice(approved ? "Action approved by user." : "Action rejected by user.");
        fetchData();
      }
    } catch (err: any) {
      setActionNotice(`Approval error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 p-6 overflow-y-auto space-y-6">
      {/* Header & Trilingual Selector */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-800 pb-4 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <span className="w-3.5 h-3.5 rounded-full bg-cyan-400 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight text-white">{t.title[lang]}</h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-700/60 font-mono">
              Phase 18 Capstone
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">{t.subtitle[lang]}</p>
        </div>

        <div className="flex items-center space-x-3">
          {/* Trilingual Toggle */}
          <div className="flex bg-slate-900 border border-slate-700 rounded-lg p-1 text-xs">
            <button
              onClick={() => setLang("en")}
              className={`px-2 py-1 rounded ${lang === "en" ? "bg-cyan-600 text-white font-medium" : "text-slate-400 hover:text-white"}`}
            >
              English
            </button>
            <button
              onClick={() => setLang("np")}
              className={`px-2 py-1 rounded ${lang === "np" ? "bg-cyan-600 text-white font-medium" : "text-slate-400 hover:text-white"}`}
            >
              नेपाली
            </button>
            <button
              onClick={() => setLang("np-roman")}
              className={`px-2 py-1 rounded ${lang === "np-roman" ? "bg-cyan-600 text-white font-medium" : "text-slate-400 hover:text-white"}`}
            >
              Roman
            </button>
          </div>

          <button
            onClick={() => { fetchData(); onRefresh?.(); }}
            disabled={isLoading}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded-lg border border-slate-700 transition"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Action Notification */}
      {actionNotice && (
        <div className="p-3 bg-cyan-950/70 border border-cyan-800/80 rounded-lg text-sm text-cyan-200 flex justify-between items-center">
          <span>{actionNotice}</span>
          <button onClick={() => setActionNotice(null)} className="text-xs text-cyan-400 hover:text-white font-mono">
            [x]
          </button>
        </div>
      )}

      {/* Row 1: Mission Launch & Active Missions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Launch Mission Form */}
        <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4 lg:col-span-1">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            {t.newMissionTitle[lang]}
          </h2>
          <form onSubmit={handleCreateMission} className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Objective</label>
              <textarea
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder={t.objectivePlaceholder[lang]}
                rows={3}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">Autonomous Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as AutonomousModeType)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="BOUNDED_DELEGATED">Bounded Delegated</option>
                  <option value="REACTIVE">Reactive (Fast)</option>
                  <option value="SCHEDULED">Scheduled Recurring</option>
                  <option value="PROACTIVE_SUGGESTION">Proactive Suggest</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Budget Ceiling (NPR)</label>
                <input
                  type="number"
                  value={budgetCentsPaisa / 100}
                  onChange={(e) => setBudgetCentsPaisa(Math.max(100, Math.round(parseFloat(e.target.value || "0") * 100)))}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-slate-200 focus:outline-none focus:border-cyan-500"
                  step="1"
                  min="1"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !objective.trim()}
              className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-medium text-xs rounded-lg transition"
            >
              {t.launchBtn[lang]}
            </button>
          </form>
        </div>

        {/* Missions Feed */}
        <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3 lg:col-span-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            {t.activeMissionsTitle[lang]} ({missions.length})
          </h2>

          {missions.length === 0 ? (
            <div className="p-6 bg-slate-950/60 rounded-lg border border-slate-800 text-center text-xs text-slate-500">
              No active or historic missions recorded. Enter an objective above to dispatch an autonomous convergence task.
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {missions.map((m) => {
                const isSelected = selectedMission?.mission_id === m.mission_id;
                return (
                  <div
                    key={m.mission_id}
                    onClick={() => setSelectedMission(m)}
                    className={`p-3 rounded-lg border cursor-pointer transition flex items-center justify-between text-xs ${
                      isSelected
                        ? "bg-cyan-950/40 border-cyan-500"
                        : "bg-slate-950 hover:bg-slate-900 border-slate-800"
                    }`}
                  >
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-mono font-bold text-white">{m.mission_id}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium ${
                            m.run_state === "COMPLETED_VERIFIED"
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                              : m.run_state === "WAITING_APPROVAL"
                              ? "bg-amber-950 text-amber-300 border border-amber-700"
                              : m.run_state === "RUNNING"
                              ? "bg-cyan-950 text-cyan-300 border border-cyan-700 animate-pulse"
                              : "bg-slate-800 text-slate-400"
                          }`}
                        >
                          {m.run_state}
                        </span>
                      </div>
                      <p className="text-slate-400 text-xs mt-1 line-clamp-1">{m.objective}</p>
                    </div>

                    <div className="text-right font-mono text-[11px] text-slate-400">
                      <div>रु {(m.budget.spent_cost_paisa / 100).toFixed(2)}</div>
                      <div className="text-[10px] text-slate-500">{m.evidence_refs.length} artifacts</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Row 2: Selected Mission Deep Dive & Governance Controls */}
      {selectedMission && (
        <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div>
              <div className="flex items-center space-x-3">
                <span className="text-base font-mono font-bold text-white">{selectedMission.mission_id}</span>
                <span className="text-xs text-slate-400">Correlation: {selectedMission.audit_correlation_id}</span>
              </div>
              <p className="text-xs text-slate-300 mt-1 font-medium">{selectedMission.objective}</p>
            </div>

            {/* Mission Controls */}
            <div className="flex items-center space-x-2">
              {selectedMission.run_state === "RUNNING" && (
                <button
                  onClick={() => handleAction("pause")}
                  className="px-2.5 py-1 bg-amber-900/50 hover:bg-amber-900 text-amber-200 border border-amber-700 rounded text-xs"
                >
                  Pause
                </button>
              )}
              {selectedMission.run_state === "PAUSED_OFFLINE" && (
                <button
                  onClick={() => handleAction("resume")}
                  className="px-2.5 py-1 bg-emerald-900/50 hover:bg-emerald-900 text-emerald-200 border border-emerald-700 rounded text-xs"
                >
                  Resume
                </button>
              )}
              {!["COMPLETED_VERIFIED", "PARTIAL", "BLOCKED_UNAVAILABLE", "FAILED", "CANCELLED"].includes(selectedMission.run_state) && (
                <button
                  onClick={() => handleAction("cancel")}
                  className="px-2.5 py-1 bg-rose-900/50 hover:bg-rose-900 text-rose-200 border border-rose-700 rounded text-xs"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>

          {/* Pending Tier C Approval Banner */}
          {selectedMission.run_state === "WAITING_APPROVAL" && (
            <div className="p-4 bg-amber-950/50 border border-amber-600 rounded-lg space-y-3">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
                <span className="text-sm font-bold text-amber-300">{t.approvalNotice[lang]}</span>
              </div>
              <p className="text-xs text-slate-300">
                {selectedMission.status_reason || "This operation involves external mutations, financial disbursements, or privileged tool execution. Human authorization required."}
              </p>
              <div className="flex space-x-3">
                <button
                  onClick={() => handleApproval(true)}
                  className="px-3 py-1.5 bg-amber-500 hover:bg-amber-400 text-black font-semibold rounded text-xs"
                >
                  {t.approveBtn[lang]}
                </button>
                <button
                  onClick={() => handleApproval(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded text-xs border border-slate-700"
                >
                  {t.rejectBtn[lang]}
                </button>
              </div>
            </div>
          )}

          {/* Output Artifacts Section */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {t.artifactsTitle[lang]} ({selectedMission.output_artifacts?.length || 0})
            </h3>

            {(!selectedMission.output_artifacts || selectedMission.output_artifacts.length === 0) ? (
              <div className="p-4 bg-slate-950/50 rounded-lg border border-slate-800 text-center text-xs text-slate-500">
                Zero output artifacts produced yet. Task is executing or pending completion.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {selectedMission.output_artifacts.map((art) => (
                  <div key={art.artifact_id} className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-2 text-xs">
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-white">{art.title}</span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 font-mono text-cyan-300">
                        {art.artifact_type}
                      </span>
                    </div>
                    <div className="font-mono text-[10px] text-slate-500 truncate">
                      SHA256: {art.content_digest}
                    </div>
                    <div className="flex justify-between items-center text-[11px] text-slate-400 pt-1">
                      <span>{art.file_size_bytes} bytes</span>
                      <span className={`font-semibold ${art.is_verified ? "text-emerald-400" : "text-amber-400"}`}>
                        {art.is_verified ? "VERIFIED (Checksum Matched)" : "UNVERIFIED"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Row 3: Empirical Capability Truth Matrix */}
      <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          {t.capabilityTruthTitle[lang]}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {Object.entries(capabilities).map(([capName, cap]) => {
            const isVerified = cap.status === "AVAILABLE_VERIFIED";
            const isBlocked = cap.status === "BLOCKED_UNAVAILABLE";
            const isApproval = cap.status === "APPROVAL_REQUIRED";
            return (
              <div key={capName} className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-slate-200">{capName}</span>
                  <span
                    className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold ${
                      isVerified
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : isBlocked
                        ? "bg-rose-950 text-rose-400 border border-rose-800"
                        : isApproval
                        ? "bg-amber-950 text-amber-300 border border-amber-800"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {cap.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">{cap.evidence}</p>
                {cap.limitations.length > 0 && (
                  <p className="text-[10px] text-slate-500 italic">Notice: {cap.limitations[0]}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
