import { useEffect, useState } from "react";
import { Mic, MicOff, PhoneOff, Radio, Send, Square, Volume2, VolumeX } from "lucide-react";
import { AgentActivityFeed } from "../../features/chat/components/AgentActivityFeed";
import { useLiveCall, type LiveVoiceEngine } from "../../live/useLiveCall";

export interface LiveCallOverlayProps {
  onClose?: () => void;
  autoConnect?: boolean;
}

export function LiveCallOverlay({ onClose, autoConnect = false }: LiveCallOverlayProps) {
  const live = useLiveCall();
  const [draftUtterance, setDraftUtterance] = useState("");

  useEffect(() => {
    if (autoConnect) {
      live.connect();
    }
    return () => live.disconnect();
  }, [autoConnect]);

  // Hold Space for Push-to-Talk when focused outside text inputs
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.code === "Space" && !e.repeat) {
        e.preventDefault();
        live.setIsPushToTalkActive(true);
        live.setMicLevel(0.65);
        if (!live.micActive) {
          void live.startMic();
        }
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        live.setIsPushToTalkActive(false);
        live.setMicLevel(0.05);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [live]);

  const orbScale = 1 + Math.min(0.32, live.micLevel * 0.45);
  const voicePresets: Array<{ id: LiveVoiceEngine; label: string }> = [
    { id: "thalia", label: "Thalia (Cute Fast)" },
    { id: "ana", label: "Ana Neural (Free)" },
    { id: "luna", label: "Luna (Warm)" },
    { id: "browser", label: "Browser Voice" },
  ];

  const handleSubmitDraft = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = draftUtterance.trim();
    if (!clean) return;
    live.sendTextUtterance(clean);
    setDraftUtterance("");
  };

  return (
    <section
      data-testid="live-call-overlay"
      aria-label="Jarvis Live Voice Mode"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 24,
        padding: "20px 18px",
        borderRadius: "var(--radius-card, 16px)",
        border: "1px solid var(--border-subtle, #ebe4e9)",
        background: "var(--bg-elevated, var(--ds-surface))",
        color: "var(--text-primary, var(--ds-text))",
        minHeight: 360,
        boxSizing: "border-box",
      }}
    >
      <header
        style={{
          width: "100%",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
        }}
      >
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 600 }}>
          <Radio size={14} style={{ color: "var(--accent-primary, var(--ds-accent))" }} />
          <span>Hinaa Live Voice</span>
          <span
            data-testid="live-state-pill"
            style={{
              padding: "2px 8px",
              borderRadius: "var(--radius-pill, 9999px)",
              border: "1px solid var(--border-subtle, #ebe4e9)",
              color: "var(--text-muted, var(--ds-text-muted))",
              fontSize: 10,
            }}
          >
            {live.callState}
          </span>
        </div>

        <div
          data-testid="live-latency-hud"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            fontSize: 11,
            color: "var(--text-muted, var(--ds-text-muted))",
            fontFamily: "var(--font-mono, monospace)",
          }}
        >
          <span>ASR {live.latency.asrMs != null ? `${live.latency.asrMs}ms` : "—"}</span>
          <span>Total {live.latency.totalMs != null ? `${live.latency.totalMs}ms` : "—"}</span>
          {onClose && (
            <button
              type="button"
              aria-label="Close live voice"
              onClick={() => {
                live.disconnect();
                onClose();
              }}
              style={{
                padding: "5px 10px",
                borderRadius: 8,
                border: "1px solid var(--border-strong, #c5b7c1)",
                color: "var(--text-secondary)",
                background: "transparent",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              Exit
            </button>
          )}
        </div>
      </header>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, textAlign: "center", maxWidth: 480 }}>
        <div
          data-testid="live-breathing-orb"
          aria-hidden="true"
          style={{
            width: 112,
            height: 112,
            borderRadius: "9999px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "transform 150ms ease",
            transform: `scale(${orbScale})`,
            background: "radial-gradient(circle, var(--accent-primary, #bd406f) 0%, var(--accent-secondary, #7c6bc4) 75%)",
            boxShadow: "0 0 36px var(--accent-glow, rgba(189,64,111,0.35))",
          }}
        >
          <Volume2 size={32} color="#ffffff" />
        </div>

        <div style={{ minHeight: 48, fontSize: 14 }} aria-live="polite">
          {live.partialCaption ? (
            <p style={{ fontStyle: "italic", color: "var(--text-muted)", margin: 0 }}>{live.partialCaption}</p>
          ) : live.finalCaption ? (
            <p style={{ fontWeight: 500, margin: 0 }}>{live.finalCaption}</p>
          ) : (
            <p style={{ color: "var(--text-muted)", margin: 0 }}>
              Hold <kbd>Space</kbd> to talk or connect full-duplex stream.
            </p>
          )}
          {live.assistantReply && (
            <p style={{ marginTop: 6, marginBottom: 0, fontSize: 12, color: "var(--text-secondary)" }}>
              {live.assistantReply}
            </p>
          )}
          {live.error && (
            <p role="alert" style={{ marginTop: 6, marginBottom: 0, fontSize: 12, color: "var(--status-err)" }}>
              {live.error}
            </p>
          )}
        </div>
      </div>

      <div
        data-testid="live-voice-presets"
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
        }}
      >
        {voicePresets.map((preset) => {
          const active = live.voiceEngine === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              data-testid={`live-voice-preset-${preset.id}`}
              onClick={() => live.setVoiceEngine(preset.id)}
              style={{
                padding: "4px 10px",
                borderRadius: "var(--radius-pill, 9999px)",
                border: `1px solid ${active ? "var(--accent-primary, #bd406f)" : "var(--border-subtle, #ebe4e9)"}`,
                background: active ? "var(--accent-primary, #bd406f)" : "transparent",
                color: active ? "#ffffff" : "var(--text-secondary)",
                fontSize: 11,
                fontWeight: active ? 600 : 500,
                cursor: "pointer",
              }}
            >
              {preset.label}
            </button>
          );
        })}
        {live.lastAudioProvider && (
          <span
            data-testid="live-audio-provider-badge"
            style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: 4 }}
          >
            {live.lastAudioProvider}
          </span>
        )}
      </div>

      {live.steps.length > 0 && (
        <div style={{ width: "100%", maxWidth: 560 }}>
          <AgentActivityFeed steps={live.steps} variant="inline" />
        </div>
      )}

      <form
        onSubmit={handleSubmitDraft}
        style={{
          width: "100%",
          maxWidth: 520,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <input
          type="text"
          value={draftUtterance}
          onChange={(e) => setDraftUtterance(e.target.value)}
          placeholder="Say or type anything for Hina to speak back…"
          aria-label="Live call message input"
          data-testid="live-call-text-input"
          style={{
            flex: 1,
            padding: "8px 12px",
            borderRadius: "var(--radius-pill, 9999px)",
            border: "1px solid var(--border-strong, #c5b7c1)",
            background: "var(--bg-canvas, transparent)",
            color: "var(--text-primary)",
            fontSize: 13,
          }}
        />
        <button
          type="submit"
          data-testid="live-call-send-btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: "var(--radius-pill, 9999px)",
            border: "none",
            background: "var(--accent-primary, #bd406f)",
            color: "#ffffff",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <Send size={13} /> Speak
        </button>
      </form>

      <footer style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "center", gap: 10 }}>
        {live.callState === "idle" || live.callState === "error" ? (
          <button
            type="button"
            data-testid="live-start-call-btn"
            onClick={() => {
              live.connect();
              void live.startMic();
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 18px",
              borderRadius: "var(--radius-pill, 9999px)",
              border: "none",
              background: "var(--accent-primary, #bd406f)",
              color: "#ffffff",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Mic size={14} /> Start Live Call
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={() => (live.micActive ? live.stopMic() : void live.startMic())}
              onMouseDown={() => live.setIsPushToTalkActive(true)}
              onMouseUp={() => live.setIsPushToTalkActive(false)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "9px 16px",
                borderRadius: "var(--radius-pill, 9999px)",
                border: `1px solid ${live.micActive || live.isPushToTalkActive ? "var(--accent-primary, #bd406f)" : "var(--border-strong, #c5b7c1)"}`,
                background: live.micActive ? "rgba(189, 64, 111, 0.14)" : "transparent",
                color: "var(--text-primary)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {live.micActive ? <Mic size={14} /> : <MicOff size={14} />}
              {live.micActive ? "Mic Live (Click Mute)" : "Enable Mic"}
            </button>
            <button
              type="button"
              onClick={() => live.setAudioMuted(!live.audioMuted)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "9px 14px",
                borderRadius: "var(--radius-pill, 9999px)",
                border: "1px solid var(--border-strong, #c5b7c1)",
                background: "transparent",
                color: "var(--text-secondary)",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              {live.audioMuted ? <VolumeX size={13} /> : <Volume2 size={13} />}
              {live.audioMuted ? "Unmute Audio" : "Audio On"}
            </button>
            <button
              type="button"
              onClick={live.bargeIn}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "9px 14px",
                borderRadius: "var(--radius-pill, 9999px)",
                border: "1px solid var(--border-strong, #c5b7c1)",
                background: "transparent",
                color: "var(--text-secondary)",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              <Square size={12} /> Interrupt
            </button>
            <button
              type="button"
              onClick={live.disconnect}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "9px 14px",
                borderRadius: "var(--radius-pill, 9999px)",
                border: "none",
                background: "var(--status-err, #c4384a)",
                color: "#ffffff",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <PhoneOff size={13} /> End
            </button>
          </>
        )}
      </footer>
    </section>
  );
}
