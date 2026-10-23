/**
 * contracts/timelineSpec.ts
 * Canonical TypeScript contract for TimelineSpec, RenderJob, ProviderJob, and Artifact
 */

export interface CanvasSpec {
  width: number;
  height: number;
  fps: number;
  durationFrames: number;
}

export interface BrandSpec {
  primaryColor: string;
  secondaryColor: string;
  fontFamily: string;
  logoAssetId?: string;
}

export interface AudioTrackSpec {
  voiceAssetId?: string;
  musicAssetId?: string;
  targetLufs: number;
  duckingDb: number;
}

export interface KeyframeSpec {
  frame: number;
  property: string;
  value: number;
  easing: string;
}

export interface LayerSpec {
  id: string;
  name: string;
  type: "video" | "image" | "html_anime" | "text" | "subtitle" | "audio";
  sourceAssetId?: string;
  htmlContent?: string;
  inFrame: number;
  outFrame: number;
  keyframes?: KeyframeSpec[];
}

export interface SceneSpec {
  id: string;
  name: string;
  startFrame: number;
  durationFrames: number;
  transition: "cut" | "crossfade" | "color-dip" | "wipe";
  layers: LayerSpec[];
}

export interface TimelineSpec {
  schemaVersion: "1.0";
  projectId: string;
  canvas: CanvasSpec;
  brand: BrandSpec;
  audio: AudioTrackSpec;
  scenes: SceneSpec[];
  deliverables: Array<"preview.mp4" | "master.mp4" | "captions.srt" | "poster.png" | "output.webm" | "output.gif">;
}

export interface Artifact {
  id: string;
  kind: "video" | "audio" | "image" | "captions" | "poster";
  path: string;
  filename: string;
  mimeType: string;
  sha256: string;
  sizeBytes: number;
  durationSeconds?: number;
  width?: number;
  height?: number;
  fps?: number;
  provenance: Record<string, any>;
  createdAt: number;
}

export interface RenderJob {
  id: string;
  timelineSpecId: string;
  status: "queued" | "running" | "succeeded" | "failed";
  idempotencyKey: string;
  progress: number;
  estimatedCostUsd: number;
  actualCostUsd: number;
  outputArtifacts: Record<string, string>;
  qcMetrics?: Record<string, any>;
  error?: string;
  createdAt: number;
  completedAt?: number;
}
