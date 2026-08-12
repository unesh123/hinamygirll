import { useCallback, useEffect, useRef, useState } from "react";
import type { PresenceMode } from "./AvatarPresence";
import type { VSeeFaceState } from "../../features/audio/useVSeeFace";

type AvatarAsset = {
  assetId: string;
  displayName: string;
  format: string;
  source: "bundled" | "managed";
  browserUrl: string | null;
  vrmVersion: "0.x" | "1.0" | "unknown";
  fileSize: number;
  humanoidPresent: boolean;
  humanoidBones: string[];
  presetExpressions: string[];
  customExpressions: string[];
  mouthExpressions: string[];
  blinkExpressions: string[];
  lookExpressions: string[];
  springBonesPresent: boolean;
  licenseMetadataPresent: boolean;
  licenseSummary: string;
  browserLoadStatus: string;
  vseeFaceCompatibility: "compatible_candidate" | "incompatible" | "unknown";
  reason: string;
};

type Props = {
  tracker: VSeeFaceState;
  selectedModelUrl: string;
  mode: PresenceMode;
  onModeChange: (mode: PresenceMode) => void;
  onSelectModel: (url: string) => void;
  trackingMode: "autonomous" | "exact-vseeface" | "tracking-proxy";
  onTrackingModeChange: (mode: "autonomous" | "exact-vseeface" | "tracking-proxy") => void;
  onClose: () => void;
};

function compatibilityLabel(asset: AvatarAsset): string {
  if (asset.vseeFaceCompatibility === "compatible_candidate") return "VSeeFace compatible candidate";
  if (asset.vrmVersion === "1.0") return "VSeeFace incompatible · browser candidate";
  return "Compatibility unknown";
}

