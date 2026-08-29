import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, AlertTriangle, CheckCircle, Clock, Mic, Radio, Brain, Volume2, Activity } from "lucide-react";

export interface VoicePipelineStage {
  id: string;
  label: string;
  status: "pending" | "active" | "success" | "error" | "skipped";
  detail?: string;
  timestamp?: number;
}

export interface VoiceDiagnosticsData {
  // Microphone
  micPermission: "unknown" | "granted" | "denied";
  trackState: "unknown" | "live" | "ended" | "muted";
  audioContextState: "unknown" | "running" | "suspended" | "closed" | "interrupted";
  inputSampleRate: number;
  rmsLevel: number;
  chunksSentPerSecond: number;
  
  // STT
  sttSocketState: "unknown" | "connecting" | "open" | "closed";
  lastPartialTranscript: string;
  lastCommittedTranscript: string;
  sttLatencyMs: number;
  
  // Brain
  brainProvider: string;
  firstTokenReceived: boolean;
  brainLatencyMs: number;
  
  // TTS
  ttsProvider: string;
  ttsSocketState: "unknown" | "connecting" | "open" | "closed";
  audioChunksReceived: number;
  
  // Playback
  playbackState: "idle" | "playing" | "error";
  
  // Voice Route (exact providers in use)
  voiceRoute: {
    sttProvider: string;
    sttTransport: string;
    brainProvider: string;
    brainModel: string;
    ttsProvider: string;
    ttsTransport: string;
    ttsVoiceId: string; // redacted
    ttsFallbackReason?: string;
  };
  
  // Pipeline
  currentStage: string;
  lastError: string;
  turnCount: number;
  activeTurnId: string;
}

interface VoiceDiagnosticsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  data: VoiceDiagnosticsData;
  onManualCommit?: () => void;
  isListening: boolean;
}

const STAGE_ORDER = [
  { id: "mic", label: "Microphone", icon: Mic },
  { id: "stt-connect", label: "STT Connection", icon: Radio },
  { id: "stt-transcribe", label: "Transcription", icon: Radio },
  { id: "brain", label: "Brain (LLM)", icon: Brain },
  { id: "tts", label: "Text-to-Speech", icon: Volume2 },
  { id: "playback", label: "Playback", icon: Activity },
];

function StatusDot({ status }: { status: "pending" | "active" | "success" | "error" | "skipped" }) {
  const colors = {
    pending: "var(--text-disabled)",
    active: "var(--accent)",
    success: "var(--success-text)",
    error: "var(--danger-text)",
    skipped: "var(--text-tertiary)",
  };
  return (
    <div
      style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: colors[status],
        flexShrink: 0,
        boxShadow: status === "active" ? `0 0 6px ${colors[status]}` : undefined,
      }}
    />
  );
}

function DiagRow({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid var(--border-subtle)" }}>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>{label}</span>
      <span style={{ fontSize: "var(--text-xs)", color: warn ? "var(--danger-text)" : "var(--text-primary)", fontFamily: "monospace" }}>{value}</span>
    </div>
  );
}

