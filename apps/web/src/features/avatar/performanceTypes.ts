import { z } from "zod";

export const performanceCueKindSchema = z.enum([
  "emotion",
  "gesture",
  "gaze",
  "blink",
  "breath",
  "jaw",
  "idle",
]);

export const semanticMotionSchema = z.enum([
  "neutral_idle",
  "friendly_greeting",
  "small_nod",
  "thoughtful_pause",
  "listening",
  "happy_ack",
  "calm_reassure",
  "mild_celebrate",
  "apology_correction",
  "return_neutral",
  "none",
]);

export const performanceCueSchema = z
  .object({
    id: z.string().min(1).max(80),
    kind: performanceCueKindSchema,
    semantic: semanticMotionSchema,
    startMs: z.number().min(0).max(120_000),
    durationMs: z.number().min(0).max(30_000),
    priority: z.number().int().min(0).max(100),
    intensity: z.number().min(0).max(1),
    blendInMs: z.number().min(0).max(2_000),
    blendOutMs: z.number().min(0).max(2_000),
    generation: z.number().int().min(0),
    facePreset: z.string().max(40).optional(),
    gesture: z.string().max(40).optional(),
  })
  .strict();

export const performanceSequenceSchema = z
  .object({
    generation: z.number().int().min(0),
    createdAtMs: z.number().min(0),
    lipSyncLevel: z.enum(["amplitude", "viseme", "phoneme"]),
    cues: z.array(performanceCueSchema).max(48),
  })
  .strict();

export type PerformanceCue = z.infer<typeof performanceCueSchema>;
export type PerformanceSequence = z.infer<typeof performanceSequenceSchema>;
export type SemanticMotion = z.infer<typeof semanticMotionSchema>;

/** Static allowlist: semantic cue → procedural adapter action only. */
export const SEMANTIC_RUNTIME_MAP: Record<
  SemanticMotion,
  { cssGesture: string; cssEmotion?: string }
> = {
  none: { cssGesture: "none" },
  neutral_idle: { cssGesture: "none", cssEmotion: "neutral" },
  friendly_greeting: { cssGesture: "wave", cssEmotion: "happy" },
  small_nod: { cssGesture: "small_nod" },
  thoughtful_pause: { cssGesture: "none", cssEmotion: "thinking" },
  listening: { cssGesture: "listening_lean" },
  happy_ack: { cssGesture: "gentle_head_tilt", cssEmotion: "happy" },
  calm_reassure: { cssGesture: "reassure", cssEmotion: "concerned" },
  mild_celebrate: { cssGesture: "celebrate", cssEmotion: "excited" },
  apology_correction: { cssGesture: "small_nod", cssEmotion: "shy" },
  return_neutral: { cssGesture: "none", cssEmotion: "neutral" },
};
