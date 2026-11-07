import React, { useState, useEffect, useCallback } from "react";

export interface ScheduleItem {
  schedule_id: string;
  name: string;
  description: string;
  schedule_type: "ONE_SHOT" | "INTERVAL" | "CRON" | "EVENT_TRIGGERED" | "CONDITION";
  cron_expr?: string;
  interval_seconds?: number;
  timezone: string;
  is_paused: boolean;
  run_count: number;
  max_runs?: number;
  next_fire_time_utc?: number;
  task_template: {
    goal: string;
    permission_tier: "TIER_A" | "TIER_B" | "TIER_C";
    budget_tokens: number;
    budget_paisa: number;
    allowed_tools: string[];
    ancestry: string;
  };
}

export interface JobItem {
  job_id: string;
  schedule_id?: string;
  task_id: string;
  status: "CREATED" | "SCHEDULED" | "READY" | "CLAIMED" | "RUNNING" | "WAITING_APPROVAL" | "RETRY_PENDING" | "COMPLETED" | "FAILED" | "CANCELLED";
  attempt_count: number;
  max_attempts: number;
  fencing_token: number;
  scheduled_for_utc: number;
  started_at_utc?: number;
  completed_at_utc?: number;
  error_message?: string;
  ancestry: string;
  budget_tokens: number;
  consumed_tokens: number;
  budget_paisa: number;
  consumed_paisa: number;
  artifacts: Array<{ name: string; path: string }>;
  trace_id: string;
  metadata?: { goal?: string } & Record<string, unknown>;
}

export interface NotificationItem {
  notification_id: string;
  event_type: string;
  title: string;
  message: string;
  job_id?: string;
  schedule_id?: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  is_read: boolean;
  created_at_utc: number;
}

export interface HealthReport {
  scheduler_alive: boolean;
  worker_alive: boolean;
  gpu_vram_allocated_mb: number;
  gpu_vram_max_mb: number;
  active_browsers: number;
  active_sandboxes: number;
  latencies: {
    count: number;
    avg_queue_lag_ms: number;
    p50_duration_ms: number;
    p95_duration_ms: number;
    p99_duration_ms: number;
  };
  status: string;
}

