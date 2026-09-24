import React, { useState } from "react";
import { motion } from "framer-motion";
import { Users, Plus, Minus, Check, DollarSign } from "lucide-react";
import { HINA_MOTION } from "../../motion/MOTION";
import type { SplitFields } from "../types";

interface SplitCardProps {
  data: SplitFields;
  onCommit?: (updated: SplitFields) => void;
  compact?: boolean;
}

export function SplitCard({ data, onCommit, compact = false }: SplitCardProps) {
  const [people, setPeople] = useState(data.peopleCount);
  const [tipPercent, setTipPercent] = useState(data.tipPercent || 0);
  const [ticking, setTicking] = useState(false);

  const totalWithTip = Math.round(data.totalAmount * (1 + tipPercent / 100));
  const perPerson = Math.round(totalWithTip / Math.max(1, people));

  const handlePeopleChange = (delta: number) => {
    const next = Math.max(1, people + delta);
    setPeople(next);
    setTicking(true);
    setTimeout(() => setTicking(false), 140);
  };

  const handleTipChange = (tip: number) => {
    setTipPercent(tip);
    setTicking(true);
    setTimeout(() => setTicking(false), 140);
  };

  return (
    <div
      style={{
        padding: compact ? "12px 14px" : "16px 20px",
        borderRadius: "14px",
        background: "var(--bg-surface-raised, #ffffff)",
        border: "1px solid var(--border-default, #e2e8f0)",
        boxShadow: "0 8px 30px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04)",
        color: "var(--text-primary, #0f172a)",
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
              background: "rgba(16, 185, 129, 0.15)",
              color: "#059669",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Users size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-primary, #0f172a)", letterSpacing: "0.02em" }}>
            Split Bill
          </span>
        </div>
        <span style={{ fontSize: "0.82rem", color: "var(--text-secondary, #475569)", fontWeight: 600 }}>
          Total: {data.currency}
          {totalWithTip.toLocaleString()}
        </span>
      </div>

      {/* Main Calculated Value with TICK motion */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderRadius: 10,
          background: "var(--surface-subtle, rgba(0,0,0,0.03))",
          border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
        }}
      >
        <div>
          <div style={{ fontSize: "0.74rem", color: "var(--text-secondary, #475569)", fontWeight: 600, textTransform: "uppercase" }}>
            Each person pays
          </div>
          <motion.div
            animate={ticking ? HINA_MOTION.tick : { scale: 1 }}
            style={{
              fontSize: "1.85rem",
              fontWeight: 800,
              color: "#059669",
              lineHeight: 1.1,
              marginTop: 3,
            }}
          >
            {data.currency}
            {perPerson.toLocaleString()}
          </motion.div>
        </div>

        {/* People Counter Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            type="button"
            onClick={() => handlePeopleChange(-1)}
            disabled={people <= 1}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "var(--surface-subtle, rgba(0,0,0,0.06))",
              border: "1px solid var(--border-subtle, rgba(0,0,0,0.1))",
              color: "var(--text-primary, #0f172a)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: people > 1 ? "pointer" : "not-allowed",
              opacity: people > 1 ? 1 : 0.4,
            }}
          >
            <Minus size={15} />
          </button>
          <span style={{ minWidth: 20, textAlign: "center", fontWeight: 750, fontSize: "1.05rem", color: "var(--text-primary, #0f172a)" }}>
            {people}
          </span>
          <button
            type="button"
            onClick={() => handlePeopleChange(1)}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "var(--surface-subtle, rgba(0,0,0,0.06))",
              border: "1px solid var(--border-subtle, rgba(0,0,0,0.1))",
              color: "var(--text-primary, #0f172a)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <Plus size={15} />
          </button>
        </div>
      </div>

      {/* Tip presets */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: "0.75rem", color: "var(--text-secondary, #475569)", fontWeight: 600, marginRight: 4 }}>Tip:</span>
        {[0, 10, 15, 20].map((tip) => (
          <button
            key={tip}
            type="button"
            onClick={() => handleTipChange(tip)}
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              background: tipPercent === tip ? "#059669" : "var(--surface-subtle, rgba(0,0,0,0.05))",
              color: tipPercent === tip ? "#ffffff" : "var(--text-secondary, #475569)",
              border: "1px solid var(--border-subtle, rgba(0,0,0,0.08))",
              fontSize: "0.75rem",
              fontWeight: 650,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {tip === 0 ? "None" : `${tip}%`}
          </button>
        ))}
      </div>

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() =>
            onCommit({
              ...data,
              peopleCount: people,
              tipPercent,
              perPerson,
              totalAmount: totalWithTip,
            })
          }
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "9px 14px",
            borderRadius: 8,
            background: "#059669",
            color: "#ffffff",
            border: "none",
            fontWeight: 750,
            fontSize: "0.84rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={15} strokeWidth={2.5} />
          <span>Save Split ↵</span>
        </button>
      )}
    </div>
  );
}
