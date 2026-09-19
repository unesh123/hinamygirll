import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Globe,
  FolderOpen,
  Monitor,
  Terminal,
  Mail,
  Image,
  FileText,
  Shield,
  Settings,
  RefreshCw,
  Play,
  Pause,
  XCircle,
  CheckCircle2,
  AlertCircle,
  Clock,
  ChevronRight,
  GitBranch,
  Code,
  Sparkles,
  Search,
  Sliders,
  Send,
  Activity,
  Layers,
  CheckCircle,
  Download,
  Calendar,
} from "lucide-react";
import { ApprovalCard, type ApprovalRiskLevel } from "../components/approval/ApprovalCard";

/* ── Types ───────────────────────────────────────────── */
export interface RuntimeTaskStep {
  id: string;
  stepId: string;
  taskId: string;
  position: number;
  title: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  attemptCount?: number;
  maxAttempts?: number;
  failureReason?: string;
  startedAt?: string | null;
  completedAt?: string | null;
}

export interface RuntimeTaskCheckpoint {
  checkpointReason?: string;
  status?: string;
  completedSteps?: string[];
  remainingSteps?: string[];
  knownFailures?: Array<{ stepId: string; reason: string }>;
  runtimeVersion?: string;
}

export interface RuntimeTask {
  id: string;
  taskId: string;
  goal: string;
  taskType: string;
  status: "pending" | "running" | "waiting_user" | "paused" | "completed" | "failed" | "cancelled";
  priority?: number;
  reasoningMode?: string;
  currentStepId?: string | null;
  failureCount?: number;
  checkpointVersion?: number;
  checkpoint?: RuntimeTaskCheckpoint;
  metadata?: {
    toolName?: string;
    parameters?: Record<string, any>;
    [key: string]: any;
  };
  steps?: RuntimeTaskStep[];
  createdAt?: string;
  updatedAt?: string;
  completedAt?: string | null;
}

export interface RuntimeToolCapability {
  name: string;
  displayName: string;
  description: string;
  riskLevel: "low" | "medium" | "high";
  requiresConfirmation: boolean;
  permissionLevel: string;
  cancellable: boolean;
  parameters?: Record<string, any>;
  requiredParameters?: string[];
  category?: "web" | "media" | "document" | "github" | "system";
}

/* ── Fallback Tool Categorization ────────────────────── */
function categorizeTool(name: string): "web" | "media" | "document" | "github" | "system" {
  if (name.startsWith("github_")) return "github";
  if (name.includes("image") || name.includes("upscale") || name.includes("relight") || name.includes("video")) return "media";
  if (name.includes("pdf") || name.includes("document") || name.includes("gamma")) return "document";
  if (name.includes("web") || name.includes("search") || name.includes("research") || name.includes("browse") || name.includes("tinyfish")) return "web";
  return "system";
}

function getCategoryIcon(category: string) {
  switch (category) {
    case "web": return <Globe size={15} />;
    case "media": return <Image size={15} />;
    case "document": return <FileText size={15} />;
    case "github": return <GitBranch size={15} />;
    case "system": default: return <Terminal size={15} />;
  }
}

/* ── Main Component ─────────────────────────────────── */
export type OperateTab = "tasks" | "capabilities" | "approvals" | "reports";

interface GeneratedDocSummary {
  docId: string;
  title: string;
  filename?: string | null;
  format?: string;
  pageCount?: number | null;
  fileSizeKb?: number | null;
  topic?: string | null;
  downloadUrl: string;
  createdAt: string;
}

