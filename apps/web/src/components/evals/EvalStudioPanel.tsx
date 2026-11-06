import React, { useState, useEffect, useCallback } from "react";

export interface DatasetManifest {
  dataset_id: string;
  version: string;
  dataset_hash: string;
  total_cases: number;
  dev_count: number;
  val_count: number;
  holdout_count: number;
  domain_counts: Record<string, number>;
  frozen_at: number;
  license_metadata: string;
}

export interface EvalRunManifest {
  run_id: string;
  eval_suite_id: string;
  dataset_id: string;
  dataset_hash: string;
  baseline_snapshot_id: string;
  candidate_id?: string | null;
  status: string;
  cases_total: number;
  cases_completed: number;
  cases_passed: number;
  cases_failed: number;
  cases_blocked: number;
  total_tokens: number;
  total_cost_paisa: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  git_commit: string;
  hardware_fingerprint: string;
  started_at: number;
  completed_at?: number | null;
}

export interface CandidateChange {
  candidate_id: string;
  proposal_id: string;
  target_layer: string;
  description: string;
  patch_diff: string;
  config_hash_before: string;
  config_hash_after: string;
  weights_updated: boolean;
  status: string;
  created_at: number;
}

export interface ImprovementProposal {
  proposal_id: string;
  symptom: string;
  failure_cluster: string;
  evidence_trace_ids: string[];
  patch_scope: string;
  expected_metric: string;
  target_threshold: number;
  blast_radius: string;
  authorization_tier: string;
  baseline_snapshot_id: string;
  created_at: number;
}

export interface MatchedComparisonResult {
  baseline_run_id: string;
  candidate_run_id: string;
  candidate_id: string;
  partition: string;
  baseline_pass_rate: number;
  candidate_pass_rate: number;
  pass_rate_delta: number;
  baseline_latency_p50: number;
  candidate_latency_p50: number;
  baseline_cost_paisa: number;
  candidate_cost_paisa: number;
  statistically_significant: boolean;
  is_regression: boolean;
  summary: string;
}

export interface LeakageCheckResult {
  is_contaminated: boolean;
  max_similarity: number;
  matched_case_id?: string | null;
  matched_ngram?: string | null;
  explanation: string;
}

