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
  .passthrough();

const performanceSchema = z
  .object({
    facePreset: z.enum(facePresets),
    gesture: z.enum(gestures),
    gazeTarget: z.enum(["camera", "away", "down", "user-content"]),
    headMotion: z.enum(["none", "subtle", "nod", "shake"]),
    blinkRate: z.number().min(0.1).max(1),
  })
  .passthrough();

const beatSchema = z
  .object({
    anchorText: z.string().min(1).max(80),
    face: z.enum(facePresets),
    gesture: z.enum(beatGestures),
    gaze: z.enum(["camera", "down", "away", "user-content"]),
    intensity: z.number().min(0).max(1).optional(),
  })
  .passthrough();

const memoryCandidateSchema = z
  .object({
    content: z.string().min(1).max(500),
    category: z.string().optional().default("other"),
    requiresConfirmation: z.boolean().optional().default(true),
    sourceMessageId: z.string().optional(),
  })
  .passthrough();

const toolRequestSchema = z
  .preprocess((val) => {
    if (val && typeof val === "object") {
      const obj = { ...(val as Record<string, unknown>) };
      if (!obj.toolName && typeof obj.tool === "string") {
        obj.toolName = obj.tool;
      }
      if (!obj.parameters && obj.arguments && typeof obj.arguments === "object") {
        obj.parameters = obj.arguments;
      }
      return obj;
    }
    return val;
  }, z.object({
    toolName: z.string().min(1).max(100),
    parameters: z.record(z.string(), z.any()),
    id: z.string().nullable().optional(),
    intent: z.string().nullable().optional(),
    reason: z.string().nullable().optional(),
    confirmed: z.boolean().nullable().optional(),
    approvalSource: z.string().nullable().optional(),
    userId: z.string().nullable().optional(),
    conversationId: z.string().nullable().optional(),
  }).passthrough());

export const assistantTurnPlanSchema = z
  .object({
    schemaVersion: z.number().optional(),
    spokenText: z.string().min(1).max(4000),
    displayText: z.string().min(1).max(8000),
    language: z.enum(["en-US", "hi-IN", "mixed"]),
    emotion: emotionSchema,
    performance: performanceSchema,
    beats: z.array(beatSchema).max(12).optional(),
    memoryCandidates: z.array(memoryCandidateSchema).max(20).optional().default([]),
    toolRequests: z.array(toolRequestSchema).max(20).optional().default([]),
    requestedProvider: z.string().nullable().optional(),
    requestedModel: z.string().nullable().optional(),
    resolvedProvider: z.string().nullable().optional(),
    resolvedModel: z.string().nullable().optional(),
    fallback: z.boolean().optional(),
    fallbackReason: z.string().nullable().optional(),
    latencyMs: z.number().nullable().optional(),
    activitySteps: z.array(z.any()).optional(),
    thinking: z.string().nullable().optional(),
    userId: z.string().nullable().optional(),
    conversationId: z.string().nullable().optional(),
  })
  .passthrough();

export type AssistantTurnPlan = z.infer<typeof assistantTurnPlanSchema>;

export function parseAssistantTurnPlan(input: unknown): AssistantTurnPlan {
  const result = assistantTurnPlanSchema.safeParse(input);
  if (result.success) return result.data;

  // Graceful salvage if input is a valid object but has minor formatting deviations
  if (input && typeof input === "object") {
    const raw = input as Record<string, any>;
    const displayText =
      typeof raw.displayText === "string" && raw.displayText.trim()
        ? raw.displayText
        : typeof raw.text === "string" && raw.text.trim()
          ? raw.text
          : typeof raw.content === "string" && raw.content.trim()
            ? raw.content
            : "I completed your request.";
    const spokenText =
      typeof raw.spokenText === "string" && raw.spokenText.trim()
        ? raw.spokenText
        : displayText.slice(0, 160);
    const validLang = ["en-US", "hi-IN", "mixed"].includes(raw.language)
      ? raw.language
      : "mixed";

    const emotion = raw.emotion && typeof raw.emotion === "object" ? raw.emotion as Record<string, unknown> : {};
    const performance = raw.performance && typeof raw.performance === "object" ? raw.performance as Record<string, unknown> : {};
    const toolRequests = Array.isArray(raw.toolRequests)
      ? raw.toolRequests.filter((item) => item && typeof item === "object").map((item) => {
          const request = item as Record<string, unknown>;
          return {
            ...request,
            toolName: typeof request.toolName === "string" && request.toolName.trim() ? request.toolName : request.tool,
            parameters: request.parameters && typeof request.parameters === "object"
              ? request.parameters
              : request.arguments && typeof request.arguments === "object"
                ? request.arguments
                : undefined,
          };
        })
      : [];

    // Providers occasionally omit optional fields or use the older aliases.
    // Normalize those fields before the final schema parse so one malformed
    // metadata field never turns an otherwise useful answer into a formatting
    // error.
    return assistantTurnPlanSchema.parse({
      schemaVersion: typeof raw.schemaVersion === "number" ? raw.schemaVersion : 1,
      spokenText,
      displayText,
      language: validLang,
      emotion: {
        primary: emotionNames.includes(emotion.primary as typeof emotionNames[number]) ? emotion.primary : "happy",
        intensity: typeof emotion.intensity === "number" ? Math.max(0, Math.min(1, emotion.intensity)) : 0.5,
        valence: typeof emotion.valence === "number" ? Math.max(-1, Math.min(1, emotion.valence)) : 0.4,
        arousal: typeof emotion.arousal === "number" ? Math.max(-1, Math.min(1, emotion.arousal)) : 0.2,
      },
      performance: {
        facePreset: facePresets.includes(performance.facePreset as typeof facePresets[number]) ? performance.facePreset : "soft_smile",
        gesture: gestures.includes(performance.gesture as typeof gestures[number]) ? performance.gesture : "none",
        gazeTarget: ["camera", "away", "down", "user-content"].includes(String(performance.gazeTarget)) ? performance.gazeTarget : "camera",
        headMotion: ["none", "subtle", "nod", "shake"].includes(String(performance.headMotion)) ? performance.headMotion : "subtle",
        blinkRate: typeof performance.blinkRate === "number" ? Math.max(0.1, Math.min(1, performance.blinkRate)) : 0.45,
      },
      beats: Array.isArray(raw.beats) ? raw.beats : [],
      memoryCandidates: Array.isArray(raw.memoryCandidates) ? raw.memoryCandidates : [],
      toolRequests,
      requestedProvider: typeof raw.requestedProvider === "string" ? raw.requestedProvider : null,
      requestedModel: typeof raw.requestedModel === "string" ? raw.requestedModel : null,
      resolvedProvider: typeof raw.resolvedProvider === "string" ? raw.resolvedProvider : null,
      resolvedModel: typeof raw.resolvedModel === "string" ? raw.resolvedModel : null,
      fallback: Boolean(raw.fallback),
      fallbackReason: typeof raw.fallbackReason === "string" ? raw.fallbackReason : null,
      latencyMs: typeof raw.latencyMs === "number" ? raw.latencyMs : null,
      activitySteps: Array.isArray(raw.activitySteps) ? raw.activitySteps : [],
      thinking: typeof raw.thinking === "string" ? raw.thinking : null,
      userId: typeof raw.userId === "string" ? raw.userId : null,
      conversationId: typeof raw.conversationId === "string" ? raw.conversationId : null,
    });
  }

  return assistantTurnPlanSchema.parse(input);
}
