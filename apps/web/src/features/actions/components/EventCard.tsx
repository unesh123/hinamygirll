import React, { useState } from "react";
import { Calendar, Clock, MapPin, User, Check, Plus } from "lucide-react";
import type { EventFields } from "../types";

interface EventCardProps {
  data: EventFields;
  onCommit?: (updated: EventFields) => void;
  compact?: boolean;
}

export function EventCard({ data, onCommit, compact = false }: EventCardProps) {
  const [title, setTitle] = useState(data.title);
  const [dateStr, setDateStr] = useState(data.dateStr);
  const [timeStr, setTimeStr] = useState(data.timeStr);
  const [participant, setParticipant] = useState(data.participant || "");
  const [location, setLocation] = useState(data.location || "");
  const [isEditingLoc, setIsEditingLoc] = useState(false);

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
              background: "rgba(59, 130, 246, 0.15)",
              color: "#3b82f6",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Calendar size={16} />
          </div>
          <span style={{ fontSize: "0.85rem", fontWeight: 700 }}>New Event</span>
        </div>
        <span
          style={{
            fontSize: "0.72rem",
            padding: "2px 8px",
            borderRadius: 4,
            background: "rgba(59, 130, 246, 0.12)",
            color: "#60a5fa",
            fontWeight: 600,
          }}
        >
          Calendar
        </span>
      </div>

      {/* Main Title */}
      <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.01em" }}>
        {title}
      </div>

      {/* Details Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: compact ? "1fr" : "1fr 1fr",
          gap: "8px",
        }}
      >
        {/* Date & Time */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.05)",
            fontSize: "0.82rem",
            color: "rgba(255,255,255,0.9)",
          }}
        >
          <Clock size={14} color="#60a5fa" />
          <span>
            {dateStr} · {timeStr}
          </span>
        </div>

        {/* Participant */}
        {participant ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              borderRadius: 8,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.05)",
              fontSize: "0.82rem",
              color: "rgba(255,255,255,0.9)",
            }}
          >
            <User size={14} color="#a78bfa" />
            <span>{participant}</span>
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 12px",
              borderRadius: 8,
              background: "rgba(255,255,255,0.02)",
              border: "1px dashed rgba(255,255,255,0.1)",
              fontSize: "0.78rem",
              color: "rgba(255,255,255,0.4)",
              cursor: "pointer",
            }}
          >
            <Plus size={13} />
            <span>Add guest</span>
          </div>
        )}

        {/* Location */}
        <div
          style={{
            gridColumn: compact ? "span 1" : "span 2",
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 12px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.05)",
            fontSize: "0.82rem",
            color: location ? "rgba(255,255,255,0.9)" : "rgba(255,255,255,0.4)",
          }}
        >
          <MapPin size={14} color="#f472b6" />
          {isEditingLoc ? (
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              onBlur={() => setIsEditingLoc(false)}
              onKeyDown={(e) => e.key === "Enter" && setIsEditingLoc(false)}
              placeholder="Enter location"
              autoFocus
              style={{
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#ffffff",
                fontSize: "0.82rem",
                width: "100%",
              }}
            />
          ) : (
            <span
              onClick={() => setIsEditingLoc(true)}
              style={{ cursor: "pointer", flex: 1 }}
            >
              {location || "+ Add place"}
            </span>
          )}
        </div>
      </div>

      {/* Commit button */}
      {onCommit && (
        <button
          type="button"
          onClick={() =>
            onCommit({
              title,
              dateStr,
              timeStr,
              participant: participant || undefined,
              location: location || undefined,
            })
          }
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "9px 14px",
            borderRadius: 8,
            background: "#3b82f6",
            color: "#ffffff",
            border: "none",
            fontWeight: 700,
            fontSize: "0.82rem",
            cursor: "pointer",
            marginTop: 4,
          }}
        >
          <Check size={14} />
          <span>Add Event ↵</span>
        </button>
      )}
    </div>
  );
}