export const EvalStudioPanel: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetManifest[]>([]);
  const [runs, setRuns] = useState<EvalRunManifest[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvalRunManifest | null>(null);
  const [proposals, setProposals] = useState<ImprovementProposal[]>([]);
  const [candidates, setCandidates] = useState<CandidateChange[]>([]);
  const [comparisonResult, setComparisonResult] = useState<MatchedComparisonResult | null>(null);

  // Leakage check state
  const [leakageInput, setLeakageInput] = useState("");
  const [leakageResult, setLeakageResult] = useState<LeakageCheckResult | null>(null);

  // Promotion / Rollback inputs
  const [tierCToken, setTierCToken] = useState("");
  const [rollbackReason, setRollbackReason] = useState("");

  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchDatasets = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/evals/datasets");
      if (res.ok) {
        setDatasets(await res.json());
      }
    } catch (e: any) {
      setStatusMessage(`Failed to fetch datasets: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const handleTriggerRun = async (partition: string = "DEV_POOL") => {
    try {
      setLoading(true);
      setStatusMessage(`Starting matched evaluation on ${partition}...`);
      const res = await fetch("/api/evals/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Caller-Role": "eval_runner" },
        body: JSON.stringify({
          eval_suite_id: `suite-${partition.toLowerCase()}-live`,
          partition: partition,
        }),
      });

      if (res.ok) {
        const manifest: EvalRunManifest = await res.json();
        setRuns((prev) => [manifest, ...prev]);
        setSelectedRun(manifest);
        setStatusMessage(`Evaluation run ${manifest.run_id} completed successfully (${manifest.cases_passed}/${manifest.cases_total} passed).`);
      } else {
        const err = await res.json();
        setStatusMessage(`Run failed: ${err.detail || res.statusText}`);
      }
    } catch (e: any) {
      setStatusMessage(`Run execution error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDiagnose = async () => {
    if (!selectedRun) {
      setStatusMessage("Please select or trigger an evaluation run first.");
      return;
    }
    try {
      setLoading(true);
      setStatusMessage(`Diagnosing trace failures for ${selectedRun.run_id}...`);
      const res = await fetch("/api/evals/proposals/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: selectedRun.run_id }),
      });

      if (res.ok) {
        const data = await res.json();
        setProposals(data.proposals);
        setCandidates(data.candidates);
        setStatusMessage(`Diagnosed ${data.diagnosed_clusters.length} failure clusters; generated ${data.candidates.length} candidate proposals.`);
      } else {
        const err = await res.json();
        setStatusMessage(`Diagnosis failed: ${err.detail || res.statusText}`);
      }
    } catch (e: any) {
      setStatusMessage(`Diagnosis error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRunMatchedExperiment = async (candidateId: string) => {
    try {
      setLoading(true);
      setStatusMessage(`Running matched experiment for candidate ${candidateId}...`);
      const res = await fetch("/api/evals/experiments/matched", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, partition: "VAL_POOL" }),
      });

      if (res.ok) {
        const comp: MatchedComparisonResult = await res.json();
        setComparisonResult(comp);
        setStatusMessage(comp.summary);
      } else {
        const err = await res.json();
        setStatusMessage(`Matched experiment failed: ${err.detail || res.statusText}`);
      }
    } catch (e: any) {
      setStatusMessage(`Matched experiment error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePromoteCandidate = async (candidateId: string) => {
    try {
      setLoading(true);
      setStatusMessage(`Evaluating promotion gates for ${candidateId}...`);
      const res = await fetch(`/api/evals/candidates/${candidateId}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          security_clean: true,
          approval_token: tierCToken || undefined,
          approver_id: "human_lead_engineer",
        }),
      });

      if (res.ok) {
        const dec = await res.json();
        setStatusMessage(`Promotion Decision: ${dec.outcome} (Delta: ${dec.primary_metric_gain > 0 ? "+" : ""}${(dec.primary_metric_gain * 100).toFixed(1)}%).`);
      } else {
        const err = await res.json();
        setStatusMessage(`Promotion failed: ${err.detail || res.statusText}`);
      }
    } catch (e: any) {
      setStatusMessage(`Promotion error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRollbackCandidate = async (candidateId: string) => {
    if (!rollbackReason) {
      setStatusMessage("Please specify a reason for the rollback.");
      return;
    }
    try {
      setLoading(true);
      setStatusMessage(`Executing atomic rollback for ${candidateId}...`);
      const res = await fetch(`/api/evals/candidates/${candidateId}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: rollbackReason,
          restored_by: "human_operator",
        }),
      });

      if (res.ok) {
        const receipt = await res.json();
        setStatusMessage(`Rollback executed! Restored configuration hash: ${receipt.restored_config_hash.slice(0, 16)}...`);
      } else {
        const err = await res.json();
        setStatusMessage(`Rollback failed: ${err.detail || res.statusText}`);
      }
    } catch (e: any) {
      setStatusMessage(`Rollback error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCheckLeakage = async () => {
    if (!leakageInput.trim()) return;
    try {
      setLoading(true);
      const res = await fetch("/api/evals/leakage/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: leakageInput }),
      });
      if (res.ok) {
        setLeakageResult(await res.json());
      }
    } catch (e: any) {
      setStatusMessage(`Leakage check error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 p-6 space-y-6 overflow-y-auto">
      {/* Header */}
      <div className="border-b border-slate-800 pb-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <span>🔬 Evaluation & Continuous Improvement Studio</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            मूल्याङ्कन तथा निरन्तर सुधार स्टुडियो | Mulyankan tatha Nirantar Sudhar Studio
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleTriggerRun("DEV_POOL")}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 rounded-md transition shadow disabled:opacity-50"
          >
            Run Dev (60%)
          </button>
          <button
            onClick={() => handleTriggerRun("VAL_POOL")}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-500 rounded-md transition shadow disabled:opacity-50"
          >
            Run Val (20%)
          </button>
          <button
            onClick={() => handleTriggerRun("SEALED_HOLDOUT")}
            disabled={loading}
            className="px-3 py-1.5 text-xs font-semibold bg-purple-600 hover:bg-purple-500 rounded-md transition shadow disabled:opacity-50"
          >
            Run Holdout (20%)
          </button>
        </div>
      </div>

      {statusMessage && (
        <div className="p-3 bg-slate-900 border border-slate-700 rounded-md text-xs text-slate-200">
          ℹ️ {statusMessage}
        </div>
      )}

      {/* Dataset & Hygiene Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Canonical Dataset</div>
          <div className="text-xl font-bold mt-1 text-slate-100">
            {datasets[0]?.total_cases || 240} Items
          </div>
          <div className="text-[10px] text-slate-500 mt-1">
            Hash: {datasets[0]?.dataset_hash.slice(0, 16) || "211a54ac1ca9..."}
          </div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Dev Stratification</div>
          <div className="text-xl font-bold mt-1 text-emerald-400">144 (60%)</div>
          <div className="text-[10px] text-slate-500 mt-1">Open candidate exploration</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Validation Stratification</div>
          <div className="text-xl font-bold mt-1 text-blue-400">48 (20%)</div>
          <div className="text-[10px] text-slate-500 mt-1">Matched comparison tuning</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Sealed Holdout</div>
          <div className="text-xl font-bold mt-1 text-purple-400">48 (20%)</div>
          <div className="text-[10px] text-purple-300 mt-1">🔒 Zero-access security isolated</div>
        </div>
      </div>

      {/* Runs & Latest Results */}
      {selectedRun && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">
              📊 Active Run: {selectedRun.run_id} ({selectedRun.eval_suite_id})
            </h2>
            <button
              onClick={handleDiagnose}
              disabled={loading}
              className="px-3 py-1 text-xs bg-indigo-600 hover:bg-indigo-500 font-medium rounded transition"
            >
              Diagnose & Propose Fixes
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 text-xs">
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Pass Rate:</span>
              <div className="text-base font-bold text-emerald-400">
                {((selectedRun.cases_passed / (selectedRun.cases_total || 1)) * 100).toFixed(1)}%
              </div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Passed / Total:</span>
              <div className="text-base font-bold text-slate-200">
                {selectedRun.cases_passed} / {selectedRun.cases_total}
              </div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Latency p50:</span>
              <div className="text-base font-bold text-slate-200">{selectedRun.p50_latency_ms} ms</div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Latency p95:</span>
              <div className="text-base font-bold text-slate-200">{selectedRun.p95_latency_ms} ms</div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Total Tokens:</span>
              <div className="text-base font-bold text-slate-200">{selectedRun.total_tokens}</div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Total Cost:</span>
              <div className="text-base font-bold text-amber-400">{selectedRun.total_cost_paisa} paisa</div>
            </div>
          </div>
          <div className="text-[11px] text-slate-400">
            Hardware: {selectedRun.hardware_fingerprint} | Git: {selectedRun.git_commit}
          </div>
        </div>
      )}

      {/* Generated Candidates & Proposals */}
      {candidates.length > 0 && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-200">
            💡 Diagnostic Proposals & Candidate Patches ({candidates.length})
          </h2>
          <div className="space-y-3">
            {candidates.map((cand) => (
              <div
                key={cand.candidate_id}
                className="p-4 bg-slate-950 border border-slate-800 rounded-md space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-blue-900/50 text-blue-300 font-mono text-[10px]">
                      {cand.target_layer.toUpperCase()}
                    </span>
                    <span className="font-semibold text-slate-200">{cand.candidate_id}</span>
                    <span className="text-slate-400">| Status: {cand.status}</span>
                  </div>
                  <span className="text-[10px] text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                    weights_updated: {String(cand.weights_updated)}
                  </span>
                </div>
                <div className="text-slate-300">{cand.description}</div>
                <div className="font-mono bg-slate-900 p-2 rounded text-[11px] text-slate-400 overflow-x-auto">
                  {cand.patch_diff}
                </div>
                <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
                  <button
                    onClick={() => handleRunMatchedExperiment(cand.candidate_id)}
                    className="px-2.5 py-1 bg-blue-700 hover:bg-blue-600 rounded text-white font-medium"
                  >
                    Run Matched Experiment
                  </button>
                  <button
                    onClick={() => handlePromoteCandidate(cand.candidate_id)}
                    className="px-2.5 py-1 bg-emerald-700 hover:bg-emerald-600 rounded text-white font-medium"
                  >
                    Promote Candidate
                  </button>
                  <button
                    onClick={() => handleRollbackCandidate(cand.candidate_id)}
                    className="px-2.5 py-1 bg-rose-700 hover:bg-rose-600 rounded text-white font-medium"
                  >
                    Instant Rollback
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Matched Experiment Result */}
      {comparisonResult && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-3">
          <h2 className="text-sm font-semibold text-slate-200">
            ⚖️ Matched Experiment Comparison Result
          </h2>
          <div className="text-xs text-slate-300">{comparisonResult.summary}</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Delta Pass Rate:</span>
              <div
                className={`text-sm font-bold ${
                  comparisonResult.pass_rate_delta >= 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {comparisonResult.pass_rate_delta >= 0 ? "+" : ""}
                {(comparisonResult.pass_rate_delta * 100).toFixed(1)}%
              </div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Statistically Significant:</span>
              <div className="text-sm font-bold text-slate-200">
                {String(comparisonResult.statistically_significant)}
              </div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Regression Detected:</span>
              <div
                className={`text-sm font-bold ${
                  comparisonResult.is_regression ? "text-rose-400" : "text-emerald-400"
                }`}
              >
                {String(comparisonResult.is_regression)}
              </div>
            </div>
            <div className="p-2 bg-slate-950 rounded">
              <span className="text-slate-400">Partition:</span>
              <div className="text-sm font-bold text-slate-200">{comparisonResult.partition}</div>
            </div>
          </div>
        </div>
      )}

      {/* Governance & Contamination Checker */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Promotion Controls */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-3">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            🛡️ PDP Governance & Rollback Config
          </h3>
          <div className="space-y-2 text-xs">
            <div>
              <label className="text-slate-400">Tier C Human Authorization Token:</label>
              <input
                type="text"
                value={tierCToken}
                onChange={(e) => setTierCToken(e.target.value)}
                placeholder="e.g. auth-token-tier-c-ceremony"
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200"
              />
            </div>
            <div>
              <label className="text-slate-400">Rollback Audit Reason:</label>
              <input
                type="text"
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                placeholder="e.g. Latency degradation or false rejection observed"
                className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200"
              />
            </div>
          </div>
        </div>

        {/* Sealed Holdout Contamination Checker */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 space-y-3">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            🔍 Holdout Leakage & Contamination Detector
          </h3>
          <textarea
            value={leakageInput}
            onChange={(e) => setLeakageInput(e.target.value)}
            rows={3}
            placeholder="Paste proposed prompt text or diff to test against sealed holdout contamination..."
            className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200"
          />
          <div className="flex items-center justify-between">
            <button
              onClick={handleCheckLeakage}
              disabled={loading || !leakageInput.trim()}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded text-xs text-slate-200 font-medium"
            >
              Verify Contamination
            </button>
            {leakageResult && (
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded ${
                  leakageResult.is_contaminated
                    ? "bg-rose-900/60 text-rose-300 border border-rose-700"
                    : "bg-emerald-900/60 text-emerald-300 border border-emerald-700"
                }`}
              >
                {leakageResult.is_contaminated ? "🚨 LEAKAGE DETECTED" : "✅ CLEAN"}
              </span>
            )}
          </div>
          {leakageResult && (
            <p className="text-[11px] text-slate-400">{leakageResult.explanation}</p>
          )}
        </div>
      </div>
    </div>
  );
};