export function AvatarLab({ tracker, selectedModelUrl, mode, onModeChange, onSelectModel, trackingMode, onTrackingModeChange, onClose }: Props) {
  const [assets, setAssets] = useState<AvatarAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("Inspecting approved local avatar roots…");
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/v1/avatar-assets");
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || "HINAA could not inspect avatar assets.");
      setAssets(Array.isArray(body.assets) ? body.assets : []);
      setMessage(body.assets?.length ? "Approved local asset inventory is current." : "No approved local avatar assets were found in this runtime.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "HINAA could not inspect avatar assets.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const importFile = async (file: File) => {
    setMessage(`Validating ${file.name} locally…`);
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const response = await fetch("/api/v1/avatar-assets/import", { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || "HINAA could not import that avatar asset.");
      setMessage(`${body.asset.displayName} was copied into HINAA-managed local avatar storage.`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "HINAA could not import that avatar asset.");
    }
  };

  const remove = async (asset: AvatarAsset) => {
    if (asset.source !== "managed") return;
    if (!window.confirm(`Delete HINAA-managed copy of ${asset.displayName}? The original selected file is not changed.`)) return;
    try {
      const response = await fetch(`/api/v1/avatar-assets/${encodeURIComponent(asset.assetId)}?confirm=true`, { method: "DELETE" });
      const body = await response.json();
      if (!response.ok || !body.deleted) throw new Error(body?.detail || "HINAA could not delete that managed copy.");
      setMessage(`Deleted HINAA-managed copy of ${asset.displayName}.`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "HINAA could not delete that managed copy.");
    }
  };

  const selected = assets.find((asset) => asset.browserUrl === selectedModelUrl);
  const labels: Partial<Record<PresenceMode, string>> = { closeup: "Close-up", portrait: "Portrait", upperbody: "Upper body", full: "Full body" };

  return (
    <section role="dialog" aria-modal="false" aria-label="Avatar Lab" style={styles.panel}>
      <header style={styles.header}>
        <div><p style={styles.eyebrow}>LOCAL AVATAR LAB</p><h2 style={styles.title}>Model, camera, expression, and VMC diagnostics</h2></div>
        <div style={{ display: "flex", gap: 8 }}><button type="button" onClick={() => void refresh()} style={styles.secondary}>Refresh inventory</button><button type="button" onClick={onClose} style={styles.secondary}>Close</button></div>
      </header>
      <p role="status" style={styles.status}>{message}</p>

      <section style={styles.card}>
        <h3 style={styles.cardTitle}>Camera</h3>
        <p style={styles.copy}>Portrait is HINAA’s conversational default. Full body remains available for model calibration; it is not selected as a live-companion fallback.</p>
        <div style={styles.actions}>{(Object.entries(labels) as Array<[PresenceMode, string]>).map(([value, label]) => <button key={value} type="button" onClick={() => onModeChange(value)} aria-pressed={mode === value} style={mode === value ? styles.primary : styles.secondary}>{label}</button>)}</div>
      </section>

      <section style={styles.card}>
        <h3 style={styles.cardTitle}>Approved avatar assets</h3>
        <p style={styles.copy}>An import uses the browser file picker, validates parseable VRM metadata, copies only the approved selected file into HINAA-managed local storage, and never uploads it to a cloud service.</p>
        <input ref={inputRef} type="file" accept=".vrm,.glb,.gltf" style={{ display: "none" }} onChange={(event) => { const file = event.target.files?.[0]; if (file) void importFile(file); event.currentTarget.value = ""; }} />
        <div style={styles.actions}><button type="button" onClick={() => inputRef.current?.click()} style={styles.primary}>Import approved local VRM</button></div>
        {loading ? <p style={styles.copy}>Loading asset metadata…</p> : <div style={styles.assetGrid}>{assets.map((asset) => <article key={asset.assetId} style={{ ...styles.asset, borderColor: asset.browserUrl === selectedModelUrl ? "#2dd4bf" : "rgba(148,163,184,.22)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}><strong>{asset.displayName}</strong><small>{asset.vrmVersion}</small></div>
          <p style={styles.assetText}>{compatibilityLabel(asset)}</p>
          <p style={styles.assetText}>{asset.humanoidPresent ? `${asset.humanoidBones.length} humanoid bones` : "No verified humanoid rig"} · {asset.springBonesPresent ? "spring bones" : "no spring-bone metadata"}</p>
          <p style={styles.assetText}>{asset.presetExpressions.length} detected expressions · {asset.licenseMetadataPresent ? "licence metadata present" : "licence metadata absent"}</p>
          <p style={styles.assetText}>{asset.reason}</p>
          <div style={styles.actions}>{asset.browserUrl && <button type="button" onClick={() => onSelectModel(asset.browserUrl!)} style={asset.browserUrl === selectedModelUrl ? styles.primary : styles.secondary}>{asset.browserUrl === selectedModelUrl ? "Selected" : "Use in HINAA"}</button>}{asset.source === "managed" && <button type="button" onClick={() => void remove(asset)} style={styles.secondary}>Delete managed copy</button>}</div>
        </article>)}</div>}
      </section>

      <section style={styles.card}>
        <h3 style={styles.cardTitle}>Selected model inspection</h3>
        {selected ? <><p style={styles.copy}>{selected.licenseSummary}</p><p style={styles.copy}>Mouth: {selected.mouthExpressions.join(", ") || "no named mouth targets detected"}. Blink: {selected.blinkExpressions.join(", ") || "no named blink targets detected"}. Gaze: {selected.lookExpressions.join(", ") || "no named gaze targets detected"}.</p></> : <p style={styles.copy}>The current default model is bundled. Its runtime metadata will appear here when the local API can inspect the approved root.</p>}
      </section>

      <section style={styles.card}>
        <h3 style={styles.cardTitle}>Avatar strategy</h3>
        <p style={styles.copy}>Autonomous is the safe default. Exact VSeeFace Model is available only for a selected VRM 0.x compatible candidate and still requires a real VSeeFace load. Tracking Proxy is deliberately labelled as proxy and requires neutral calibration before head motion is applied.</p>
        <div style={styles.actions}>
          <button type="button" onClick={() => onTrackingModeChange("autonomous")} aria-pressed={trackingMode === "autonomous"} style={trackingMode === "autonomous" ? styles.primary : styles.secondary}>HINAA Autonomous</button>
          <button type="button" onClick={() => onTrackingModeChange("exact-vseeface")} disabled={selected?.vseeFaceCompatibility !== "compatible_candidate"} aria-pressed={trackingMode === "exact-vseeface"} style={trackingMode === "exact-vseeface" ? styles.primary : styles.secondary}>Exact VSeeFace Model</button>
          <button type="button" onClick={() => onTrackingModeChange("tracking-proxy")} aria-pressed={trackingMode === "tracking-proxy"} style={trackingMode === "tracking-proxy" ? styles.primary : styles.secondary}>VSeeFace Tracking Proxy</button>
        </div>
        {trackingMode === "tracking-proxy" && <p style={styles.copy}>Proxy mode is not exact-model tracking. HINAA keeps uncalibrated body and limb channels disabled and requires a fresh neutral calibration for head motion.</p>}
      </section>

      <section style={styles.card}>
        <h3 style={styles.cardTitle}>Pose, facial ownership, and VMC</h3>
        <p style={styles.copy}>The browser avatar has one normalized-humanoid neutral pose profile. Speech owns mouth visemes while HINAA is speaking; fresh VMC may own blink, brows, gaze, and approved expression channels. Uncalibrated VMC limbs are deliberately not applied.</p>
        <div style={styles.metricGrid}>
          <Metric label="VMC state" value={tracker.status} />
          <Metric label="Packet age" value={tracker.diagnostics?.packetAgeMs == null ? "—" : `${tracker.diagnostics.packetAgeMs} ms`} />
          <Metric label="Packet rate" value={`${tracker.diagnostics?.packetRate ?? 0} packets/s`} />
          <Metric label="Receiver" value={tracker.diagnostics?.receiverInstanceId ?? "not connected"} />
          <Metric label="Calibration" value={tracker.calibration ? "Neutral captured" : "Not calibrated"} />
          <Metric label="Channels" value={`${tracker.diagnostics?.detectedChannels.length ?? 0} observed`} />
        </div>
        <div style={styles.actions}><button type="button" onClick={tracker.connect} style={styles.primary}>Connect / listen</button><button type="button" onClick={tracker.reconnect} style={styles.secondary}>Reconnect</button><button type="button" onClick={() => void tracker.testSignal()} style={styles.secondary}>Test signal</button><button type="button" onClick={tracker.calibrate} disabled={tracker.status !== "live"} style={styles.secondary}>Calibrate neutral</button><button type="button" onClick={tracker.disconnect} style={styles.secondary}>Disconnect</button></div>
      </section>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) { return <div style={styles.metric}><span>{label}</span><strong>{value}</strong></div>; }

const styles: Record<string, React.CSSProperties> = {
  panel: { padding: 20, background: "linear-gradient(160deg,#0f172a,#172554)", color: "#e2e8f0", minHeight: "100%", overflowY: "auto" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 },
  eyebrow: { margin: 0, color: "#5eead4", fontSize: 11, fontWeight: 800, letterSpacing: ".12em" },
  title: { margin: "5px 0 0", fontSize: 22, maxWidth: 620 },
  status: { margin: "12px 0", color: "#cbd5e1", fontSize: 13 },
  card: { border: "1px solid rgba(148,163,184,.22)", borderRadius: 12, padding: 14, background: "rgba(15,23,42,.55)", marginTop: 12 },
  cardTitle: { margin: 0, fontSize: 15 }, copy: { margin: "8px 0", fontSize: 12, color: "#cbd5e1", lineHeight: 1.5 },
  actions: { display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 },
  primary: { border: 0, borderRadius: 8, padding: "8px 10px", background: "#2dd4bf", color: "#042f2e", fontWeight: 800 },
  secondary: { border: "1px solid rgba(148,163,184,.3)", borderRadius: 8, padding: "8px 10px", background: "rgba(15,23,42,.55)", color: "#e2e8f0" },
  assetGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(235px,1fr))", gap: 10, marginTop: 12 },
  asset: { border: "1px solid", borderRadius: 10, padding: 11, background: "rgba(15,23,42,.42)" },
  assetText: { margin: "6px 0", fontSize: 11, lineHeight: 1.4, color: "#cbd5e1" },
  metricGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 8, marginTop: 10 },
  metric: { display: "grid", gap: 3, border: "1px solid rgba(148,163,184,.18)", borderRadius: 8, padding: 9, fontSize: 11, color: "#94a3b8" },
};
