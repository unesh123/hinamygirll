import React, { useState } from "react";
import { motion } from "framer-motion";
import { Zap, Play, CheckCircle2, Clock, Check } from "lucide-react";
import type { PlanFields, PlanStep } from "../types";

interface PlanCardProps {
  data: PlanFields;
  onCommit?: (updated: PlanFields) => void;
  compact?: boolean;
}

export function PlanCard({ data, onCommit, compact = false }: PlanCardProps) {
  const [steps, setSteps] = useState<PlanStep[]>(data.steps);
  const [isRunning, setIsRunning] = useState(false);

  const runAllSteps = () => {
    setIsRunning(true);
    steps.forEach((step, idx) => {
      setTimeout(() => {
        setSteps((prev) =>
          prev.map((s, i) =>
            i === idx
              ? { ...s, status: "running" }
              : i < idx
                ? { ...s, status: "done" }
                : s
          )
        );
      }, (idx + 1) * 700);
    });

    setTimeout(() => {
      setSteps((prev) => prev.map((s) => ({ ...s, status: "done" })));
      setIsRunning(false);
    }, (steps.length + 1) * 700);
  };

  const allDone = steps.every((s) => s.status === "done");

  return (
    <div
      style={{
        padding: compact ? "12px 14px" : "16px 20px",
        borderRadius: "14px",
        background: "var(--bg-surface-raised, #18202a)",
        border: "1px solid var(--border-subtle, rgba(255,255,255,0.08))",
        boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
        color: "#ffffff",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        width: "100%",
        maxWidth: 520,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: "rgba(234, 179, 8, 0.15)",
              color: "#eab308",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Zap size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>{data.title}</span>
        </div>
        <span
          style={{
            fontSize: "0.72rem",
            padding: "2px 8px",
            borderRadius: 4,
            background: allDone ? "rgba(16, 185, 129, 0.15)" : "rgba(255,255,255,0.06)",
            color: allDone ? "#10b981" : "rgba(255,255,255,0.6)",
            fontWeight: 650,
          }}
        >
          {allDone ? "All Complete" : `${steps.length} Actions`}
        </span>
      </div>

      {/* Steps List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {steps.map((step, idx) => (
          <div
            key={step.id}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 12px",
              borderRadius: 8,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.05)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  background:
                    step.status === "done"
                      ? "#10b981"
                      : step.status === "running"
                        ? "#eab308"
                        : "rgba(255,255,255,0.1)",
                  color: step.status === "done" || step.status === "running" ? "#000000" : "#ffffff",
                  fontSize: "0.68rem",
                  fontWeight: 800,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {step.status === "done" ? <Check size={12} strokeWidth={3} /> : idx + 1}
              </span>
              <span
                style={{
                  fontSize: "0.82rem",
                  color: step.status === "done" ? "rgba(255,255,255,0.5)" : "#ffffff",
                  textDecoration: step.status === "done" ? "line-through" : "none",
                }}
              >
                {step.title}
              </span>
            </div>

            <span style={{ fontSize: "0.72rem", color: "rgba(255,255,255,0.4)" }}>
              {step.status === "done"
                ? "Done"
                : step.status === "running"
                  ? "Running…"
                  : "Queued"}
            </span>
          </div>
        ))}
      </div>

      {/* Action Button */}
      {!allDone && (
        <button
          type="button"
          disabled={isRunning}
          onClick={runAllSteps}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "9px 14px",
            borderRadius: 8,
            background: "#eab308",
            color: "#000000",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: isRunning ? "wait" : "pointer",
            marginTop: 4,
          }}
        >
          <Play size={14} fill="#000" />
          <span>{isRunning ? "Executing Plan…" : "Run All Actions ↵"}</span>
        </button>
      )}

      {allDone && onCommit && (
        <button
          type="button"
          onClick={() => onCommit({ ...data, steps, allCompleted: true })}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "9px 14px",
            borderRadius: 8,
            background: "#10b981",
            color: "#000000",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Save Completed Plan ↵</span>
        </button>
      )}
    </div>
  );
}
