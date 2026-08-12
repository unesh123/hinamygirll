import type { VSeeFaceState } from "../../features/audio/useVSeeFace";

type Props = {
  tracker: VSeeFaceState;
  selectedModelLabel: string;
  selectedModelMode: "autonomous" | "exact-vseeface" | "tracking-proxy";
  onClose: () => void;
  onOpenAvatarLab: () => void;
};

const STATE_COPY = {
  disabled: { label: "Disconnected", color: "#94a3b8", detail: "Tracking is disabled in this browser." },
  disconnected: { label: "Disconnected", color: "#94a3b8", detail: "Connect HINAA to its local VMC bridge, then start VSeeFace sending." },
  connecting: { label: "Starting receiver", color: "#fde68a", detail: "Opening one browser connection to HINAA’s local VMC bridge." },
  listening: { label: "VMC Listening", color: "#93c5fd", detail: "The receiver is bound, but no recent VSeeFace tracking packet has arrived." },
  live: { label: "VSeeFace Live", color: "#86efac", detail: "Fresh external packets are driving facial expression and calibrated head motion. HINAA keeps her shoulders, arms, hands, and body in a protected relaxed pose." },
  stale: { label: "Tracking Stale", color: "#fdba74", detail: "Packets arrived previously but are no longer fresh. HINAA is fading to a neutral autonomous presence." },
  test: { label: "Test Signal", color: "#c4b5fd", detail: "A HINAA diagnostic fixture is active. This is not camera tracking and never appears as LIVE." },
  error: { label: "Error", color: "#fda4af", detail: "The local VMC bridge is unavailable. Chat and voice remain usable." },
} as const;

function timeSince(timestamp: string | null): string {
  if (!timestamp) return "No valid packet yet";
  const ms = Date.now() - Date.parse(timestamp);
  if (!Number.isFinite(ms) || ms < 0) return "Just now";
  return `${Math.max(0, Math.round(ms / 100) / 10)} s ago`;
}