export function VoiceDiagnosticsDrawer({ isOpen, onClose, data, onManualCommit, isListening }: VoiceDiagnosticsDrawerProps) {
  if (!isOpen) return null;

  const stages: VoicePipelineStage[] = [
    {
      id: "mic",
      label: "Microphone",
      status: data.micPermission === "granted" && data.trackState === "live" ? "success"
        : data.micPermission === "denied" ? "error"
        : data.micPermission === "granted" ? "active" : "pending",
      detail: data.micPermission === "granted" ? `Track: ${data.trackState} · RMS: ${data.rmsLevel.toFixed(3)}` : data.micPermission === "denied" ? "Permission denied" : "Not started",
    },
    {
      id: "stt-connect",
      label: "STT Socket",
      status: data.sttSocketState === "open" ? "success"
        : data.sttSocketState === "connecting" ? "active"
        : data.sttSocketState === "closed" ? "error" : "pending",
      detail: data.sttSocketState === "open" ? "Connected" : data.sttSocketState,
    },
    {
      id: "stt-transcribe",
      label: "Transcription",
      status: data.lastCommittedTranscript ? "success"
        : data.lastPartialTranscript ? "active"
        : data.sttSocketState === "open" ? "active" : "pending",
      detail: data.lastCommittedTranscript ? `"${data.lastCommittedTranscript.slice(0, 60)}${data.lastCommittedTranscript.length > 60 ? "…" : ""}"` 
        : data.lastPartialTranscript ? `Partial: "${data.lastPartialTranscript.slice(0, 60)}…"` 
        : "Waiting for speech",
    },
    {
      id: "brain",
      label: "Brain (LLM)",
      status: data.firstTokenReceived ? "success"
        : data.currentStage === "thinking" ? "active"
        : data.currentStage === "error" ? "error" : "pending",
      detail: data.brainProvider ? `${data.brainProvider}${data.brainLatencyMs ? ` · ${data.brainLatencyMs}ms` : ""}` : "Not started",
    },
    {
      id: "tts",
      label: "TTS",
      status: data.audioChunksReceived > 0 ? "success"
        : data.currentStage === "speaking" ? "active"
        : data.ttsSocketState === "open" ? "active" : "pending",
      detail: data.ttsProvider ? `${data.ttsProvider} · ${data.audioChunksReceived} chunks` : "Not started",
    },
    {
      id: "playback",
      label: "Playback",
      status: data.playbackState === "playing" ? "active"
        : data.playbackState === "error" ? "error" : "pending",
      detail: data.playbackState,
    },
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 25, stiffness: 200 }}
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            width: 380,
            maxWidth: "90vw",
            background: "var(--bg-surface)",
            borderLeft: "1px solid var(--border-default)",
            boxShadow: "var(--shadow-lg)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
            <h3 style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>Voice Diagnostics</h3>
            <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-tertiary)", padding: 4 }}>
              <X size={16} />
            </button>
          </div>

          {/* Pipeline Stages */}
          <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Pipeline
            </div>
            {stages.map((stage) => {
              const Icon = STAGE_ORDER.find((s) => s.id === stage.id)?.icon || Activity;
              return (
                <div key={stage.id} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", padding: "6px 0" }}>
                  <StatusDot status={stage.status} />
                  <Icon size={14} style={{ color: "var(--text-tertiary)", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "var(--text-xs)", fontWeight: 500, color: "var(--text-primary)" }}>{stage.label}</div>
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{stage.detail}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Microphone Details */}
          <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Microphone
            </div>
            <DiagRow label="Permission" value={data.micPermission} warn={data.micPermission === "denied"} />
            <DiagRow label="Track state" value={data.trackState} warn={data.trackState !== "live"} />
            <DiagRow label="AudioContext" value={data.audioContextState} warn={data.audioContextState !== "running"} />
            <DiagRow label="Sample rate" value={`${data.inputSampleRate} Hz`} />
            <DiagRow label="RMS level" value={data.rmsLevel.toFixed(4)} />
            <DiagRow label="Chunks/sec" value={`${data.chunksSentPerSecond}`} />
          </div>

          {/* Transcript */}
          <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Transcript
            </div>
            <DiagRow label="Partial" value={data.lastPartialTranscript || "—"} />
            <DiagRow label="Committed" value={data.lastCommittedTranscript || "—"} />
            <DiagRow label="STT latency" value={data.sttLatencyMs > 0 ? `${data.sttLatencyMs}ms` : "—"} />
          </div>

          {/* Brain & TTS */}
          <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Brain & TTS
            </div>
            <DiagRow label="Provider" value={data.brainProvider || "—"} />
            <DiagRow label="First token" value={data.firstTokenReceived ? "Received" : "Pending"} />
            <DiagRow label="Brain latency" value={data.brainLatencyMs > 0 ? `${data.brainLatencyMs}ms` : "—"} />
            <DiagRow label="TTS provider" value={data.ttsProvider || "—"} />
            <DiagRow label="Audio chunks" value={`${data.audioChunksReceived}`} />
            <DiagRow label="Playback" value={data.playbackState} />
          </div>

          {/* Voice Route */}
          <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Voice Route
            </div>
            <DiagRow label="STT" value={`${data.voiceRoute.sttProvider} · ${data.voiceRoute.sttTransport}`} />
            <DiagRow label="Brain" value={`${data.voiceRoute.brainProvider} · ${data.voiceRoute.brainModel}`} />
            <DiagRow label="TTS" value={`${data.voiceRoute.ttsProvider} · ${data.voiceRoute.ttsTransport}`} />
            <DiagRow label="Voice ID" value={data.voiceRoute.ttsVoiceId} />
            {data.voiceRoute.ttsFallbackReason && (
              <DiagRow label="Fallback" value={data.voiceRoute.ttsFallbackReason} warn />
            )}
          </div>

          {/* Actions */}
          <div style={{ padding: "var(--space-3) var(--space-4)", display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            {isListening && onManualCommit && (
              <button
                onClick={onManualCommit}
                style={{
                  padding: "var(--space-2) var(--space-3)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--accent)",
                  background: "var(--accent-pale)",
                  color: "var(--accent)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Manual Commit
              </button>
            )}
            <div style={{ fontSize: "11px", color: "var(--text-tertiary)", padding: "var(--space-2) 0" }}>
              Turns: {data.turnCount} · Stage: {data.currentStage}
              {data.lastError && (
                <span style={{ color: "var(--danger-text)", display: "block", marginTop: 4 }}>
                  <AlertTriangle size={12} style={{ verticalAlign: -2 }} /> {data.lastError}
                </span>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
