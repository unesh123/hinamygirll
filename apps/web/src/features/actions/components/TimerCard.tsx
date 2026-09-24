import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Timer, Play, Pause, RotateCcw, Check } from "lucide-react";
import type { TimerFields } from "../types";

interface TimerCardProps {
  data: TimerFields;
  onCommit?: (updated: TimerFields) => void;
  compact?: boolean;
}

export function TimerCard({ data, onCommit, compact = false }: TimerCardProps) {
  const [seconds, setSeconds] = useState(data.remainingSeconds || data.durationSeconds);
  const [isRunning, setIsRunning] = useState(data.isRunning || false);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isRunning && seconds > 0) {
      interval = setInterval(() => {
        setSeconds((prev) => Math.max(0, prev - 1));
      }, 1000);
    } else if (seconds === 0 && isRunning) {
      setIsRunning(false);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRunning, seconds]);

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const timeFormatted = `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  const progressPercent = ((data.durationSeconds - seconds) / Math.max(1, data.durationSeconds)) * 100;

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
              background: "rgba(235, 111, 146, 0.15)",
              color: "#eb6f92",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Timer size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>{data.label || "Timer"}</span>
        </div>
        <span style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.5)" }}>
          {Math.round(data.durationSeconds / 60)} min total
        </span>
      </div>

      {/* Timer Display */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "2.2rem",
              fontWeight: 800,
              color: isRunning ? "#eb6f92" : seconds === 0 ? "#10b981" : "#ffffff",
              letterSpacing: "0.05em",
              lineHeight: 1,
            }}
          >
            {timeFormatted}
          </div>
          <div style={{ fontSize: "0.72rem", color: "rgba(255,255,255,0.4)", marginTop: 4 }}>
            {seconds === 0 ? "Complete!" : isRunning ? "Counting down..." : "Paused"}
          </div>
        </div>

        {/* Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            type="button"
            onClick={() => setIsRunning(!isRunning)}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              background: isRunning ? "rgba(239, 68, 68, 0.2)" : "#eb6f92",
              color: isRunning ? "#ef4444" : "#ffffff",
              border: isRunning ? "1px solid #ef4444" : "none",
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: "0.82rem",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            {isRunning ? <Pause size={14} /> : <Play size={14} fill="#fff" />}
            <span>{isRunning ? "Pause" : "Start"}</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setIsRunning(false);
              setSeconds(data.durationSeconds);
            }}
            title="Reset"
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "rgba(255,255,255,0.06)",
              border: "none",
              color: "rgba(255,255,255,0.6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: "100%",
          height: 4,
          borderRadius: 2,
          background: "rgba(255,255,255,0.06)",
          overflow: "hidden",
        }}
      >
        <motion.div
          style={{
            height: "100%",
            background: "#eb6f92",
            borderRadius: 2,
          }}
          animate={{ width: `${progressPercent}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() =>
            onCommit({
              ...data,
              remainingSeconds: seconds,
              isRunning,
              isCompleted: seconds === 0,
            })
          }
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.08)",
            color: "#ffffff",
            border: "1px solid rgba(255,255,255,0.1)",
            fontWeight: 650,
            fontSize: "0.8rem",
            cursor: "pointer",
          }}
        >
          <Check size={14} />
          <span>Keep Timer Active ↵</span>
        </button>
      )}
    </div>
  );
}