export function VmcControlPanel({ tracker, selectedModelLabel, selectedModelMode, onClose, onOpenAvatarLab }: Props) {
  const copy = STATE_COPY[tracker.status];
  const diagnostics = tracker.diagnostics;
  const live = tracker.status === "live";
  const connected = tracker.status !== "disconnected" && tracker.status !== "error";

  return (
    <section role="dialog" aria-modal="false" aria-label="VSeeFace and VMC connection panel" style={styles.panel}>
      <header style={styles.header}>
        <div>
          <p style={styles.eyebrow}>LOCAL PRESENCE</p>
          <h2 style={styles.title}>VSeeFace and VMC</h2>
        </div>
        <button type="button" onClick={onClose} style={styles.close} aria-label="Close VSeeFace and VMC panel">Close</button>
      </header>

      <div style={{ ...styles.state, borderColor: copy.color, color: copy.color }} aria-live="polite">
        <span style={{ ...styles.dot, background: copy.color }} />
        <strong>{copy.label}</strong>
      </div>
      <p style={styles.detail}>{tracker.error || copy.detail}</p>

      <div style={styles.grid}>
        <Metric label="Receiver" value={diagnostics?.listening ? "Listening" : "Not bound"} />
        <Metric label="Host / port" value={`${diagnostics?.host ?? "127.0.0.1"}:${diagnostics?.port ?? 39539}`} />
        <Metric label="Last packet" value={timeSince(diagnostics?.lastPacketTimestamp ?? null)} />
        <Metric label="Packet rate" value={`${diagnostics?.packetRate ?? 0} packets/s`} />
        <Metric label="Model mode" value={selectedModelMode.replaceAll("-", " ")} />
        <Metric label="Calibration" value={tracker.calibration ? "Neutral captured" : "Not calibrated"} />
      </div>

      <div style={styles.box}>
        <strong style={styles.boxTitle}>Detected channels</strong>
        <p style={styles.channels}>{diagnostics?.detectedChannels.length ? diagnostics.detectedChannels.join(" · ") : "No supported VMC channels have been observed yet."}</p>
      </div>
      <div style={styles.box}>
        <strong style={styles.boxTitle}>Selected browser model</strong>
        <p style={styles.channels}>{selectedModelLabel}. HINAA owns speech mouth movement while she talks. Fresh VMC controls facial expression and a bounded calibrated head response; her body, shoulders, arms, and hands stay locked to the relaxed companion pose so a sender cannot force a T-pose.</p>
      </div>

      <div style={styles.actions}>
        <button type="button" onClick={tracker.connect} disabled={connected} style={styles.primary}>Connect / listen</button>
        <button type="button" onClick={tracker.disconnect} disabled={!connected} style={styles.secondary}>Disconnect</button>
        <button type="button" onClick={tracker.reconnect} style={styles.secondary}>Reconnect</button>
        <button type="button" onClick={() => { void tracker.testSignal(); }} style={styles.secondary}>Test signal</button>
        <button type="button" onClick={tracker.calibrate} disabled={!live} style={styles.secondary}>Calibrate neutral</button>
        {tracker.calibration && <button type="button" onClick={tracker.resetCalibration} style={styles.secondary}>Reset calibration</button>}
        <button type="button" onClick={onOpenAvatarLab} style={styles.secondary}>Open Avatar Lab</button>
      </div>

      <aside style={styles.setup}>
        <strong>Windows VSeeFace setup</strong>
        <ol style={{ margin: "6px 0 0", paddingLeft: 18 }}>
          <li>Open VSeeFace and load an actual VRM 0.x model you are licensed to use.</li>
          <li>Enable VMC Protocol sending to <code>127.0.0.1:39539</code>.</li>
          <li>Select Connect / listen here. The badge changes to VSeeFace Live only after fresh external packets arrive.</li>
        </ol>
      </aside>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div style={styles.metric}><span>{label}</span><strong>{value}</strong></div>;
}

const styles: Record<string, React.CSSProperties> = {
  panel: { padding: 18, color: "#e2e8f0", background: "linear-gradient(160deg, #0f172a, #18243c)", minHeight: "100%", overflowY: "auto" },
  header: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 },
  eyebrow: { margin: 0, color: "#5eead4", fontSize: 11, fontWeight: 800, letterSpacing: "0.12em" },
  title: { margin: "5px 0 0", fontSize: 22 },
  close: { border: "1px solid rgba(226,232,240,.25)", borderRadius: 8, padding: "6px 9px", color: "#e2e8f0", background: "rgba(15,23,42,.55)" },
  state: { display: "flex", alignItems: "center", gap: 8, border: "1px solid", borderRadius: 10, padding: "9px 10px", marginTop: 16, background: "rgba(15,23,42,.45)" },
  dot: { width: 8, height: 8, borderRadius: "50%", boxShadow: "0 0 12px currentColor" },
  detail: { color: "#cbd5e1", fontSize: 13, lineHeight: 1.5, margin: "10px 0 14px" },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 8 },
  metric: { display: "grid", gap: 3, border: "1px solid rgba(148,163,184,.18)", borderRadius: 9, padding: 10, background: "rgba(15,23,42,.48)", fontSize: 11, color: "#94a3b8" },
  box: { marginTop: 10, border: "1px solid rgba(148,163,184,.18)", borderRadius: 9, padding: 10, background: "rgba(15,23,42,.32)" },
  boxTitle: { fontSize: 12, color: "#e2e8f0" },
  channels: { margin: "5px 0 0", color: "#cbd5e1", fontSize: 12, lineHeight: 1.45 },
  actions: { display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 },
  primary: { border: 0, borderRadius: 8, padding: "8px 10px", background: "#14b8a6", color: "#052e2b", fontWeight: 800 },
  secondary: { border: "1px solid rgba(148,163,184,.28)", borderRadius: 8, padding: "8px 10px", background: "rgba(15,23,42,.55)", color: "#e2e8f0" },
  setup: { marginTop: 16, padding: 11, borderRadius: 9, color: "#cbd5e1", background: "rgba(20,184,166,.08)", border: "1px solid rgba(45,212,191,.18)", fontSize: 12, lineHeight: 1.45 },
};
