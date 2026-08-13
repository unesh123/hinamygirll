import { useCallback, useEffect, useRef, useState } from "react";
import type { PresenceMode } from "./AvatarPresence";
import type { AvatarPresentation } from "../../features/avatar/avatarPresentation";
import { defaultAvatarPresentation, flipAvatarFacing } from "../../features/avatar/avatarPresentation";
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
  mouthExpressions: string[];
  blinkExpressions: string[];
  lookExpressions: string[];
  springBonesPresent: boolean;
  licenseMetadataPresent: boolean;
  licenseSummary: string;
  vseeFaceCompatibility: "compatible_candidate" | "incompatible" | "unknown";
  reason: string;
};

type Props = {
  tracker: VSeeFaceState;
  selectedModelUrl: string;
  mode: PresenceMode;
  onModeChange: (mode: PresenceMode) => void;
  onSelectModel: (url: string, resetCompanionView?: boolean) => void;
  presentation: AvatarPresentation;
  onPresentationChange: (presentation: AvatarPresentation) => void;
  trackingMode: "autonomous" | "exact-vseeface" | "tracking-proxy";
  onTrackingModeChange: (mode: "autonomous" | "exact-vseeface" | "tracking-proxy") => void;
  onClose: () => void;
};

const CAMERA_LABELS: Array<[PresenceMode, string]> = [
  ["portrait", "Portrait"], ["closeup", "Close-up"], ["upperbody", "Upper body"], ["full", "Full body"],
];

function modelCompatibility(asset: AvatarAsset | undefined): string {
  if (!asset) return "Loading model details…";
  if (asset.vseeFaceCompatibility === "compatible_candidate") return "VRM 0.x candidate for VSeeFace";
  if (asset.vrmVersion === "1.0") return "Browser model · not labelled VSeeFace compatible";
  return "Compatibility needs model inspection";
}

