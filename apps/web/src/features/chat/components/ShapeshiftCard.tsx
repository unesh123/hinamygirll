import React, { useState, useEffect, useMemo } from "react";
import {
  Calendar,
  CheckSquare,
  Clock,
  Palette,
  DollarSign,
  Globe2,
  Bell,
  Dices,
  Play,
  RotateCcw,
  Check,
  Copy,
  ExternalLink,
  Monitor,
  Share2,
  ArrowRight,
  X,
  Sparkles,
} from "lucide-react";

export type ShapeshiftIntentType =
  | "event"
  | "checklist"
  | "timer"
  | "color"
  | "split"
  | "timezone"
  | "reminder"
  | "dice"
  | "social_reach"
  | "desktop_operator";

export interface ShapeshiftData {
  type: ShapeshiftIntentType;
  title: string;
  subtitle: string;
  rawText: string;
  payload: any;
}

interface ShapeshiftCardProps {
  input: string;
  onExecute: (text: string, executeImmediately?: boolean) => void;
  onDismiss?: () => void;
  isDark?: boolean;
}

export function parseShapeshiftIntent(input: string): ShapeshiftData | null {
  const text = input.trim();
  if (!text || text.length < 3) return null;

  // 1. Color detector (#hex, rgb, or named special colors)
  const hexMatch = text.match(/#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/i);
  const rgbMatch = text.match(/rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)/i);
  const namedColors: Record<string, string> = {
    "minecraft diamond": "#4dedf4",
    "cyberpunk neon": "#00ffcc",
    "nordic frost": "#70c1b3",
    "sunset gold": "#ffb347",
    "tokyo sakura": "#ff9ebb",
    "emerald green": "#10b981",
  };
  const namedColorKey = Object.keys(namedColors).find((k) =>
    text.toLowerCase().includes(k)
  );

  if (hexMatch || rgbMatch || namedColorKey) {
    const colorHex = hexMatch
      ? hexMatch[0]
      : rgbMatch
      ? `#${(
          (1 << 24) +
          (parseInt(rgbMatch[1]) << 16) +
          (parseInt(rgbMatch[2]) << 8) +
          parseInt(rgbMatch[3])
        )
          .toString(16)
          .slice(1)}`
      : namedColors[namedColorKey!];

    return {
      type: "color",
      title: "Color Swatch",
      subtitle: namedColorKey ? `Theme: ${namedColorKey}` : colorHex.toUpperCase(),
      rawText: text,
      payload: { hex: colorHex, name: namedColorKey },
    };
  }

  // 2. Dice detector (e.g. "roll 2d6", "roll d20", "flip a coin")
  const diceMatch = text.match(/(?:roll\s+)?(\d*)d(4|6|8|10|12|20|100)\b/i);
  const coinMatch = text.match(/flip\s+a?\s*coin/i);
  if (diceMatch || coinMatch) {
    const isCoin = !!coinMatch;
    const count = diceMatch && diceMatch[1] ? parseInt(diceMatch[1]) : 1;
    const sides = diceMatch ? parseInt(diceMatch[2]) : 2;
    return {
      type: "dice",
      title: isCoin ? "Coin Flipper" : `Dice Roller (${count}d${sides})`,
      subtitle: isCoin ? "Heads or Tails" : `Roll up to ${count * sides}`,
      rawText: text,
      payload: { isCoin, count, sides },
    };
  }

  // 3. Timer / Focus detector (e.g. "25 min focus", "timer 10 mins", "15m study")
  const timerMatch = text.match(
    /(?:(?:set\s+)?timer\s+(?:for\s+)?|focus\s+(?:for\s+)?)?(\d+)\s*(min|mins|minutes|sec|secs|seconds|hr|hrs|hours)\b(?:\s+(focus|break|study|meditation|workout))?/i
  );
  if (timerMatch && (text.toLowerCase().includes("timer") || text.toLowerCase().includes("focus") || text.toLowerCase().includes("min"))) {
    const amount = parseInt(timerMatch[1]);
    const unit = timerMatch[2].toLowerCase();
    const tag = timerMatch[3] || "Focus";
    let totalSeconds = amount * 60;
    if (unit.startsWith("sec")) totalSeconds = amount;
    if (unit.startsWith("hr")) totalSeconds = amount * 3600;

    return {
      type: "timer",
      title: `Timer • ${amount} ${unit}`,
      subtitle: `Preset: ${tag.toUpperCase()} session`,
      rawText: text,
      payload: { totalSeconds, tag, amount, unit },
    };
  }

  // 4. Split / Bill detector (e.g. "split 2400 between 3", "split $120 with 4 friends")
  const splitMatch = text.match(
    /split\s+(?:[$€£₹])?(\d+(?:\.\d{1,2})?)\s+(?:between|with|among)\s+(\d+)(?:\s*(?:people|friends|us|ways)?)?/i
  );
  if (splitMatch) {
    const total = parseFloat(splitMatch[1]);
    const people = parseInt(splitMatch[2]);
    const perPerson = people > 0 ? (total / people).toFixed(2) : total.toFixed(2);
    return {
      type: "split",
      title: "Split Expense",
      subtitle: `$${total} ÷ ${people} people = $${perPerson} each`,
      rawText: text,
      payload: { total, people, perPerson },
    };
  }

  // 5. Timezone Converter (e.g. "3pm pst in ist", "9am tokyo in est")
  const tzMatch = text.match(
    /(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+([a-zA-Z]{3,4})\s+(?:to|in)\s+([a-zA-Z]{3,4})/i
  );
  if (tzMatch) {
    const timeStr = tzMatch[1];
    const fromZone = tzMatch[2].toUpperCase();
    const toZone = tzMatch[3].toUpperCase();
    return {
      type: "timezone",
      title: "Timezone Converter",
      subtitle: `${timeStr} ${fromZone} ➔ ${toZone}`,
      rawText: text,
      payload: { timeStr, fromZone, toZone },
    };
  }

  // 6. Checklist detector (e.g. "buy milk, eggs, bread" or "checklist: apples, milk, flour")
  const checklistMatch = text.match(
    /^(?:buy|pack|todo|checklist|groceries|get|bring):\s*(.+)$/i
  ) || text.match(
    /(?:buy|pack|get)\s+([^,.?!]+(?:,\s*[^,.?!]+)+)/i
  );
  if (checklistMatch) {
    const rawItems = (checklistMatch[1] || checklistMatch[0])
      .replace(/^(buy|pack|get|todo|checklist|groceries|bring):\s*/i, "")
      .replace(/^(buy|pack|get)\s+/i, "")
      .split(/,|\n/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    if (rawItems.length >= 2) {
      return {
        type: "checklist",
        title: "Checklist Generator",
        subtitle: `${rawItems.length} items parsed`,
        rawText: text,
        payload: { items: rawItems },
      };
    }
  }

  // 7. Event detector (e.g. "dinner with priya friday 8pm", "meeting with team tomorrow 3pm")
  const eventMatch = text.match(
    /(dinner|lunch|breakfast|coffee|meeting|call|sync|interview|date)\s+(?:with\s+([\w\s]+?)\s+)?(?:(at|on|this|next|tomorrow|friday|saturday|sunday|monday|tuesday|wednesday|thursday)\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)/i
  );
  if (eventMatch) {
    const activity = eventMatch[1];
    const withPerson = eventMatch[2]?.trim() || "";
    const day = eventMatch[3] || "Upcoming";
    const time = eventMatch[4] || "";
    return {
      type: "event",
      title: `${activity.charAt(0).toUpperCase() + activity.slice(1)}${withPerson ? ` with ${withPerson}` : ""}`,
      subtitle: `${day} at ${time}`,
      rawText: text,
      payload: { activity, withPerson, day, time },
    };
  }

  // 8. Reminder detector (e.g. "remind me to pay rent tomorrow 9am")
  const reminderMatch = text.match(
    /remind\s+(?:me\s+)?(?:to\s+)?(.+?)\s+(at|on|tomorrow|in\s+\d+\s*(?:mins|hours|days))/i
  );
  if (reminderMatch) {
    const task = reminderMatch[1];
    const when = reminderMatch[2];
    return {
      type: "reminder",
      title: "Smart Reminder",
      subtitle: `${task} (${when})`,
      rawText: text,
      payload: { task, when },
    };
  }

  // 9. Agent-Reach Social Intelligence detector
  const reachMatch = text.match(
    /(?:search|find|lookup|scan)\s+(?:on\s+)?(x|twitter|reddit|youtube|github)\s+(?:for\s+)?(.+)/i
  );
  if (reachMatch) {
    const platform = reachMatch[1].toLowerCase() === "twitter" ? "x" : reachMatch[1].toLowerCase();
    const query = reachMatch[2].trim();
    return {
      type: "social_reach",
      title: `Agent-Reach • ${platform.toUpperCase()}`,
      subtitle: `Multi-Platform intelligence scan for "${query}"`,
      rawText: text,
      payload: { platform, query },
    };
  }

  // 10. Native Desktop Computer Operator detector
  const desktopMatch = text.match(
    /(?:open|launch|focus)\s+(spotify|arc|whatsapp|chrome|discord|vscode|terminal)|(?:play\s+(.+)\s+on\s+spotify)|(?:play\s+(.+)\s+on\s+youtube)/i
  );
  if (desktopMatch) {
    const app = desktopMatch[1];
    const spotifySong = desktopMatch[2];
    const ytQuery = desktopMatch[3];
    return {
      type: "desktop_operator",
      title: "Native Desktop Computer Operator",
      subtitle: app
        ? `Focus / Launch application: ${app.toUpperCase()}`
        : spotifySong
        ? `Spotify Sub-ms Stream: "${spotifySong}"`
        : `YouTube Direct Play: "${ytQuery}"`,
      rawText: text,
      payload: { app, spotifySong, ytQuery },
    };
  }

  return null;
}

export function ShapeshiftCard({
  input,
  onExecute,
  onDismiss,
  isDark = true,
}: ShapeshiftCardProps) {
  const intent = useMemo(() => parseShapeshiftIntent(input), [input]);

  // Sub-states for interactive cards
  const [checkedItems, setCheckedItems] = useState<Record<number, boolean>>({});
  const [timerRunning, setTimerRunning] = useState(false);
  const [timerSecondsLeft, setTimerSecondsLeft] = useState(0);
  const [diceResult, setDiceResult] = useState<string | number | null>(null);
  const [copiedHex, setCopiedHex] = useState(false);
  const [tipPercent, setTipPercent] = useState(15);

  useEffect(() => {
    if (intent?.type === "timer") {
      setTimerSecondsLeft(intent.payload.totalSeconds);
      setTimerRunning(false);
    }
  }, [intent?.type, intent?.payload?.totalSeconds]);

  useEffect(() => {
    let interval: any = null;
    if (timerRunning && timerSecondsLeft > 0) {
      interval = setInterval(() => {
        setTimerSecondsLeft((s) => (s > 0 ? s - 1 : 0));
      }, 1000);
    } else if (timerSecondsLeft === 0 && timerRunning) {
      setTimerRunning(false);
    }
    return () => clearInterval(interval);
  }, [timerRunning, timerSecondsLeft]);

  if (!intent) return null;

  const handleRollDice = () => {
    if (intent.payload.isCoin) {
      setDiceResult(Math.random() > 0.5 ? "Heads 🪙" : "Tails 🪙");
    } else {
      let sum = 0;
      for (let i = 0; i < intent.payload.count; i++) {
        sum += Math.floor(Math.random() * intent.payload.sides) + 1;
      }
      setDiceResult(sum);
    }
  };

  const handleCopyHex = (hex: string) => {
    navigator.clipboard?.writeText(hex);
    setCopiedHex(true);
    setTimeout(() => setCopiedHex(false), 2000);
  };

  return (
    <div
      data-testid="shapeshift-card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "10px 14px",
        borderRadius: "12px",
        background: isDark
          ? "linear-gradient(135deg, rgba(30, 27, 46, 0.95), rgba(18, 16, 28, 0.95))"
          : "linear-gradient(135deg, #ffffff, #f8fafc)",
        border: isDark
          ? "1px solid rgba(139, 92, 246, 0.35)"
          : "1px solid rgba(139, 92, 246, 0.25)",
        boxShadow: isDark
          ? "0 8px 24px -4px rgba(0, 0, 0, 0.6), 0 0 12px rgba(139, 92, 246, 0.2)"
          : "0 8px 20px -4px rgba(0, 0, 0, 0.08), 0 0 10px rgba(139, 92, 246, 0.1)",
        backdropFilter: "blur(12px)",
        marginBottom: 8,
        transition: "all 180ms cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {/* ── Top Header ────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 24,
              height: 24,
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(139, 92, 246, 0.15)",
              color: "#a855f7",
            }}
          >
            {intent.type === "event" && <Calendar size={14} />}
            {intent.type === "checklist" && <CheckSquare size={14} />}
            {intent.type === "timer" && <Clock size={14} />}
            {intent.type === "color" && <Palette size={14} />}
            {intent.type === "split" && <DollarSign size={14} />}
            {intent.type === "timezone" && <Globe2 size={14} />}
            {intent.type === "reminder" && <Bell size={14} />}
            {intent.type === "dice" && <Dices size={14} />}
            {intent.type === "social_reach" && <Share2 size={14} />}
            {intent.type === "desktop_operator" && <Monitor size={14} />}
          </div>
          <div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 650,
                color: isDark ? "#f3e8ff" : "#1e1b4b",
                lineHeight: 1.2,
              }}
            >
              {intent.title}
            </div>
            <div
              style={{
                fontSize: 10,
                color: isDark ? "#a1a1aa" : "#64748b",
                lineHeight: 1.2,
              }}
            >
              {intent.subtitle}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss Shapeshift preview"
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: 4,
                color: isDark ? "#71717a" : "#94a3b8",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* ── Interactive Intent Body ───────────────────────────── */}
      <div style={{ marginTop: 2 }}>
        {/* EVENT */}
        {intent.type === "event" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 10px",
              borderRadius: "8px",
            }}
          >
            <span style={{ fontSize: 11, color: isDark ? "#d4d4d8" : "#334155" }}>
              🗓️ <strong>{intent.payload.activity}</strong> {intent.payload.withPerson && `w/ ${intent.payload.withPerson}`} on{" "}
              <strong>{intent.payload.day}</strong> at {intent.payload.time}
            </span>
            <button
              type="button"
              onClick={() => onExecute(`Schedule calendar event: ${intent.rawText}`, true)}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                background: "#8b5cf6",
                color: "#fff",
                border: "none",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <span>Add Event</span>
              <ArrowRight size={11} />
            </button>
          </div>
        )}

        {/* CHECKLIST */}
        {intent.type === "checklist" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 6,
                padding: "4px 0",
              }}
            >
              {intent.payload.items.map((item: string, idx: number) => {
                const isChecked = !!checkedItems[idx];
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() =>
                      setCheckedItems((prev) => ({ ...prev, [idx]: !prev[idx] }))
                    }
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "3px 8px",
                      borderRadius: "6px",
                      fontSize: 11,
                      cursor: "pointer",
                      border: isChecked
                        ? "1px solid #10b981"
                        : isDark
                        ? "1px solid rgba(255,255,255,0.1)"
                        : "1px solid #cbd5e1",
                      background: isChecked
                        ? "rgba(16, 185, 129, 0.15)"
                        : isDark
                        ? "rgba(255,255,255,0.04)"
                        : "#f8fafc",
                      color: isChecked ? "#10b981" : isDark ? "#e4e4e7" : "#1e293b",
                      textDecoration: isChecked ? "line-through" : "none",
                    }}
                  >
                    <CheckSquare size={11} />
                    <span>{item}</span>
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => onExecute(`Create checklist task items:\n${intent.payload.items.map((i: string) => `- [ ] ${i}`).join("\n")}`, true)}
              style={{
                alignSelf: "flex-end",
                padding: "3px 9px",
                borderRadius: "6px",
                background: "#8b5cf6",
                color: "#fff",
                border: "none",
                fontSize: 10,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Save to Tasks
            </button>
          </div>
        )}

        {/* TIMER */}
        {intent.type === "timer" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 16,
                  fontWeight: 700,
                  color: timerRunning ? "#10b981" : isDark ? "#f3e8ff" : "#1e1b4b",
                }}
              >
                {Math.floor(timerSecondsLeft / 60)
                  .toString()
                  .padStart(2, "0")}
                :{(timerSecondsLeft % 60).toString().padStart(2, "0")}
              </span>
              <span style={{ fontSize: 10, color: isDark ? "#a1a1aa" : "#64748b" }}>
                {timerRunning ? "Running..." : "Ready"}
              </span>
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() => setTimerRunning(!timerRunning)}
                style={{
                  padding: "4px 10px",
                  borderRadius: "6px",
                  background: timerRunning ? "#ef4444" : "#10b981",
                  color: "#fff",
                  border: "none",
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {timerRunning ? "Pause" : <><Play size={10} /> Start</>}
              </button>
              <button
                type="button"
                onClick={() => {
                  setTimerRunning(false);
                  setTimerSecondsLeft(intent.payload.totalSeconds);
                }}
                style={{
                  padding: "4px 8px",
                  borderRadius: "6px",
                  background: isDark ? "rgba(255,255,255,0.06)" : "#e2e8f0",
                  color: isDark ? "#d4d4d8" : "#475569",
                  border: "none",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                <RotateCcw size={11} />
              </button>
            </div>
          </div>
        )}

        {/* COLOR */}
        {intent.type === "color" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "6px",
                  background: intent.payload.hex,
                  border: "1px solid rgba(255,255,255,0.2)",
                  boxShadow: `0 0 10px ${intent.payload.hex}88`,
                }}
              />
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 12,
                  fontWeight: 600,
                  color: isDark ? "#ffffff" : "#0f172a",
                }}
              >
                {intent.payload.hex.toUpperCase()}
              </span>
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                onClick={() => handleCopyHex(intent.payload.hex)}
                style={{
                  padding: "4px 8px",
                  borderRadius: "6px",
                  background: isDark ? "rgba(255,255,255,0.06)" : "#e2e8f0",
                  color: isDark ? "#d4d4d8" : "#475569",
                  border: "none",
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {copiedHex ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                <span>{copiedHex ? "Copied" : "Copy"}</span>
              </button>
              <button
                type="button"
                onClick={() => onExecute(`Generate CSS theme palette matching ${intent.payload.hex}`, true)}
                style={{
                  padding: "4px 8px",
                  borderRadius: "6px",
                  background: "#8b5cf6",
                  color: "#fff",
                  border: "none",
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Create Palette
              </button>
            </div>
          </div>
        )}

        {/* SPLIT BILL */}
        {intent.type === "split" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#10b981" }}>
                ${(
                  (intent.payload.total * (1 + tipPercent / 100)) /
                  intent.payload.people
                ).toFixed(2)}{" "}
                <span style={{ fontSize: 10, fontWeight: 500, color: isDark ? "#a1a1aa" : "#64748b" }}>
                  / person (incl. {tipPercent}% tip)
                </span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              {[0, 15, 18, 20].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTipPercent(t)}
                  style={{
                    padding: "3px 6px",
                    borderRadius: "4px",
                    fontSize: 10,
                    cursor: "pointer",
                    border: "none",
                    background: tipPercent === t ? "#8b5cf6" : isDark ? "rgba(255,255,255,0.06)" : "#e2e8f0",
                    color: tipPercent === t ? "#fff" : isDark ? "#a1a1aa" : "#64748b",
                  }}
                >
                  {t}%
                </button>
              ))}
            </div>
          </div>
        )}

        {/* TIMEZONE */}
        {intent.type === "timezone" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <span style={{ fontSize: 11, color: isDark ? "#e4e4e7" : "#1e293b" }}>
              🌐 Local conversion for <strong>{intent.payload.timeStr} {intent.payload.fromZone}</strong> to <strong>{intent.payload.toZone}</strong>
            </span>
            <button
              type="button"
              onClick={() => onExecute(`Convert exact time: ${intent.rawText}`, true)}
              style={{
                padding: "4px 8px",
                borderRadius: "6px",
                background: "#8b5cf6",
                color: "#fff",
                border: "none",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Convert Live
            </button>
          </div>
        )}

        {/* DICE */}
        {intent.type === "dice" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 12, color: isDark ? "#d4d4d8" : "#334155" }}>
                Result:{" "}
                <strong style={{ fontSize: 14, color: "#a855f7" }}>
                  {diceResult !== null ? diceResult : "—"}
                </strong>
              </span>
            </div>
            <button
              type="button"
              onClick={handleRollDice}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                background: "#8b5cf6",
                color: "#fff",
                border: "none",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <Dices size={12} />
              <span>{intent.payload.isCoin ? "Flip Coin" : "Roll"}</span>
            </button>
          </div>
        )}

        {/* REMINDER */}
        {intent.type === "reminder" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <span style={{ fontSize: 11, color: isDark ? "#e4e4e7" : "#1e293b" }}>
              🔔 Reminder: <strong>{intent.payload.task}</strong>
            </span>
            <button
              type="button"
              onClick={() => onExecute(`Set reminder: ${intent.rawText}`, true)}
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                background: "#8b5cf6",
                color: "#fff",
                border: "none",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Set Reminder
            </button>
          </div>
        )}

        {/* SOCIAL REACH */}
        {intent.type === "social_reach" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <span style={{ fontSize: 11, color: isDark ? "#e4e4e7" : "#1e293b" }}>
              📡 Deep Reach on <strong>{intent.payload.platform.toUpperCase()}</strong>: "{intent.payload.query}"
            </span>
            <button
              type="button"
              onClick={() =>
                onExecute(
                  `Execute tool agent_reach with platform="${intent.payload.platform}" and query="${intent.payload.query}"`,
                  true
                )
              }
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                background: "linear-gradient(135deg, #06b6d4, #3b82f6)",
                color: "#fff",
                border: "none",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <Sparkles size={11} />
              <span>Deep Reach</span>
            </button>
          </div>
        )}

        {/* DESKTOP OPERATOR */}
        {intent.type === "desktop_operator" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: isDark ? "rgba(255,255,255,0.03)" : "#f1f5f9",
              padding: "6px 12px",
              borderRadius: "8px",
            }}
          >
            <span style={{ fontSize: 11, color: isDark ? "#e4e4e7" : "#1e293b" }}>
              ⚡ Windows Desktop:{" "}
              <strong>
                {intent.payload.app
                  ? `Launch ${intent.payload.app}`
                  : intent.payload.spotifySong
                  ? `Play "${intent.payload.spotifySong}"`
                  : `YouTube "${intent.payload.ytQuery}"`}
              </strong>
            </span>
            <button
              type="button"
              onClick={() =>
                onExecute(
                  intent.payload.app
                    ? `Execute tool computer_operator action="open_app" target="${intent.payload.app}"`
                    : intent.payload.spotifySong
                    ? `Execute tool computer_operator action="media_control" command="play" target="${intent.payload.spotifySong}"`
                    : `Execute tool computer_operator action="youtube_play" query="${intent.payload.ytQuery}"`,
                  true
                )
              }
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                background: "linear-gradient(135deg, #10b981, #059669)",
                color: "#fff",
                border: "none",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <Monitor size={11} />
              <span>Execute OS</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
