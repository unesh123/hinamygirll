import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Circle,
  FileCheck2,
  Loader2,
  Search,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";

export type StepStatus = "pending" | "active" | "done" | "error" | "cancelled";
export type WorkflowMode = "research" | "execution";

export interface AgentStep {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

interface ActivityPanelProps {
  steps: AgentStep[];
  title?: string;
  mode?: WorkflowMode;
  collapsed?: boolean;
}

const STEP_ICONS = [Sparkles, Search, ShieldCheck, FileCheck2];

function statusTone(status: StepStatus): { color: string; label: string; background: string } {
  switch (status) {
    case "done": return { color: "#34d399", label: "Complete", background: "rgba(16,185,129,.10)" };
    case "active": return { color: "#7dd3fc", label: "In progress", background: "rgba(14,165,233,.12)" };
    case "error": return { color: "#fda4af", label: "Needs attention", background: "rgba(244,63,94,.10)" };
    case "cancelled": return { color: "#94a3b8", label: "Stopped", background: "rgba(148,163,184,.10)" };
    default: return { color: "#a5b4fc", label: "Queued", background: "rgba(129,140,248,.10)" };
  }
}

export function ActivityPanel({
  steps,
  title = "Execution workflow",
  mode = "execution",
  collapsed: initialCollapsed = false,
}: ActivityPanelProps) {
  const [collapsed, setCollapsed] = useState(initialCollapsed);
  const completed = steps.filter((step) => step.status === "done").length;
  const active = steps.find((step) => step.status === "active");
  const progress = steps.length ? Math.round((completed / steps.length) * 100) : 0;

  if (!steps.length) return null;

  return (
    <motion.section
      aria-label={title}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      style={{
        margin: "0 0 14px",
        border: "1px solid rgba(125,211,252,.20)",
        background: "linear-gradient(135deg, rgba(15,23,42,.94), rgba(15,23,42,.74))",
        borderRadius: 14,
        overflow: "hidden",
        boxShadow: "0 12px 32px rgba(2,6,23,.14)",
      }}
    >
      <button
        type="button"
        onClick={() => setCollapsed((value) => !value)}
        aria-expanded={!collapsed}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "12px 14px",
          border: 0,
          color: "#e2e8f0",
          background: "transparent",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span style={{ display: "flex", minWidth: 0, alignItems: "center", gap: 10 }}>
          <span style={{ display: "grid", placeItems: "center", width: 28, height: 28, borderRadius: 9, color: "#a5f3fc", background: "rgba(14,165,233,.13)" }}>
            {mode === "research" ? <Search size={15} /> : <Sparkles size={15} />}
          </span>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: "block", fontSize: 13, fontWeight: 750, letterSpacing: ".01em" }}>{title}</span>
            <span style={{ display: "block", marginTop: 2, overflow: "hidden", color: "#94a3b8", fontSize: 11, textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {active ? `${active.label} · ${active.detail || "Hinaa is working locally"}` : `${completed}/${steps.length} stages complete`}
            </span>
          </span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 8, color: "#94a3b8" }}>
          <span style={{ padding: "3px 7px", border: "1px solid rgba(125,211,252,.18)", borderRadius: 999, color: active ? "#7dd3fc" : "#94a3b8", fontSize: 10, fontWeight: 800, letterSpacing: ".08em" }}>
            {active ? "LIVE" : "READY"}
          </span>
          {collapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            style={{ overflow: "hidden" }}
          >
            <div style={{ height: 2, margin: "0 14px", borderRadius: 999, background: "rgba(148,163,184,.16)", overflow: "hidden" }}>
              <motion.div
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.38, ease: "easeOut" }}
                style={{ height: "100%", borderRadius: 999, background: "linear-gradient(90deg,#2dd4bf,#38bdf8)" }}
              />
            </div>
            <div style={{ display: "grid", gap: 2, padding: "10px 14px 13px" }}>
              {steps.map((step, index) => {
                const Icon = STEP_ICONS[index % STEP_ICONS.length];
                const tone = statusTone(step.status);
                const isLast = index === steps.length - 1;
                return (
                  <motion.div
                    key={step.id}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.04, duration: 0.18 }}
                    style={{ display: "flex", minHeight: 42, gap: 10, position: "relative" }}
                  >
                    {!isLast && <span style={{ position: "absolute", left: 13, top: 28, bottom: -3, width: 1, background: step.status === "done" ? "rgba(45,212,191,.55)" : "rgba(148,163,184,.22)" }} />}
                    <span style={{ position: "relative", zIndex: 1, display: "grid", flex: "0 0 auto", placeItems: "center", width: 27, height: 27, border: `1px solid ${tone.color}55`, borderRadius: 9, color: tone.color, background: tone.background }}>
                      {step.status === "done" ? <CheckCircle2 size={14} /> : step.status === "active" ? <motion.span animate={{ opacity: [0.55, 1, 0.55] }} transition={{ duration: 1.3, repeat: Infinity }}><Loader2 size={14} /></motion.span> : step.status === "error" ? <XCircle size={14} /> : <Icon size={14} />}
                    </span>
                    <span style={{ display: "flex", minWidth: 0, flex: 1, alignItems: "flex-start", justifyContent: "space-between", gap: 10, paddingTop: 3 }}>
                      <span style={{ minWidth: 0 }}>
                        <strong style={{ display: "block", color: step.status === "pending" ? "#cbd5e1" : "#f8fafc", fontSize: 12, fontWeight: step.status === "active" ? 750 : 650 }}>{step.label}</strong>
                        {step.detail && <span style={{ display: "block", marginTop: 2, color: "#94a3b8", fontSize: 11, lineHeight: 1.35 }}>{step.detail}</span>}
                      </span>
                      <span style={{ flexShrink: 0, paddingTop: 1, color: tone.color, fontSize: 10, fontWeight: 700 }}>{tone.label}</span>
                    </span>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
}

export default ActivityPanel;
