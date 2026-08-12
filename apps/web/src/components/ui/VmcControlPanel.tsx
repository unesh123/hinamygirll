import type { VSeeFaceState } from "../../features/audio/useVSeeFace";

type Props = {
  tracker: VSeeFaceState;
  selectedModelLabel: string;
  selectedModelMode: "autonomous" | "exact-vseeface" | "tracking-proxy";
  onClose: () => void;
  onOpenAvatarLab: () => void;
};

const STATE_COPY = {
  disabled: { label: "Disconnected", tone: "neutral", detail: "Tracking is disabled in this browser." },
  disconnected: { label: "Disconnected", tone: "neutral", detail: "Start HINAA’s local receiver, then let VSeeFace send to it." },
  connecting: { label: "Connecting HINAA", tone: "waiting", detail: "Opening HINAA’s one local browser connection." },
  listening: { label: "Waiting for VSeeFace", tone: "waiting", detail: "HINAA is ready. No recent VSeeFace tracking packet has arrived yet." },
  live: { label: "VSeeFace Live", tone: "live", detail: "Fresh external packets are driving HINAA’s face and calibrated head movement. Her relaxed companion pose remains protected." },
  stale: { label: "Tracking paused", tone: "warning", detail: "Packets stopped arriving, so HINAA is returning gently to her autonomous presence." },
  test: { label: "Diagnostic signal", tone: "test", detail: "This is a HINAA test signal, not camera tracking." },
  error: { label: "Connection needs attention", tone: "error", detail: "The local VMC bridge is unavailable. HINAA’s chat and voice still work." },
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
  const facialReady = live && tracker.hasFacialSignal;
  const connected = tracker.status !== "disconnected" && tracker.status !== "error";
  const stateDetail = live && !facialReady
    ? "Fresh motion packets are arriving, but no supported VSeeFace blendshape channel has been detected yet. HINAA keeps her autonomous expression layer until one arrives."
    : (tracker.error || copy.detail);
  const primaryLabel = !connected ? "Start VSeeFace connection" : !live ? "Waiting for VSeeFace" : !tracker.calibration ? "Calibrate neutral" : "Tracking ready";
  const primaryAction = !connected ? tracker.connect : live && !tracker.calibration ? tracker.calibrate : undefined;

  return (
    <section role="dialog" aria-modal="false" aria-label="VSeeFace and VMC connection panel" className="vmc-panel">
      <header className="vmc-panel__header">
        <div>
          <p className="vmc-panel__eyebrow">HINAA MOTION LINK</p>
          <h2>Connect VSeeFace</h2>
          <p>Keep HINAA close, expressive, and comfortably framed while her body stays in the relaxed companion pose.</p>
        </div>
        <button type="button" onClick={onClose} className="vmc-panel__icon-button" aria-label="Close VSeeFace and VMC panel">×</button>
      </header>

      <div className={`vmc-panel__state vmc-panel__state--${copy.tone}`} aria-live="polite">
        <span className="vmc-panel__state-dot" aria-hidden="true" />
        <div><strong>{copy.label}</strong><small>{stateDetail}</small></div>
      </div>

      <ol className="vmc-panel__steps" aria-label="VSeeFace connection readiness">
        <li className={connected ? "is-complete" : "is-current"}>
          <span>1</span><div><strong>Connect HINAA</strong><small>{connected ? "Local receiver ready" : "Use the button below"}</small></div>
        </li>
        <li className={live ? "is-complete" : connected ? "is-current" : ""}>
          <span>2</span><div><strong>Start sending in VSeeFace</strong><small>{live ? `${diagnostics?.packetRate ?? 0} packets/s from VSeeFace` : "Send VMC to 127.0.0.1:39539"}</small></div>
        </li>
        <li className={tracker.calibration ? "is-complete" : live ? "is-current" : ""}>
          <span>3</span><div><strong>Capture neutral</strong><small>{tracker.calibration ? "HINAA is calibrated" : "Sit naturally, then calibrate once"}</small></div>
        </li>
      </ol>

      <div className="vmc-panel__primary-action">
        <button type="button" onClick={primaryAction} disabled={!primaryAction} className="vmc-panel__primary">{primaryLabel}</button>
        {connected && <button type="button" onClick={tracker.disconnect} className="vmc-panel__quiet">Disconnect</button>}
      </div>

      <div className="vmc-panel__model-note">
        <strong>{selectedModelLabel}</strong>
        <span>{facialReady ? "Face blendshapes detected" : live ? "Facial signal pending" : "HINAA owns speech mouth movement while she talks"}</span>
      </div>

      <details className="vmc-panel__details">
        <summary>Connection details</summary>
        <div className="vmc-panel__metrics">
          <Metric label="Receiver" value={diagnostics?.listening ? "Listening" : "Not bound"} />
          <Metric label="Last packet" value={timeSince(diagnostics?.lastPacketTimestamp ?? null)} />
          <Metric label="Face signal" value={facialReady ? "Blendshapes detected" : live ? "Waiting for blendshapes" : "Not active"} />
          <Metric label="Model mode" value={selectedModelMode.replaceAll("-", " ")} />
        </div>
        <p className="vmc-panel__technical-copy"><code>{`${diagnostics?.host ?? "127.0.0.1"}:${diagnostics?.port ?? 39539}`}</code> · {diagnostics?.packetRate ?? 0} packets/s · {diagnostics?.detectedChannels.length ? diagnostics.detectedChannels.join(" · ") : "No supported VMC channels observed"}</p>
        <div className="vmc-panel__secondary-actions">
          <button type="button" onClick={tracker.reconnect}>Reconnect</button>
          <button type="button" onClick={() => { void tracker.testSignal(); }}>Test signal</button>
          {tracker.calibration && <button type="button" onClick={tracker.resetCalibration}>Reset calibration</button>}
          <button type="button" onClick={onOpenAvatarLab}>Open Avatar Lab</button>
        </div>
      </details>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="vmc-panel__metric"><span>{label}</span><strong>{value}</strong></div>;
}
