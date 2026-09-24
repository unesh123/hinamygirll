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
              background: "rgba(79, 185, 137, 0.15)",
              color: "#4fb989",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Users size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700, letterSpacing: "0.02em" }}>
            Split Bill
          </span>
        </div>
        <span style={{ fontSize: "0.78rem", color: "rgba(255,255,255,0.5)", fontWeight: 500 }}>
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
          padding: "10px 14px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
        }}
      >
        <div>
          <div style={{ fontSize: "0.72rem", color: "rgba(255,255,255,0.5)", textTransform: "uppercase" }}>
            Each person pays
          </div>
          <motion.div
            animate={ticking ? HINA_MOTION.tick : { scale: 1 }}
            style={{
              fontSize: "1.75rem",
              fontWeight: 800,
              color: "#4fb989",
              lineHeight: 1.1,
              marginTop: 2,
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
              background: "rgba(255,255,255,0.08)",
              border: "none",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: people > 1 ? "pointer" : "not-allowed",
              opacity: people > 1 ? 1 : 0.4,
            }}
          >
            <Minus size={15} />
          </button>
          <span style={{ minWidth: 20, textAlign: "center", fontWeight: 700, fontSize: "1rem" }}>
            {people}
          </span>
          <button
            type="button"
            onClick={() => handlePeopleChange(1)}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "rgba(255,255,255,0.08)",
              border: "none",
              color: "#ffffff",
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
        <span style={{ fontSize: "0.72rem", color: "rgba(255,255,255,0.4)", marginRight: 4 }}>Tip:</span>
        {[0, 10, 15, 20].map((tip) => (
          <button
            key={tip}
            type="button"
            onClick={() => handleTipChange(tip)}
            style={{
              padding: "3px 9px",
              borderRadius: 6,
              background: tipPercent === tip ? "#4fb989" : "rgba(255,255,255,0.06)",
              color: tipPercent === tip ? "#000000" : "rgba(255,255,255,0.7)",
              border: "none",
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
            padding: "8px 14px",
            borderRadius: 8,
            background: "#4fb989",
            color: "#000000",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Save Split ↵</span>
        </button>
      )}
    </div>
  );
}
