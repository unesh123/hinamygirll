import { z } from "zod";

export const emotionNames = [
  "neutral",
  "happy",
  "excited",
  "playful",
  "shy",
  "concerned",
  "sad",
  "surprised",
  "thinking",
] as const;

export const facePresets = [
  "neutral",
  "soft_smile",
  "big_smile",
  "blush",
  "pout",
  "concerned",
  "surprised",
  "thinking",
] as const;

export const gestures = [
  "none",
  "small_nod",
  "head_shake",
  "gentle_head_tilt",
  "wave",
  "explain",
  "celebrate",
  "reassure",
  "listening_lean",
] as const;

const beatGestures = [
  "none",
  "small_nod",
  "head_shake",
  "gentle_head_tilt",
  "wave",
  "explain",
  "celebrate",
  "reassure",
] as const;

const emotionSchema = z
  .object({
    primary: z.enum(emotionNames),
    intensity: z.number().min(0).max(1),
    valence: z.number().min(-1).max(1),
    arousal: z.number().min(-1).max(1),
  })
  .strict();

const performanceSchema = z
  .object({
    facePreset: z.enum(facePresets),
    gesture: z.enum(gestures),
    gazeTarget: z.enum(["camera", "away", "down", "user-content"]),
    headMotion: z.enum(["none", "subtle", "nod", "shake"]),
    blinkRate: z.number().min(0.1).max(1),
  })
  .strict();

const beatSchema = z
  .object({
    anchorText: z.string().min(1).max(80),
    face: z.enum(facePresets),
    gesture: z.enum(beatGestures),
    gaze: z.enum(["camera", "down", "away", "user-content"]),
    intensity: z.number().min(0).max(1).optional(),
  })
  .strict();

const memoryCandidateSchema = z
  .object({
    content: z.string().min(1).max(500),
    category: z.enum(["preference", "profile", "goal", "project", "other"]),
    requiresConfirmation: z.literal(true),
    sourceMessageId: z.uuid().optional(),
  })
  .strict();

const toolRequestSchema = z
  .object({
    toolName: z.string().min(1).max(100),
    parameters: z.record(z.string(), z.any()),
    // Some compatible model gateways serialize absent optional values as null
    // and may echo a proposed confirmation flag.  This plan remains only a
    // proposal: server-side tool execution still independently requires
    // explicit user confirmation for protected actions.
    confirmed: z.boolean().optional(),
    userId: z.string().nullable().optional(),
    conversationId: z.string().nullable().optional(),
  })
  .strict();

export const assistantTurnPlanSchema = z
  .object({
    spokenText: z.string().min(1).max(4000),
    displayText: z.string().min(1).max(8000),
    language: z.enum(["en-US", "hi-IN", "mixed"]),
    emotion: emotionSchema,
    performance: performanceSchema,
    beats: z.array(beatSchema).max(12).optional(),
    memoryCandidates: z.array(memoryCandidateSchema).max(3),
    toolRequests: z.array(toolRequestSchema).max(5),
  })
  .strict();

export type AssistantTurnPlan = z.infer<typeof assistantTurnPlanSchema>;

export function parseAssistantTurnPlan(input: unknown): AssistantTurnPlan {
  return assistantTurnPlanSchema.parse(input);
}
