import React, { useState, useEffect, useCallback } from "react";
import { HINAA_DEV_USER } from "../../lib/hinaaIdentity";
import { Sparkles, Calendar, Zap, RefreshCw, ShieldCheck, Layers, ExternalLink } from "lucide-react";

interface BudgetStatus {
  planCredits: number;
  anchorDay: number;
  cycleStart: string;
  cycleEnd: string;
  daysRemaining: number;
  totalCycleDays: number;
  hinaaApiCreditsUsed: number;
  todayCreditsUsed: number;
  manualBalanceSnapshot: number | null;
  manualSnapshotTime: string | null;
  effectiveRemaining: number;
  dailyPace: number;
  pacingMode: "economy" | "balanced" | "quality" | "use-it-wisely";
  pacingAdvice: string;
  videoGenerationEnabled: boolean;
}

export function MagnificBudgetWidget() {
  const [status, setStatus] = useState<BudgetStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshotInput, setSnapshotInput] = useState("");
  const [showSnapshotModal, setShowSnapshotModal] = useState(false);

  const fetchBudget = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/creative/budget", {
        headers: { "X-HINAA-Dev-User": HINAA_DEV_USER },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BudgetStatus = await res.json();
      setStatus(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load budget");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBudget();
    const timer = setInterval(fetchBudget, 60000);
    return () => clearInterval(timer);
  }, [fetchBudget]);

  const handleUpdateSnapshot = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseInt(snapshotInput, 10);
    if (isNaN(val) || val < 0) return;
    try {
      const res = await fetch("/api/v1/creative/budget/snapshot", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-HINAA-Dev-User": HINAA_DEV_USER,
        },
        body: JSON.stringify({ balance: val }),
      });
      if (res.ok) {
        const updated = await res.json();
        setStatus(updated);
        setShowSnapshotModal(false);
        setSnapshotInput("");
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (!status && loading) {
    return (
      <div
        style={{
          padding: "var(--space-4)",
          borderRadius: "var(--radius-xl)",
          background: "var(--bg-surface-raised)",
          border: "1px solid var(--border-subtle)",
          color: "var(--text-tertiary)",
          fontSize: "var(--text-xs)",
        }}
      >
        Syncing Magnific Premium+ 45,000 credit budget…
      </div>
    );
  }

  if (!status) return null;

  const modeColors: Record<string, { bg: string; border: string; text: string }> = {
    economy: { bg: "rgba(14, 165, 233, 0.10)", border: "rgba(14, 165, 233, 0.25)", text: "#0284c7" },
    balanced: { bg: "rgba(16, 185, 129, 0.10)", border: "rgba(16, 185, 129, 0.25)", text: "#059669" },
    quality: { bg: "rgba(245, 158, 11, 0.10)", border: "rgba(245, 158, 11, 0.25)", text: "#d97706" },
    "use-it-wisely": { bg: "rgba(168, 85, 247, 0.10)", border: "rgba(168, 85, 247, 0.25)", text: "#9333ea" },
  };

  const currentTheme = modeColors[status.pacingMode] || modeColors.balanced;
  const progressPercent = Math.min(100, Math.round((status.todayCreditsUsed / Math.max(1, status.dailyPace)) * 100));

  return (
    <div
      style={{
        width: "100%",
        borderRadius: "var(--radius-xl, 16px)",
        background: "var(--bg-surface-raised)",
        border: "1px solid var(--border-subtle)",
        boxShadow: "var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.04))",
        padding: "var(--space-4, 16px)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3, 12px)",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "var(--radius-md, 8px)",
              background: "var(--accent-pale, rgba(244, 114, 182, 0.12))",
              color: "var(--accent, #f472b6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "1px solid rgba(244, 114, 182, 0.22)",
              flexShrink: 0,
            }}
          >
            <Sparkles size={18} />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontWeight: 700, fontSize: "var(--text-sm, 14px)", color: "var(--text-primary)" }}>
                Magnific Premium+
              </span>
              <span
                style={{
                  fontSize: "0.68rem",
                  fontWeight: 650,
                  padding: "2px 8px",
                  borderRadius: "var(--radius-pill)",
                  background: "var(--accent-pale, rgba(244, 114, 182, 0.10))",
                  color: "var(--accent, #f472b6)",
                  border: "1px solid rgba(244, 114, 182, 0.25)",
                }}
              >
                45,000 Credits
              </span>
            </div>
            <span
              style={{
                fontSize: "var(--text-xs, 12px)",
                color: "var(--text-tertiary)",
                display: "flex",
                alignItems: "center",
                gap: 4,
                marginTop: 2,
              }}
            >
              <Calendar size={12} />
              Reset on Day {status.anchorDay} ({status.daysRemaining} days remaining in cycle)
            </span>
          </div>
        </div>

        {/* Pacing Mode Pill & Refresh */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              fontSize: "0.7rem",
              textTransform: "uppercase",
              fontWeight: 700,
              letterSpacing: "0.04em",
              padding: "4px 10px",
              borderRadius: "var(--radius-pill)",
              background: currentTheme.bg,
              border: `1px solid ${currentTheme.border}`,
              color: currentTheme.text,
            }}
          >
            {status.pacingMode}
          </span>
          <button
            type="button"
            onClick={fetchBudget}
            disabled={loading}
            style={{
              width: 30,
              height: 30,
              borderRadius: "var(--radius-md, 8px)",
              border: "1px solid var(--border-subtle)",
              background: "var(--bg-canvas)",
              color: "var(--text-secondary)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "color 150ms ease",
            }}
            title="Refresh Budget"
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
        <div
          style={{
            padding: "10px 14px",
            borderRadius: "var(--radius-lg, 12px)",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <span style={{ fontSize: "var(--text-xs, 12px)", color: "var(--text-tertiary)", display: "block", marginBottom: 2 }}>
            Effective Balance
          </span>
          <span style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--text-primary)", display: "block" }}>
            {status.effectiveRemaining.toLocaleString()}
          </span>
          <span style={{ fontSize: "0.68rem", color: "var(--text-tertiary)", marginTop: 2, display: "block" }}>
            {status.manualBalanceSnapshot !== null ? "Manual snapshot" : "Estimated"}
          </span>
        </div>

        <div
          style={{
            padding: "10px 14px",
            borderRadius: "var(--radius-lg, 12px)",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <span style={{ fontSize: "var(--text-xs, 12px)", color: "var(--text-tertiary)", display: "block", marginBottom: 2 }}>
            Dynamic Daily Pace
          </span>
          <span style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--accent, #f472b6)", display: "block" }}>
            ~{status.dailyPace.toLocaleString()}
          </span>
          <span style={{ fontSize: "0.68rem", color: "var(--text-tertiary)", marginTop: 2, display: "block" }}>
            credits / day target
          </span>
        </div>

        <div
          style={{
            padding: "10px 14px",
            borderRadius: "var(--radius-lg, 12px)",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <span style={{ fontSize: "var(--text-xs, 12px)", color: "var(--text-tertiary)", display: "block", marginBottom: 2 }}>
            HINAA API Spend
          </span>
          <span style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--text-secondary)", display: "block" }}>
            {status.hinaaApiCreditsUsed.toLocaleString()}
          </span>
          <span style={{ fontSize: "0.68rem", color: "var(--text-tertiary)", marginTop: 2, display: "block" }}>
            this billing cycle
          </span>
        </div>
      </div>

      {/* Today's Consumption Bar */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "var(--text-xs, 12px)", marginBottom: 6 }}>
          <span style={{ color: "var(--text-secondary)" }}>Today's Consumption</span>
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)", fontWeight: 600 }}>
            {status.todayCreditsUsed} / {status.dailyPace} credits ({progressPercent}%)
          </span>
        </div>
        <div
          style={{
            width: "100%",
            height: 6,
            borderRadius: "var(--radius-pill)",
            background: "var(--bg-secondary)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${Math.min(100, progressPercent)}%`,
              borderRadius: "var(--radius-pill)",
              background:
                progressPercent >= 100
                  ? "var(--danger, #f43f5e)"
                  : progressPercent >= 75
                  ? "var(--warning, #f59e0b)"
                  : "linear-gradient(90deg, var(--accent, #f472b6), #ec4899)",
              transition: "width 0.4s ease",
            }}
          />
        </div>
      </div>

      {/* Dynamic Pacing Advice */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
          padding: "10px 12px",
          borderRadius: "var(--radius-lg, 12px)",
          background: "var(--accent-pale, rgba(244, 114, 182, 0.08))",
          border: "1px solid rgba(244, 114, 182, 0.2)",
          fontSize: "var(--text-xs, 12px)",
          color: "var(--text-primary)",
        }}
      >
        <Zap size={14} style={{ color: "var(--accent, #f472b6)", flexShrink: 0, marginTop: 1 }} />
        <div style={{ lineHeight: 1.4 }}>
          <strong style={{ fontWeight: 650, color: "var(--text-primary)" }}>Pacing Strategy: </strong>
          <span style={{ color: "var(--text-secondary)" }}>{status.pacingAdvice}</span>
        </div>
      </div>

      {/* Footer Guardrails & Snapshot Trigger */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "0.72rem",
          paddingTop: 8,
          borderTop: "1px solid var(--border-subtle)",
          color: "var(--text-tertiary)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4, color: "#10b981", fontWeight: 600 }}>
            <ShieldCheck size={13} />
            Strict Video Ban (0 credit waste)
          </span>
          <span>·</span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-secondary)" }}>
            <Layers size={13} />
            Fast: 1c-5c · Flux: 10c · Mystic: 50c
          </span>
        </div>

        <button
          type="button"
          onClick={() => setShowSnapshotModal(true)}
          style={{
            background: "none",
            border: "none",
            color: "var(--accent, #f472b6)",
            fontSize: "0.72rem",
            fontWeight: 650,
            cursor: "pointer",
            padding: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: 3,
          }}
        >
          Sync Dashboard Balance <ExternalLink size={11} />
        </button>
      </div>

      {/* Snapshot Modal */}
      {showSnapshotModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0, 0, 0, 0.35)",
            backdropFilter: "blur(6px)",
            padding: "var(--space-4)",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface-raised, #ffffff)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-xl, 16px)",
              padding: "var(--space-5, 20px)",
              maxWidth: 380,
              width: "100%",
              boxShadow: "var(--shadow-xl, 0 20px 30px rgba(0,0,0,0.15))",
            }}
          >
            <h3 style={{ fontSize: "var(--text-md, 16px)", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
              Sync Magnific Balance
            </h3>
            <p style={{ fontSize: "var(--text-xs, 12px)", color: "var(--text-secondary)", marginBottom: 16, lineHeight: 1.4 }}>
              Enter your current credit balance as displayed on your Magnific/Freepik web dashboard.
            </p>
            <form onSubmit={handleUpdateSnapshot}>
              <input
                type="number"
                min="0"
                max="100000"
                value={snapshotInput}
                onChange={(e) => setSnapshotInput(e.target.value)}
                placeholder="e.g. 42500"
                style={{
                  width: "100%",
                  background: "var(--bg-canvas)",
                  border: "1px solid var(--border-default)",
                  borderRadius: "var(--radius-md, 8px)",
                  padding: "8px 12px",
                  fontSize: "var(--text-sm)",
                  color: "var(--text-primary)",
                  outline: "none",
                  marginBottom: 16,
                  fontFamily: "var(--font-mono)",
                }}
                autoFocus
              />
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setShowSnapshotModal(false)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: "var(--radius-md, 8px)",
                    background: "var(--bg-secondary)",
                    border: "1px solid var(--border-subtle)",
                    color: "var(--text-secondary)",
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: "6px 16px",
                    borderRadius: "var(--radius-md, 8px)",
                    background: "var(--accent, #f472b6)",
                    border: "none",
                    color: "#ffffff",
                    fontSize: "var(--text-xs)",
                    fontWeight: 650,
                    cursor: "pointer",
                    boxShadow: "0 2px 8px var(--accent-glow)",
                  }}
                >
                  Save Snapshot
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