export function AvatarLab({
  tracker, selectedModelUrl, mode, onModeChange, onSelectModel, presentation,
  onPresentationChange, trackingMode, onTrackingModeChange, onClose,
}: Props) {
  const [assets, setAssets] = useState<AvatarAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("Choose a model or add one from this computer.");
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/v1/avatar-assets");
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail || "HINAA could not load local avatar models.");
      setAssets(Array.isArray(body.assets) ? body.assets : []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "HINAA could not load local avatar models.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const importFile = async (file: File) => {
    setMessage(`Checking ${file.name} on this computer…`);
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const response = await fetch("/api/v1/avatar-assets/import", { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok || !body?.asset?.browserUrl) throw new Error(body?.detail || "HINAA could not import that model.");
      onSelectModel(body.asset.browserUrl, true);
      setMessage(`${body.asset.displayName} is now centered in portrait view with HINAA’s strong relaxed-arm preset.`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "HINAA could not import that model.");
    }
  };

  const removeManaged = async (asset: AvatarAsset) => {
    if (asset.source !== "managed") return;
    if (!window.confirm(`Delete HINAA’s managed copy of ${asset.displayName}? Your original file will not be changed.`)) return;
    try {
      const response = await fetch(`/api/v1/avatar-assets/${encodeURIComponent(asset.assetId)}?confirm=true`, { method: "DELETE" });
      const body = await response.json();
      if (!response.ok || !body.deleted) throw new Error(body?.detail || "HINAA could not delete that managed copy.");
      setMessage(`Deleted HINAA’s managed copy of ${asset.displayName}.`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "HINAA could not delete that managed copy.");
    }
  };

  const selectable = assets.filter((asset) => asset.browserUrl);
  const selected = assets.find((asset) => asset.browserUrl === selectedModelUrl);
  const selectModel = (url: string) => {
    onSelectModel(url);
    setMessage("Model selected. HINAA uses portrait view and remembers its appearance settings.");
  };

  return (
    <section className="avatar-lab" role="dialog" aria-modal="false" aria-label="Avatar Lab">
      <header className="avatar-lab__header">
        <div>
          <p className="avatar-lab__eyebrow">HINAA AVATAR</p>
          <h2>Choose her look</h2>
          <p>Pick a model, add a local VRM, or fix the view in one click. HINAA never edits your original VRM file.</p>
        </div>
        <button type="button" className="avatar-lab__icon-button" onClick={onClose} aria-label="Close Avatar Lab">Close</button>
      </header>

      <p className="avatar-lab__status" role="status">{message}</p>

      <section className="avatar-lab__hero-card">
        <div className="avatar-lab__hero-copy">
          <span className="avatar-lab__label">CURRENT AVATAR</span>
          <h3>{selected?.displayName ?? "Hinaa"}</h3>
          <p>{modelCompatibility(selected)}</p>
        </div>
        <div className="avatar-lab__hero-actions">
          <input
            ref={inputRef}
            type="file"
            accept=".vrm,.glb,.gltf"
            className="avatar-lab__file-input"
            onChange={(event) => { const file = event.target.files?.[0]; if (file) void importFile(file); event.currentTarget.value = ""; }}
          />
          <button type="button" className="avatar-lab__primary" onClick={() => inputRef.current?.click()}>+ Add a local avatar</button>
          <button type="button" className="avatar-lab__secondary" onClick={() => void refresh()} disabled={loading}>Refresh models</button>
        </div>
      </section>

      <section className="avatar-lab__card">
        <div className="avatar-lab__section-heading"><div><span className="avatar-lab__label">MODEL</span><h3>Switch in one click</h3></div><span>{loading ? "Loading…" : `${selectable.length} available`}</span></div>
        <select
          className="avatar-lab__select"
          value={selectedModelUrl}
          aria-label="Choose an avatar model"
          onChange={(event) => selectModel(event.target.value)}
        >
          {selectable.map((asset) => <option key={asset.assetId} value={asset.browserUrl!}>{asset.displayName}{asset.source === "managed" ? " · local" : ""}</option>)}
        </select>
        <div className="avatar-lab__model-strip">
          {selectable.map((asset) => <button key={asset.assetId} type="button" className={`avatar-lab__model-chip${asset.browserUrl === selectedModelUrl ? " avatar-lab__model-chip--active" : ""}`} onClick={() => selectModel(asset.browserUrl!)}>{asset.displayName}</button>)}
        </div>
      </section>

      <section className="avatar-lab__card">
        <div className="avatar-lab__section-heading"><div><span className="avatar-lab__label">MAKE HER LOOK RIGHT</span><h3>Facing and hands</h3></div><span>Saved for this model</span></div>
        <p className="avatar-lab__help">New models start with HINAA’s safe front-facing relaxed pose. If this exact model looks backward or its author pose is better, use one simple correction below.</p>
        <div className="avatar-lab__actions">
          <button type="button" className="avatar-lab__primary" onClick={() => { onPresentationChange(flipAvatarFacing(presentation)); setMessage("Facing flipped for this model. HINAA saved the correction locally."); }}>Flip facing</button>
          <button type="button" className={presentation.poseMode === "relaxed" ? "avatar-lab__primary" : "avatar-lab__secondary"} onClick={() => onPresentationChange({ ...presentation, poseMode: "relaxed" })}>Relax arms</button>
          <button type="button" className={presentation.poseMode === "original" ? "avatar-lab__primary" : "avatar-lab__secondary"} onClick={() => onPresentationChange({ ...presentation, poseMode: "original" })}>Original pose</button>
          <button type="button" className="avatar-lab__secondary" onClick={() => { onPresentationChange(defaultAvatarPresentation(selectedModelUrl)); setMessage("Restored HINAA’s default appearance preset for this model."); }}>Reset model view</button>
        </div>
        <label className="avatar-lab__range-label">Height and scale <input type="range" min="0.7" max="1.3" step="0.01" value={presentation.scale} onChange={(event) => onPresentationChange({ ...presentation, scale: Number(event.target.value) })} /><output>{presentation.scale.toFixed(2)}×</output></label>
      </section>

      <section className="avatar-lab__card">
        <div className="avatar-lab__section-heading"><div><span className="avatar-lab__label">CAMERA</span><h3>Companion view</h3></div><span>Portrait is recommended</span></div>
        <div className="avatar-lab__actions">{CAMERA_LABELS.map(([value, label]) => <button key={value} type="button" className={mode === value ? "avatar-lab__primary" : "avatar-lab__secondary"} onClick={() => onModeChange(value)} aria-pressed={mode === value}>{label}</button>)}</div>
      </section>

      <section className="avatar-lab__card">
        <div className="avatar-lab__section-heading"><div><span className="avatar-lab__label">VSEEFACE</span><h3>Tracking mode</h3></div><span>{tracker.status}</span></div>
        <p className="avatar-lab__help">Use Autonomous for normal HINAA. Exact VSeeFace is available only for a parsed VRM 0.x candidate. Tracking Proxy is visibly marked as a proxy and never moves uncalibrated limbs.</p>
        <div className="avatar-lab__actions">
          <button type="button" className={trackingMode === "autonomous" ? "avatar-lab__primary" : "avatar-lab__secondary"} onClick={() => onTrackingModeChange("autonomous")}>Autonomous</button>
          <button type="button" className={trackingMode === "exact-vseeface" ? "avatar-lab__primary" : "avatar-lab__secondary"} disabled={selected?.vseeFaceCompatibility !== "compatible_candidate"} onClick={() => onTrackingModeChange("exact-vseeface")}>Exact VSeeFace</button>
          <button type="button" className={trackingMode === "tracking-proxy" ? "avatar-lab__primary" : "avatar-lab__secondary"} onClick={() => onTrackingModeChange("tracking-proxy")}>Tracking proxy</button>
          <button type="button" className="avatar-lab__secondary" onClick={tracker.status === "disconnected" ? tracker.connect : tracker.reconnect}>{tracker.status === "disconnected" ? "Connect VSeeFace" : "Reconnect"}</button>
        </div>
      </section>

      <details className="avatar-lab__details">
        <summary>Model details and advanced actions</summary>
        {selected ? <div className="avatar-lab__details-body">
          <p><strong>Rig:</strong> {selected.humanoidPresent ? `${selected.humanoidBones.length} humanoid bones` : "No verified humanoid rig"}. <strong>Expressions:</strong> {selected.presetExpressions.length}. <strong>Spring bones:</strong> {selected.springBonesPresent ? "present" : "not reported"}.</p>
          <p><strong>Speech targets:</strong> {selected.mouthExpressions.join(", ") || "none detected"}. <strong>Blink:</strong> {selected.blinkExpressions.join(", ") || "none detected"}.</p>
          <p>{selected.reason} {selected.licenseSummary}</p>
          {selected.source === "managed" && <button type="button" className="avatar-lab__danger" onClick={() => void removeManaged(selected)}>Delete HINAA-managed copy</button>}
        </div> : <p className="avatar-lab__details-body">Select a model to see its local inspection.</p>}
      </details>
    </section>
  );
}