export function OperateMode({ initialTab = "tasks" }: { initialTab?: OperateTab } = {}) {
  const [activeTab, setActiveTab] = useState<OperateTab>(initialTab);
  const [tasks, setTasks] = useState<RuntimeTask[]>([]);
  const [tools, setTools] = useState<RuntimeToolCapability[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedToolName, setSelectedToolName] = useState<string | null>(null);
  const [taskEvents, setTaskEvents] = useState<any[]>([]);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [steerInput, setSteerInput] = useState("");
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [taskFilter, setTaskFilter] = useState<"all" | "active" | "waiting" | "terminal">("all");
  const [toolCategoryFilter, setToolCategoryFilter] = useState<string>("all");

  const [isMobile, setIsMobile] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth <= 768;
    }
    return false;
  });

  const [docs, setDocs] = useState<GeneratedDocSummary[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);

  const loadDocs = useCallback(async () => {
    try {
      setIsLoadingDocs(true);
      const res = await fetch("/api/v1/generated-docs", {
        headers: { "X-HINAA-Dev-User": "local-web-user" },
      });
      if (res.ok) {
        const data = await res.json();
        setDocs(Array.isArray(data.documents) ? data.documents : []);
      }
    } catch {
      // Reports are non-critical; keep previous state on failure
    } finally {
      setIsLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "reports") void loadDocs();
  }, [activeTab, loadDocs]);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const showNotice = (msg: string) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 4000);
  };

  /* ── Fetch Tasks ───────────────────────────────────── */
  const fetchTasks = useCallback(async () => {
    setIsLoadingTasks(true);
    try {
      const res = await fetch("/v1/tasks?include_completed=true&limit=100");
      if (res.ok) {
        const data = await res.json();
        setTasks(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.warn("Failed to fetch runtime tasks", err);
    } finally {
      setIsLoadingTasks(false);
    }
  }, []);

  /* ── Fetch Tools ───────────────────────────────────── */
  const fetchTools = useCallback(async () => {
    setIsLoadingTools(true);
    try {
      const res = await fetch("/v1/tools");
      if (res.ok) {
        const data = await res.json();
        const mapped: RuntimeToolCapability[] = (Array.isArray(data) ? data : []).map((t: any) => ({
          ...t,
          category: categorizeTool(t.name),
        }));
        setTools(mapped);
      }
    } catch (err) {
      console.warn("Failed to fetch tools registry", err);
    } finally {
      setIsLoadingTools(false);
    }
  }, []);

  /* ── Fetch Task Events ─────────────────────────────── */
  const fetchTaskEvents = useCallback(async (taskId: string) => {
    try {
      const res = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/events`);
      if (res.ok) {
        const data = await res.json();
        setTaskEvents(data.events || []);
      }
    } catch (err) {
      console.warn(`Failed to fetch events for task ${taskId}`, err);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
    fetchTools();
    const interval = setInterval(fetchTasks, 6000);
    return () => clearInterval(interval);
  }, [fetchTasks, fetchTools]);

  useEffect(() => {
    if (selectedTaskId) {
      fetchTaskEvents(selectedTaskId);
    } else {
      setTaskEvents([]);
    }
  }, [selectedTaskId, fetchTaskEvents]);

  /* ── Task Actions ──────────────────────────────────── */
  const handlePauseTask = async (taskId: string) => {
    try {
      const res = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/pause`, { method: "POST" });
      if (res.ok) {
        showNotice(`Task ${taskId.slice(0, 8)} paused`);
        fetchTasks();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleResumeTask = async (taskId: string) => {
    try {
      const res = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/resume`, { method: "POST" });
      if (res.ok) {
        showNotice(`Task ${taskId.slice(0, 8)} resumed`);
        fetchTasks();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancelTask = async (taskId: string) => {
    try {
      const res = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/cancel`, { method: "POST" });
      if (res.ok) {
        showNotice(`Task ${taskId.slice(0, 8)} cancelled`);
        fetchTasks();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSteerTask = async (taskId: string) => {
    if (!steerInput.trim()) return;
    try {
      const res = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/steer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction: steerInput.trim() }),
      });
      if (res.ok) {
        showNotice(`Instruction sent to task ${taskId.slice(0, 8)}`);
        setSteerInput("");
        fetchTasks();
        fetchTaskEvents(taskId);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleApproveWaitingTask = async (taskId: string) => {
    try {
      const res = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/continue`, { method: "POST" });
      if (res.ok) {
        showNotice(`Task approved and resumed execution`);
        fetchTasks();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const waitingTasks = tasks.filter((t) => t.status === "waiting_user");
  const filteredTasks = tasks.filter((t) => {
    if (taskFilter === "active") return t.status === "running" || t.status === "pending";
    if (taskFilter === "waiting") return t.status === "waiting_user";
    if (taskFilter === "terminal") return t.status === "completed" || t.status === "failed" || t.status === "cancelled";
    return true;
  });

  const filteredTools = tools.filter((t) => {
    if (toolCategoryFilter === "all") return true;
    return t.category === toolCategoryFilter;
  });

  const selectedTask = tasks.find((t) => t.id === selectedTaskId || t.taskId === selectedTaskId);
  const selectedTool = tools.find((t) => t.name === selectedToolName);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100%",
      overflow: "hidden",
      background: "var(--bg-canvas, #09090b)",
      color: "var(--text-primary, #f4f4f5)",
      fontFamily: "var(--font-sans, system-ui, sans-serif)",
    }}>
      {/* ── Top Header ────────────────────────────────────────── */}
      <header style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: isMobile ? "0 10px" : "0 16px",
        borderBottom: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
        background: "var(--bg-surface, #121215)",
        flexShrink: 0,
        minHeight: 52,
        height: isMobile ? "auto" : 52,
        flexWrap: isMobile ? "wrap" : "nowrap",
        gap: isMobile ? 6 : 12,
        paddingTop: isMobile ? 8 : 0,
        paddingBottom: isMobile ? 8 : 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 28,
            height: 28,
            borderRadius: 8,
            background: "linear-gradient(135deg, #ec4899, #8b5cf6)",
            color: "#fff",
            flexShrink: 0,
          }}>
            <Shield size={15} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: "14px", fontWeight: 700, letterSpacing: "-0.01em" }}>
                Operate
              </span>
              <span style={{
                fontSize: "10px",
                padding: "1px 6px",
                borderRadius: "999px",
                background: "rgba(236,72,153,0.15)",
                color: "#f472b6",
                fontWeight: 600,
                border: "1px solid rgba(236,72,153,0.3)",
                whiteSpace: "nowrap",
              }}>
                SUPERVISED
              </span>
            </div>
            {!isMobile && (
              <div style={{ fontSize: "11px", color: "var(--text-tertiary, #a1a1aa)" }}>
                Durable execution, action gates & tool orchestration
              </div>
            )}
          </div>
        </div>

        {/* Tab Controls & Refresh */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, overflowX: isMobile ? "auto" : "visible", maxWidth: "100%" }}>
          <div style={{
            display: "flex",
            padding: 2,
            background: "var(--bg-surface-raised, rgba(255,255,255,0.05))",
            borderRadius: 8,
            border: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
          }}>
            <button
              onClick={() => setActiveTab("tasks")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: "12px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "tasks" ? "var(--bg-surface-active, rgba(255,255,255,0.15))" : "transparent",
                color: activeTab === "tasks" ? "#fff" : "var(--text-secondary, #a1a1aa)",
                transition: "all 150ms ease",
              }}
            >
              <Activity size={13} />
              Durable Tasks
              <span style={{
                fontSize: "10px",
                padding: "0 5px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.1)",
              }}>
                {tasks.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab("approvals")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: "12px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "approvals" ? "rgba(236,72,153,0.2)" : "transparent",
                color: activeTab === "approvals" ? "#f472b6" : "var(--text-secondary, #a1a1aa)",
                transition: "all 150ms ease",
              }}
            >
              <Shield size={13} />
              Approvals Queue
              {waitingTasks.length > 0 && (
                <span style={{
                  fontSize: "10px",
                  padding: "0 6px",
                  borderRadius: 999,
                  background: "#ec4899",
                  color: "#fff",
                  fontWeight: 700,
                }}>
                  {waitingTasks.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("reports")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: "12px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "reports" ? "var(--bg-surface-active, rgba(255,255,255,0.15))" : "transparent",
                color: activeTab === "reports" ? "#fff" : "var(--text-secondary, #a1a1aa)",
                transition: "all 150ms ease",
              }}
            >
              <FileText size={13} />
              Reports
              {docs.length > 0 && (
                <span style={{
                  fontSize: "10px",
                  padding: "0 5px",
                  borderRadius: 999,
                  background: "rgba(255,255,255,0.1)",
                }}>
                  {docs.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab("capabilities")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: "12px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "capabilities" ? "var(--bg-surface-active, rgba(255,255,255,0.15))" : "transparent",
                color: activeTab === "capabilities" ? "#fff" : "var(--text-secondary, #a1a1aa)",
                transition: "all 150ms ease",
              }}
            >
              <Layers size={13} />
              Capability Registry
              <span style={{
                fontSize: "10px",
                padding: "0 5px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.1)",
              }}>
                {tools.length}
              </span>
            </button>
          </div>

          <button
            onClick={() => {
              fetchTasks();
              fetchTools();
              if (selectedTaskId) fetchTaskEvents(selectedTaskId);
            }}
            disabled={isLoadingTasks || isLoadingTools}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              padding: "6px 10px",
              borderRadius: 6,
              background: "transparent",
              border: "1px solid var(--border-subtle, rgba(255,255,255,0.1))",
              color: "var(--text-secondary, #a1a1aa)",
              fontSize: "12px",
              cursor: "pointer",
            }}
            title="Refresh runtime state"
          >
            <RefreshCw size={13} className={isLoadingTasks || isLoadingTools ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </header>

      {/* Action Notification Toast */}
      {actionNotice && (
        <div style={{
          padding: "8px 16px",
          background: "linear-gradient(90deg, #ec4899, #8b5cf6)",
          color: "#fff",
          fontSize: "12px",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          gap: 8,
          boxShadow: "0 2px 10px rgba(0,0,0,0.3)",
        }}>
          <CheckCircle size={14} />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* ── Main Workspace Body ───────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* ── Tab: Approvals Queue ───────────────────────────── */}
        {activeTab === "approvals" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <h2 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>Pending Supervised Actions</h2>
                <p style={{ fontSize: "12px", color: "var(--text-tertiary, #a1a1aa)", margin: "4px 0 0" }}>
                  All high-impact, file-system mutating, and external platform calls require explicit user authorization.
                </p>
              </div>
              <span style={{ fontSize: "12px", color: "var(--text-secondary, #a1a1aa)" }}>
                {waitingTasks.length} pending
              </span>
            </div>

            {waitingTasks.length === 0 ? (
              <div style={{
                padding: "64px 16px",
                textAlign: "center",
                borderRadius: 12,
                border: "1px dashed var(--border-subtle, rgba(255,255,255,0.1))",
                background: "var(--bg-surface, #121215)",
              }}>
                <CheckCircle2 size={40} color="#22c55e" style={{ margin: "0 auto 12px", opacity: 0.8 }} />
                <h3 style={{ fontSize: "14px", fontWeight: 600, margin: 0 }}>All clearances granted</h3>
                <p style={{ fontSize: "12px", color: "var(--text-tertiary, #a1a1aa)", marginTop: 6 }}>
                  No tasks or tool executions are currently blocked waiting for approval.
                </p>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 16 }}>
                {waitingTasks.map((t) => {
                  const failure = t.checkpoint?.knownFailures?.[0]?.reason || "";
                  const toolName = t.metadata?.toolName || t.taskType;
                  return (
                    <div key={t.id} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      <ApprovalCard
                        id={t.id}
                        action={t.goal || `Execute ${toolName}`}
                        target={toolName}
                        riskLevel="high"
                        reason={failure || `Task requires user clearance to continue execution past step ${t.currentStepId?.slice(0, 8) || 1}.`}
                        onApprove={() => handleApproveWaitingTask(t.id)}
                        onReject={() => handleCancelTask(t.id)}
                      />
                      <div style={{
                        padding: "8px 12px",
                        background: "rgba(255,255,255,0.03)",
                        borderRadius: 6,
                        border: "1px solid rgba(255,255,255,0.06)",
                        fontSize: "11px",
                        color: "var(--text-tertiary, #a1a1aa)",
                        display: "flex",
                        justifyContent: "space-between",
                      }}>
                        <span>Task ID: {t.id.slice(0, 16)}</span>
                        <span>Created: {t.createdAt ? new Date(t.createdAt).toLocaleTimeString() : "Recent"}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── Tab: Durable Tasks ─────────────────────────────── */}
        {activeTab === "tasks" && (
          <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
            {/* Task list pane */}
            {(!isMobile || !selectedTaskId) && (
              <div style={{
                flex: 1,
                overflowY: "auto",
                padding: isMobile ? 12 : 16,
                display: "flex",
                flexDirection: "column",
                gap: 12,
                borderRight: !isMobile ? "1px solid var(--border-subtle, rgba(255,255,255,0.08))" : "none",
              }}>
              {/* Task filters */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <div style={{ display: "flex", gap: 4 }}>
                  {(["all", "active", "waiting", "terminal"] as const).map((filter) => (
                    <button
                      key={filter}
                      onClick={() => setTaskFilter(filter)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "capitalize",
                        border: "none",
                        cursor: "pointer",
                        background: taskFilter === filter ? "var(--accent, #ec4899)" : "rgba(255,255,255,0.06)",
                        color: taskFilter === filter ? "#fff" : "var(--text-secondary, #a1a1aa)",
                      }}
                    >
                      {filter}
                    </button>
                  ))}
                </div>
                <span style={{ fontSize: "11px", color: "var(--text-tertiary, #71717a)" }}>
                  Showing {filteredTasks.length} of {tasks.length}
                </span>
              </div>

              {filteredTasks.length === 0 ? (
                <div style={{
                  padding: "48px 16px",
                  textAlign: "center",
                  color: "var(--text-tertiary, #a1a1aa)",
                  fontSize: "13px",
                }}>
                  <Activity size={32} style={{ margin: "0 auto 8px", opacity: 0.3 }} />
                  <p>No durable tasks found matching filter.</p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {filteredTasks.map((task) => {
                    const isSelected = selectedTaskId === task.id || selectedTaskId === task.taskId;
                    return (
                      <motion.div
                        key={task.id}
                        whileHover={{ scale: 1.005 }}
                        onClick={() => setSelectedTaskId(task.id)}
                        style={{
                          padding: "12px 14px",
                          borderRadius: 8,
                          background: isSelected ? "rgba(236,72,153,0.1)" : "var(--bg-surface, #121215)",
                          border: `1px solid ${isSelected ? "var(--accent, #ec4899)" : "var(--border-subtle, rgba(255,255,255,0.08))"}`,
                          cursor: "pointer",
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                          transition: "all 120ms ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <TaskStatusBadge status={task.status} />
                            <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                              {task.goal || `Task ${task.id.slice(0, 8)}`}
                            </span>
                          </div>
                          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #71717a)" }}>
                            {task.createdAt ? new Date(task.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ""}
                          </span>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 2 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "11px", color: "var(--text-secondary, #a1a1aa)" }}>
                            <span>Type: {task.taskType}</span>
                            {task.steps && (
                              <span>Steps: {task.steps.filter((s) => s.status === "completed").length}/{task.steps.length}</span>
                            )}
                            {task.checkpointVersion !== undefined && (
                              <span>CP: v{task.checkpointVersion}</span>
                            )}
                          </div>
                          <ChevronRight size={14} color={isSelected ? "var(--accent, #ec4899)" : "#71717a"} />
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>
            )}

            {/* Task Detail & Steer Pane */}
            {(!isMobile || selectedTaskId) && (
            <div style={{
              width: isMobile ? "100%" : 440,
              flex: isMobile ? 1 : undefined,
              flexShrink: isMobile ? 1 : 0,
              background: "var(--bg-surface, #121215)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}>
              {isMobile && selectedTaskId && (
                <button
                  onClick={() => setSelectedTaskId(null)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "10px 16px",
                    background: "rgba(255,255,255,0.05)",
                    border: "none",
                    borderBottom: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
                    color: "var(--accent, #ec4899)",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: "pointer",
                    width: "100%",
                    textAlign: "left",
                  }}
                >
                  ← Back to task list
                </button>
              )}
              {selectedTask ? (
                <div style={{ display: "flex", flexDirection: "column", height: "100%", overflowY: "auto", padding: 16, gap: 16 }}>
                  {/* Task Header */}
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <TaskStatusBadge status={selectedTask.status} />
                      <span style={{ fontSize: "11px", color: "var(--text-tertiary, #71717a)" }}>
                        ID: {selectedTask.id}
                      </span>
                    </div>
                    <h3 style={{ fontSize: "15px", fontWeight: 700, margin: "8px 0 4px" }}>
                      {selectedTask.goal}
                    </h3>
                    <p style={{ fontSize: "11px", color: "var(--text-secondary, #a1a1aa)", margin: 0 }}>
                      Reasoning: {selectedTask.reasoningMode || "balanced"} · Priority: {selectedTask.priority ?? 0}
                    </p>
                  </div>

                  {/* Task Controls */}
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}>
                    {selectedTask.status === "paused" ? (
                      <button
                        onClick={() => handleResumeTask(selectedTask.id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "6px 12px",
                          borderRadius: 6,
                          background: "#22c55e",
                          color: "#fff",
                          fontWeight: 600,
                          fontSize: "11px",
                          border: "none",
                          cursor: "pointer",
                        }}
                      >
                        <Play size={12} /> Resume
                      </button>
                    ) : selectedTask.status === "running" || selectedTask.status === "pending" ? (
                      <button
                        onClick={() => handlePauseTask(selectedTask.id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "6px 12px",
                          borderRadius: 6,
                          background: "#f59e0b",
                          color: "#fff",
                          fontWeight: 600,
                          fontSize: "11px",
                          border: "none",
                          cursor: "pointer",
                        }}
                      >
                        <Pause size={12} /> Pause
                      </button>
                    ) : null}

                    {selectedTask.status === "waiting_user" && (
                      <button
                        onClick={() => handleApproveWaitingTask(selectedTask.id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "6px 12px",
                          borderRadius: 6,
                          background: "#ec4899",
                          color: "#fff",
                          fontWeight: 600,
                          fontSize: "11px",
                          border: "none",
                          cursor: "pointer",
                        }}
                      >
                        <CheckCircle size={12} /> Approve & Continue
                      </button>
                    )}

                    {selectedTask.status !== "completed" && selectedTask.status !== "cancelled" && selectedTask.status !== "failed" && (
                      <button
                        onClick={() => handleCancelTask(selectedTask.id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "6px 12px",
                          borderRadius: 6,
                          background: "rgba(239,68,68,0.15)",
                          color: "#ef4444",
                          border: "1px solid rgba(239,68,68,0.3)",
                          fontWeight: 600,
                          fontSize: "11px",
                          cursor: "pointer",
                        }}
                      >
                        <XCircle size={12} /> Cancel Task
                      </button>
                    )}
                  </div>

                  {/* Steering Input */}
                  {selectedTask.status !== "completed" && selectedTask.status !== "cancelled" && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-secondary, #a1a1aa)" }}>
                        Steer Task Execution
                      </span>
                      <div style={{ display: "flex", gap: 6 }}>
                        <input
                          type="text"
                          value={steerInput}
                          onChange={(e) => setSteerInput(e.target.value)}
                          placeholder="Inject instruction into runtime..."
                          onKeyDown={(e) => e.key === "Enter" && handleSteerTask(selectedTask.id)}
                          style={{
                            flex: 1,
                            padding: "7px 10px",
                            borderRadius: 6,
                            background: "rgba(0,0,0,0.3)",
                            border: "1px solid rgba(255,255,255,0.1)",
                            color: "#fff",
                            fontSize: "12px",
                            outline: "none",
                          }}
                        />
                        <button
                          onClick={() => handleSteerTask(selectedTask.id)}
                          style={{
                            padding: "0 12px",
                            borderRadius: 6,
                            background: "var(--accent, #ec4899)",
                            color: "#fff",
                            border: "none",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                          }}
                        >
                          <Send size={13} />
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Steps Checklist */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-tertiary, #71717a)" }}>
                      Step Execution Checklist ({selectedTask.steps?.length || 0})
                    </span>
                    {selectedTask.steps && selectedTask.steps.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {selectedTask.steps.map((step) => (
                          <div
                            key={step.id || step.stepId}
                            style={{
                              padding: "8px 10px",
                              borderRadius: 6,
                              background: "rgba(255,255,255,0.02)",
                              border: "1px solid rgba(255,255,255,0.06)",
                              display: "flex",
                              flexDirection: "column",
                              gap: 4,
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                {step.status === "completed" ? (
                                  <CheckCircle2 size={13} color="#22c55e" />
                                ) : step.status === "failed" ? (
                                  <AlertCircle size={13} color="#ef4444" />
                                ) : step.status === "running" ? (
                                  <RefreshCw size={13} color="#3b82f6" className="animate-spin" />
                                ) : (
                                  <Clock size={13} color="#71717a" />
                                )}
                                <span style={{ fontSize: "12px", fontWeight: 600, color: "#fff" }}>
                                  {step.position + 1}. {step.title}
                                </span>
                              </div>
                              <span style={{
                                fontSize: "10px",
                                textTransform: "uppercase",
                                color: step.status === "completed" ? "#22c55e" : step.status === "failed" ? "#ef4444" : "#a1a1aa",
                                fontWeight: 700,
                              }}>
                                {step.status}
                              </span>
                            </div>
                            {step.failureReason && (
                              <div style={{
                                fontSize: "11px",
                                color: "#fca5a5",
                                background: "rgba(239,68,68,0.1)",
                                padding: "4px 8px",
                                borderRadius: 4,
                                marginTop: 2,
                              }}>
                                {step.failureReason}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span style={{ fontSize: "12px", color: "var(--text-tertiary, #71717a)" }}>
                        No step breakdown available.
                      </span>
                    )}
                  </div>

                  {/* Task Events & Audit Trail */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-tertiary, #71717a)" }}>
                      Audit Ledger Events ({taskEvents.length})
                    </span>
                    <div style={{
                      maxHeight: 180,
                      overflowY: "auto",
                      background: "rgba(0,0,0,0.4)",
                      padding: 8,
                      borderRadius: 6,
                      fontSize: "11px",
                      fontFamily: "monospace",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}>
                      {taskEvents.length > 0 ? (
                        taskEvents.map((evt, idx) => (
                          <div key={idx} style={{ color: "#a1a1aa" }}>
                            <span style={{ color: "#f472b6" }}>[{evt.type || evt.eventType}]</span> {evt.message || JSON.stringify(evt.payload || {})}
                          </div>
                        ))
                      ) : (
                        <div style={{ color: "#71717a" }}>No event receipts logged yet.</div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{
                  padding: 32,
                  textAlign: "center",
                  color: "var(--text-tertiary, #71717a)",
                  fontSize: "12px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                }}>
                  <Layers size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
                  Select a durable task from the list to inspect checkpoints, steer execution, or view step receipts.
                </div>
              )}
            </div>
            )}
          </div>
        )}

        {/* ── Tab: Generated Reports / Documents ────────────── */}
        {activeTab === "reports" && (
          <div style={{ flex: 1, overflowY: "auto", padding: isMobile ? "16px" : "20px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-primary, #fff)" }}>
                Generated Documents
              </div>
              <button
                onClick={() => void loadDocs()}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "5px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "transparent",
                  color: "var(--text-secondary, #a1a1aa)",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                <RefreshCw size={12} />
                Refresh
              </button>
            </div>

            {isLoadingDocs && (
              <div style={{ textAlign: "center", padding: 40, color: "var(--text-tertiary, #71717a)", fontSize: "12px" }}>
                Loading documents…
              </div>
            )}

            {!isLoadingDocs && docs.length === 0 && (
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: 48,
                color: "var(--text-tertiary, #71717a)",
                fontSize: "12px",
                textAlign: "center",
                gap: 8,
              }}>
                <FileText size={30} style={{ opacity: 0.35 }} />
                No generated documents yet. Ask HINA to create a PDF, report, or document — they will appear here.
              </div>
            )}

            {!isLoadingDocs && docs.length > 0 && (
              <div style={{
                display: "grid",
                gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fill, minmax(300px, 1fr))",
                gap: 12,
              }}>
                {docs.map((doc) => (
                  <div
                    key={doc.docId}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      padding: 14,
                      borderRadius: 10,
                      border: "1px solid rgba(255,255,255,0.08)",
                      background: "var(--bg-surface, rgba(255,255,255,0.04))",
                    }}
                  >
                    <div style={{ fontSize: "12.5px", fontWeight: 650, color: "var(--text-primary, #fff)", lineHeight: 1.35 }}>
                      {doc.title}
                    </div>
                    {doc.topic && (
                      <div style={{ fontSize: "11px", color: "var(--text-tertiary, #71717a)", lineHeight: 1.4 }}>
                        {doc.topic}
                      </div>
                    )}
                    <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "10.5px", color: "var(--text-tertiary, #71717a)", flexWrap: "wrap" }}>
                      <span style={{ display: "flex", alignItems: "center", gap: 4, textTransform: "uppercase", fontWeight: 700 }}>
                        <FileText size={11} /> {doc.format ?? "pdf"}
                      </span>
                      {doc.pageCount != null && <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Layers size={11} /> {doc.pageCount}p</span>}
                      {doc.fileSizeKb != null && <span>{doc.fileSizeKb} KB</span>}
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <Calendar size={11} /> {new Date(doc.createdAt).toLocaleDateString()}
                      </span>
                    </div>
                    <a
                      href={doc.downloadUrl}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 6,
                        padding: "7px 10px",
                        borderRadius: 8,
                        background: "rgba(236,72,153,0.16)",
                        color: "#f472b6",
                        fontSize: "11px",
                        fontWeight: 650,
                        textDecoration: "none",
                      }}
                    >
                      <Download size={12} />
                      Download
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Tab: Capability Registry ───────────────────────── */}
        {activeTab === "capabilities" && (
          <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
            {(!isMobile || !selectedToolName) && (
            <div style={{ flex: 1, overflowY: "auto", padding: isMobile ? 12 : 20, display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Category filters */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", gap: 6 }}>
                  {["all", "web", "media", "document", "github", "system"].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setToolCategoryFilter(cat)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "capitalize",
                        border: "none",
                        cursor: "pointer",
                        background: toolCategoryFilter === cat ? "var(--accent, #ec4899)" : "rgba(255,255,255,0.06)",
                        color: toolCategoryFilter === cat ? "#fff" : "var(--text-secondary, #a1a1aa)",
                      }}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
                <span style={{ fontSize: "11px", color: "var(--text-tertiary, #71717a)" }}>
                  {filteredTools.length} tools registered
                </span>
              </div>

              {/* Tools Grid */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                gap: 12,
              }}>
                {filteredTools.map((tool) => {
                  const isSelected = selectedToolName === tool.name;
                  return (
                    <motion.div
                      key={tool.name}
                      whileHover={{ scale: 1.01 }}
                      onClick={() => setSelectedToolName(tool.name)}
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        background: isSelected ? "rgba(236,72,153,0.1)" : "var(--bg-surface, #121215)",
                        border: `1px solid ${isSelected ? "var(--accent, #ec4899)" : "var(--border-subtle, rgba(255,255,255,0.08))"}`,
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                        transition: "all 150ms ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ color: "var(--accent, #ec4899)" }}>
                            {getCategoryIcon(tool.category || "system")}
                          </span>
                          <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                            {tool.displayName || tool.name}
                          </span>
                        </div>
                        <span style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "1px 6px",
                          borderRadius: 999,
                          background: tool.requiresConfirmation ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
                          color: tool.requiresConfirmation ? "#f87171" : "#4ade80",
                          border: `1px solid ${tool.requiresConfirmation ? "rgba(239,68,68,0.3)" : "rgba(34,197,94,0.3)"}`,
                        }}>
                          {tool.requiresConfirmation ? "GATED" : "AUTO"}
                        </span>
                      </div>

                      <p style={{
                        fontSize: "11px",
                        color: "var(--text-secondary, #a1a1aa)",
                        margin: 0,
                        lineHeight: 1.4,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}>
                        {tool.description}
                      </p>

                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "10px", color: "var(--text-tertiary, #71717a)" }}>
                        <span>Risk: {tool.riskLevel || "medium"}</span>
                        <span>{tool.parameters ? `${Object.keys(tool.parameters).length} params` : "No params"}</span>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </div>
            )}

            {/* Selected Tool Details Pane */}
            {selectedTool && (!isMobile || selectedToolName) && (
              <div style={{
                width: isMobile ? "100%" : 320,
                flex: isMobile ? 1 : undefined,
                flexShrink: isMobile ? 1 : 0,
                borderLeft: !isMobile ? "1px solid var(--border-subtle, rgba(255,255,255,0.08))" : "none",
                background: "var(--bg-surface, #121215)",
                padding: 16,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 16,
              }}>
                {isMobile && (
                  <button
                    onClick={() => setSelectedToolName(null)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "4px 0 10px 0",
                      background: "none",
                      border: "none",
                      color: "var(--accent, #ec4899)",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    ← Back to capability registry
                  </button>
                )}
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ color: "var(--accent, #ec4899)" }}>
                      {getCategoryIcon(selectedTool.category || "system")}
                    </span>
                    <h3 style={{ fontSize: "14px", fontWeight: 700, margin: 0 }}>
                      {selectedTool.displayName}
                    </h3>
                  </div>
                  <span style={{ fontSize: "11px", fontFamily: "monospace", color: "var(--text-tertiary, #71717a)" }}>
                    tool: {selectedTool.name}
                  </span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: "12px" }}>
                  <DetailRow label="Category" value={selectedTool.category || "system"} />
                  <DetailRow label="Risk Rating" value={selectedTool.riskLevel} />
                  <DetailRow label="User Approval" value={selectedTool.requiresConfirmation ? "Required" : "Standing Consent"} />
                  <DetailRow label="Permission Level" value={selectedTool.permissionLevel} />
                  <DetailRow label="Cancellable" value={selectedTool.cancellable ? "Yes" : "No"} />
                </div>

                <div>
                  <h4 style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--text-tertiary, #71717a)", marginBottom: 6 }}>
                    Description
                  </h4>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary, #a1a1aa)", lineHeight: 1.5, margin: 0 }}>
                    {selectedTool.description}
                  </p>
                </div>

                {selectedTool.parameters && Object.keys(selectedTool.parameters).length > 0 && (
                  <div>
                    <h4 style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--text-tertiary, #71717a)", marginBottom: 6 }}>
                      Parameters Schema
                    </h4>
                    <div style={{
                      background: "rgba(0,0,0,0.3)",
                      padding: 8,
                      borderRadius: 6,
                      fontSize: "11px",
                      fontFamily: "monospace",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}>
                      {Object.entries(selectedTool.parameters).map(([paramName, schema]: [string, any]) => {
                        const isRequired = selectedTool.requiredParameters?.includes(paramName);
                        return (
                          <div key={paramName}>
                            <span style={{ color: "#f472b6", fontWeight: isRequired ? "bold" : "normal" }}>
                              {paramName}{isRequired ? "*" : ""}
                            </span>
                            <span style={{ color: "#71717a" }}>: {schema.type || "any"}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Helper Components ───────────────────────────────── */
function TaskStatusBadge({ status }: { status: string }) {
  const configs: Record<string, { bg: string; color: string; label: string }> = {
    running: { bg: "rgba(59,130,246,0.15)", color: "#60a5fa", label: "Running" },
    waiting_user: { bg: "rgba(236,72,153,0.15)", color: "#f472b6", label: "Needs Approval" },
    paused: { bg: "rgba(245,158,11,0.15)", color: "#fbbf24", label: "Paused" },
    completed: { bg: "rgba(34,197,94,0.15)", color: "#4ade80", label: "Completed" },
    failed: { bg: "rgba(239,68,68,0.15)", color: "#f87171", label: "Failed" },
    cancelled: { bg: "rgba(113,113,122,0.15)", color: "#a1a1aa", label: "Cancelled" },
    pending: { bg: "rgba(168,85,247,0.15)", color: "#c084fc", label: "Queued" },
  };

  const c = configs[status] || { bg: "rgba(255,255,255,0.08)", color: "#fff", label: status };

  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 4,
      padding: "2px 8px",
      borderRadius: 999,
      fontSize: "10px",
      fontWeight: 700,
      background: c.bg,
      color: c.color,
      textTransform: "uppercase",
      letterSpacing: "0.02em",
    }}>
      <span style={{ width: 4, height: 4, borderRadius: "50%", background: c.color }} />
      {c.label}
    </span>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: "11px", color: "var(--text-tertiary, #71717a)" }}>{label}</span>
      <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-primary, #fff)", textTransform: "capitalize" }}>
        {value}
      </span>
    </div>
  );
}
