import React, { useState } from "react";
import { motion } from "framer-motion";
import { Dices, RotateCcw, Check } from "lucide-react";
import { HINA_MOTION } from "../../motion/MOTION";
import type { RandomFields } from "../types";

interface RandomCardProps {
  data: RandomFields;
  onCommit?: (updated: RandomFields) => void;
  compact?: boolean;
}

export function RandomCard({ data, onCommit, compact = false }: RandomCardProps) {
  const [rolls, setRolls] = useState<number[]>(data.rolls);
  const [ticking, setTicking] = useState(false);

  const rollDice = () => {
    setTicking(true);
    const newRolls: number[] = [];
    for (let i = 0; i < data.diceCount; i++) {
      newRolls.push(Math.floor(Math.random() * data.diceSides) + 1);
    }
    setRolls(newRolls);
    setTimeout(() => setTicking(false), 140);
  };

  const total = rolls.reduce((acc, curr) => acc + curr, 0);

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
              background: "rgba(244, 63, 94, 0.15)",
              color: "#f43f5e",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Dices size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>
            {data.type === "coin" ? "Coin Flip" : `${data.diceCount}d${data.diceSides} Dice Roll`}
          </span>
        </div>
        <button
          type="button"
          onClick={rollDice}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "4px 10px",
            borderRadius: 6,
            background: "rgba(255,255,255,0.08)",
            color: "#ffffff",
            border: "none",
            fontSize: "0.75rem",
            fontWeight: 650,
            cursor: "pointer",
          }}
        >
          <RotateCcw size={13} />
          <span>Roll Again</span>
        </button>
      </div>

      {/* Dice Face Visuals */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
          padding: "16px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.05)",
        }}
      >
        {rolls.map((roll, idx) => (
          <motion.div
            key={idx}
            animate={ticking ? { rotate: [0, 15, -15, 0], scale: [1, 1.15, 1] } : {}}
            transition={{ duration: 0.18 }}
            style={{
              width: 54,
              height: 54,
              borderRadius: 12,
              background: "linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.75rem",
              fontWeight: 800,
              boxShadow: "0 6px 16px rgba(244, 63, 94, 0.4)",
            }}
          >
            {data.type === "coin" ? (roll === 1 ? "H" : "T") : roll}
          </motion.div>
        ))}
      </div>

      {/* Total calculation */}
      {rolls.length > 1 && (
        <div style={{ textAlign: "center", fontSize: "0.85rem", color: "rgba(255,255,255,0.7)" }}>
          Total sum: <strong style={{ color: "#ffffff", fontSize: "1.1rem" }}>{total}</strong>
        </div>
      )}

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() => onCommit({ ...data, rolls, total })}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            background: "#f43f5e",
            color: "#ffffff",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Keep Result ↵</span>
        </button>
      )}
    </div>
  );
}