export const AutopilotDashboard: React.FC = () => {
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [lang, setLang] = useState<"en" | "ne">("en");
  const [isLoading, setIsLoading] = useState(false);
  const [isEmergencyStopped, setIsEmergencyStopped] = useState(false);

  // Form State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formName, setFormName] = useState("");
  const [formGoal, setFormGoal] = useState("");
  const [formType, setFormType] = useState<"INTERVAL" | "CRON" | "ONE_SHOT">("INTERVAL");
  const [formInterval, setFormInterval] = useState(300);
  const [formCron, setFormCron] = useState("0 * * * *");
  const [formTimezone, setFormTimezone] = useState("Asia/Kathmandu");
  const [formTier, setFormTier] = useState<"TIER_A" | "TIER_B" | "TIER_C">("TIER_A");
  const [formPaisa, setFormPaisa] = useState(25000);

  // Load Data
  const fetchData = useCallback(async () => {
    try {
      const [resSched, resJobs, resNotifs, resHealth] = await Promise.all([
        fetch("/api/autopilot/schedules"),
        fetch("/api/autopilot/jobs"),
        fetch("/api/autopilot/notifications"),
        fetch("/api/autopilot/health"),
      ]);

      if (resSched.ok) {
        const data = await resSched.json();
        setSchedules(data.schedules || []);
      }
      if (resJobs.ok) {
        const data = await resJobs.json();
        setJobs(data.jobs || []);
      }
      if (resNotifs.ok) {
        const data = await resNotifs.json();
        setNotifications(data.notifications || []);
      }
      if (resHealth.ok) {
        const data = await resHealth.json();
        setHealth(data);
      }
    } catch (err) {
      console.error("Failed to fetch autopilot data:", err);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Actions
  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const payload: any = {
        name: formName,
        goal: formGoal,
        schedule_type: formType,
        timezone: formTimezone,
        permission_tier: formTier,
        budget_paisa: formPaisa,
        allowed_tools: formTier === "TIER_A" ? ["sandbox_read", "search_web"] : ["*"],
      };
      if (formType === "INTERVAL") payload.interval_seconds = formInterval;
      if (formType === "CRON") payload.cron_expr = formCron;

      const res = await fetch("/api/autopilot/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setIsCreateModalOpen(false);
        setFormName("");
        setFormGoal("");
        fetchData();
      }
    } catch (err) {
      console.error("Create schedule failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePauseResume = async (scheduleId: string, isPaused: boolean) => {
    const action = isPaused ? "resume" : "pause";
    try {
      await fetch(`/api/autopilot/schedules/${scheduleId}/${action}`, { method: "POST" });
      fetchData();
    } catch (err) {
      console.error(`Failed to ${action} schedule:`, err);
    }
  };

  const handleDeleteSchedule = async (scheduleId: string) => {
    if (!confirm(lang === "en" ? "Delete this schedule?" : "यो तालिका मेटाउनुहुन्छ?")) return;
    try {
      await fetch(`/api/autopilot/schedules/${scheduleId}`, { method: "DELETE" });
      fetchData();
    } catch (err) {
      console.error("Failed to delete schedule:", err);
    }
  };

  const handleEmergencyStop = async () => {
    const promptText = lang === "en"
      ? "EMERGENCY STOP: This will immediately halt all autonomous workers and pause schedules. Proceed?"
      : "आपतकालीन बन्द: यसले सबै स्वचालित कार्यहरू तुरुन्त रोक्नेछ। अगाडि बढ्नुहुन्छ?";
    if (!confirm(promptText)) return;

    try {
      const res = await fetch("/api/autopilot/emergency-stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: "default" }),
      });
      if (res.ok) {
        setIsEmergencyStopped(true);
        fetchData();
      }
    } catch (err) {
      console.error("Emergency stop failed:", err);
    }
  };

  const handleRevokeEmergencyStop = async () => {
    try {
      const res = await fetch("/api/autopilot/emergency-stop/revoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: "default" }),
      });
      if (res.ok) {
        setIsEmergencyStopped(false);
        fetchData();
      }
    } catch (err) {
      console.error("Revoke emergency stop failed:", err);
    }
  };

  const handleApprove = async (jobId: string, approved: boolean) => {
    try {
      await fetch(`/api/autopilot/approvals/${jobId}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      });
      fetchData();
    } catch (err) {
      console.error("Approval decide failed:", err);
    }
  };

  const formatPaisa = (paisa: number) => {
    const npr = (paisa / 100).toFixed(2);
    return `रू ${npr}`;
  };

  const formatKathmanduTime = (utcEpoch?: number) => {
    if (!utcEpoch) return "—";
    return new Date(utcEpoch * 1000).toLocaleString("en-US", {
      timeZone: "Asia/Kathmandu",
      dateStyle: "medium",
      timeStyle: "short",
    }) + " (NPT)";
  };

  const pendingApprovals = jobs.filter((j) => j.status === "WAITING_APPROVAL");

  return (
    <div className="flex flex-col h-full bg-zinc-950 text-zinc-100 p-6 space-y-6 overflow-y-auto">
      {/* HEADER & CONTROLS */}
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">
              {lang === "en" ? "Persistent Autopilot Operations" : "स्वचालित स्वायत्त सञ्चालन केन्द्र"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Phase 13 Active
            </span>
            {isEmergencyStopped && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse">
                EMERGENCY STOPPED
              </span>
            )}
          </div>
          <p className="text-sm text-zinc-400 mt-1">
            {lang === "en"
              ? "Durable background execution, verified schedules, and ancestry governance."
              : "निरन्तर पृष्ठभूमि कार्यहरू, प्रमाणित तालिकाहरू, र वंशावली सुरक्षा।"}
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setLang(lang === "en" ? "ne" : "en")}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition"
          >
            {lang === "en" ? "नेपाली (NE)" : "English (EN)"}
          </button>

          {!isEmergencyStopped ? (
            <button
              onClick={handleEmergencyStop}
              className="px-4 py-1.5 text-xs font-bold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-lg transition flex items-center space-x-1.5"
            >
              <span>⛔</span>
              <span>{lang === "en" ? "Emergency Stop" : "आपतकालीन बन्द"}</span>
            </button>
          ) : (
            <button
              onClick={handleRevokeEmergencyStop}
              className="px-4 py-1.5 text-xs font-bold rounded-lg bg-amber-600 hover:bg-amber-700 text-white shadow-lg transition flex items-center space-x-1.5"
            >
              <span>⚡</span>
              <span>{lang === "en" ? "Revoke Stop" : "पुनः सञ्चालन"}</span>
            </button>
          )}

          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-md transition"
          >
            + {lang === "en" ? "New Schedule" : "नयाँ तालिका"}
          </button>
        </div>
      </div>

      {/* TELEMETRY CARDS */}
      {health && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <span className="text-xs text-zinc-500 uppercase tracking-wider">{lang === "en" ? "Scheduler Status" : "तालिका अवस्था"}</span>
            <div className="text-lg font-bold text-emerald-400 mt-1 flex items-center space-x-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>{health.status}</span>
            </div>
            <span className="text-xs text-zinc-500 mt-1 block">p50 lag: {health.latencies.avg_queue_lag_ms.toFixed(1)}ms</span>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <span className="text-xs text-zinc-500 uppercase tracking-wider">{lang === "en" ? "GPU VRAM Allocation" : "GPU VRAM प्रयोग"}</span>
            <div className="text-lg font-bold text-zinc-100 mt-1">
              {health.gpu_vram_allocated_mb} / {health.gpu_vram_max_mb} MB
            </div>
            <div className="w-full bg-zinc-800 rounded-full h-1.5 mt-2">
              <div
                className="bg-indigo-500 h-1.5 rounded-full"
                style={{ width: `${Math.min(100, (health.gpu_vram_allocated_mb / health.gpu_vram_max_mb) * 100)}%` }}
              />
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <span className="text-xs text-zinc-500 uppercase tracking-wider">{lang === "en" ? "Concurrency Pools" : "समानान्तर सीमा"}</span>
            <div className="text-lg font-bold text-zinc-100 mt-1">
              {health.active_browsers} Browsers / {health.active_sandboxes} Sandboxes
            </div>
            <span className="text-xs text-zinc-500 mt-1 block">Active sandbox workers</span>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <span className="text-xs text-zinc-500 uppercase tracking-wider">{lang === "en" ? "Execution Latency" : "कार्य निष्पादन ढिलाइ"}</span>
            <div className="text-lg font-bold text-zinc-100 mt-1">
              p95: {health.latencies.p95_duration_ms.toFixed(0)}ms
            </div>
            <span className="text-xs text-zinc-500 mt-1 block">Total jobs: {health.latencies.count}</span>
          </div>
        </div>
      )}

      {/* PENDING APPROVALS QUEUE (TIER C) */}
      {pendingApprovals.length > 0 && (
        <div className="p-5 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-3">
          <div className="flex items-center space-x-2 text-amber-400">
            <span className="text-lg">⚠️</span>
            <h2 className="text-sm font-bold uppercase tracking-wider">
              {lang === "en" ? "Pending Tier C Approvals" : "स्वीकृति पर्खिरहेका महत्वपूर्ण कार्यहरू"} ({pendingApprovals.length})
            </h2>
          </div>
          <div className="space-y-2">
            {pendingApprovals.map((j) => (
              <div key={j.job_id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/80 border border-zinc-800">
                <div>
                  <div className="text-sm font-semibold text-white">{j.metadata?.goal || j.job_id}</div>
                  <div className="text-xs text-zinc-400 mt-0.5">
                    Ancestry: <span className="font-mono text-zinc-300">{j.ancestry}</span> | Amount: <span className="text-amber-400 font-semibold">{formatPaisa(j.budget_paisa)}</span>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleApprove(j.job_id, true)}
                    className="px-3 py-1 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition"
                  >
                    {lang === "en" ? "Approve" : "स्वीकृत"}
                  </button>
                  <button
                    onClick={() => handleApprove(j.job_id, false)}
                    className="px-3 py-1 text-xs font-bold rounded-lg bg-zinc-700 hover:bg-zinc-600 text-zinc-200 transition"
                  >
                    {lang === "en" ? "Reject" : "अस्वीकृत"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SCHEDULES TABLE */}
      <div className="p-5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-zinc-100">
            {lang === "en" ? "Active Autonomous Schedules" : "सक्रिय स्वचालित तालिकाहरू"} ({schedules.length})
          </h2>
        </div>

        {schedules.length === 0 ? (
          <div className="py-8 text-center text-sm text-zinc-500">
            {lang === "en" ? "No schedules configured. Click '+ New Schedule' to begin." : "कुनै तालिका भेटिएन। नयाँ तालिका सिर्जना गर्नुहोस्।"}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800">
                <tr>
                  <th className="py-2.5 px-3">Name</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Next Fire (Kathmandu)</th>
                  <th className="py-2.5 px-3">Runs</th>
                  <th className="py-2.5 px-3">Tier</th>
                  <th className="py-2.5 px-3">Budget</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {schedules.map((s) => (
                  <tr key={s.schedule_id} className="hover:bg-zinc-800/30">
                    <td className="py-3 px-3 font-medium text-white">{s.name}</td>
                    <td className="py-3 px-3 text-zinc-400">
                      {s.schedule_type} {s.schedule_type === "INTERVAL" ? `(${s.interval_seconds}s)` : `(${s.cron_expr})`}
                    </td>
                    <td className="py-3 px-3 text-zinc-300 font-mono">
                      {formatKathmanduTime(s.next_fire_time_utc)}
                    </td>
                    <td className="py-3 px-3 text-zinc-400">{s.run_count}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        s.task_template.permission_tier === "TIER_A"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : s.task_template.permission_tier === "TIER_B"
                          ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      }`}>
                        {s.task_template.permission_tier}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-zinc-300 font-mono">{formatPaisa(s.task_template.budget_paisa)}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        s.is_paused ? "bg-zinc-800 text-zinc-400" : "bg-emerald-500/20 text-emerald-300"
                      }`}>
                        {s.is_paused ? "PAUSED" : "ACTIVE"}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <button
                        onClick={() => handlePauseResume(s.schedule_id, s.is_paused)}
                        className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                      >
                        {s.is_paused ? "Resume" : "Pause"}
                      </button>
                      <button
                        onClick={() => handleDeleteSchedule(s.schedule_id)}
                        className="text-xs text-rose-400 hover:text-rose-300 transition"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ACTIVE & RECENT JOBS QUEUE */}
      <div className="p-5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
        <h2 className="text-base font-semibold text-zinc-100">
          {lang === "en" ? "Recent Autonomous Executions" : "हालैका कार्य कार्यान्वयनहरू"} ({jobs.length})
        </h2>

        {jobs.length === 0 ? (
          <div className="py-8 text-center text-sm text-zinc-500">
            {lang === "en" ? "No jobs executed yet." : "हाल कुनै कार्य सञ्चालन भएको छैन।"}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800">
                <tr>
                  <th className="py-2.5 px-3">Job ID</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Attempts</th>
                  <th className="py-2.5 px-3">Fencing Token</th>
                  <th className="py-2.5 px-3">Cost (NPR)</th>
                  <th className="py-2.5 px-3">Artifacts</th>
                  <th className="py-2.5 px-3">Scheduled For</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {jobs.slice(0, 15).map((j) => (
                  <tr key={j.job_id} className="hover:bg-zinc-800/30">
                    <td className="py-3 px-3 font-mono text-zinc-300">{j.job_id}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        j.status === "COMPLETED"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : j.status === "FAILED"
                          ? "bg-rose-500/20 text-rose-400"
                          : j.status === "WAITING_APPROVAL"
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-blue-500/20 text-blue-400"
                      }`}>
                        {j.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-zinc-400">{j.attempt_count} / {j.max_attempts}</td>
                    <td className="py-3 px-3 text-zinc-400 font-mono">#{j.fencing_token}</td>
                    <td className="py-3 px-3 text-zinc-300 font-mono">{formatPaisa(j.consumed_paisa)}</td>
                    <td className="py-3 px-3 text-zinc-400">
                      {j.artifacts.length > 0 ? `${j.artifacts.length} file(s)` : "None"}
                    </td>
                    <td className="py-3 px-3 text-zinc-400 font-mono">
                      {formatKathmanduTime(j.scheduled_for_utc)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* CREATE SCHEDULE MODAL */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-lg font-bold text-white">
                {lang === "en" ? "Configure New Autonomous Schedule" : "नयाँ स्वचालित तालिका सिर्जना गर्नुहोस्"}
              </h3>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-zinc-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateSchedule} className="space-y-4 text-xs">
              <div>
                <label className="block text-zinc-400 mb-1">Schedule Name</label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g., Weekly Repo Health Check"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="block text-zinc-400 mb-1">Mission Goal</label>
                <textarea
                  required
                  value={formGoal}
                  onChange={(e) => setFormGoal(e.target.value)}
                  placeholder="e.g., Inspect repository, run sandbox tests, save defect reports"
                  rows={2}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-400 mb-1">Trigger Type</label>
                  <select
                    value={formType}
                    onChange={(e: any) => setFormType(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="INTERVAL">Interval</option>
                    <option value="CRON">Cron Expression</option>
                    <option value="ONE_SHOT">One-Shot</option>
                  </select>
                </div>

                <div>
                  <label className="block text-zinc-400 mb-1">Timezone</label>
                  <input
                    type="text"
                    value={formTimezone}
                    onChange={(e) => setFormTimezone(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>

              {formType === "INTERVAL" && (
                <div>
                  <label className="block text-zinc-400 mb-1">Interval (Seconds, min 10s)</label>
                  <input
                    type="number"
                    min={10}
                    value={formInterval}
                    onChange={(e) => setFormInterval(parseInt(e.target.value) || 300)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              )}

              {formType === "CRON" && (
                <div>
                  <label className="block text-zinc-400 mb-1">Cron Expression (5-part)</label>
                  <input
                    type="text"
                    value={formCron}
                    onChange={(e) => setFormCron(e.target.value)}
                    placeholder="0 9 * * 1-5"
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-400 mb-1">Permission Tier</label>
                  <select
                    value={formTier}
                    onChange={(e: any) => setFormTier(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="TIER_A">Tier A (Read-only / Safe)</option>
                    <option value="TIER_B">Tier B (Sandbox Modification)</option>
                    <option value="TIER_C">Tier C (Approval Required)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-zinc-400 mb-1">Budget Ceiling (Paisa)</label>
                  <input
                    type="number"
                    value={formPaisa}
                    onChange={(e) => setFormPaisa(parseInt(e.target.value) || 25000)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-md"
                >
                  {isLoading ? "Saving..." : "Create Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AutopilotDashboard;
