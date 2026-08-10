/**
 * motionScenes.ts
 * 50 typed reusable motion scenes bound to real HinaaExperienceState events.
 */
import type { HinaaExperienceState } from "../companion/types";

export type MotionSceneId =
  // BOOT (1-4)
  | "core-awakening" | "logo-resolution" | "particle-gather" | "readiness-settle"
  // IDLE (5-8)
  | "breathing" | "subtle-orbit" | "ambient-drift" | "gaze-wander"
  // LISTENING (9-12)
  | "inward-particles" | "audio-rings" | "microphone-pulse" | "transcript-emerge"
  // THINKING (13-16)
  | "circuit-expand" | "neural-orbit" | "labyrinth-fold" | "reasoning-pulse"
  // SPEAKING (17-20)
  | "voice-wave" | "face-expression" | "word-materialization" | "ambient-ripple"
  // INTERRUPTION (21-23)
  | "immediate-audio-cut" | "visual-recoil" | "new-listening-focus"
  // ACTION (24-27)
  | "task-start" | "real-progress" | "success-ripple" | "recoverable-failure"
  // PANELS (28-33)
  | "slide-in" | "dock" | "expand" | "collapse" | "focus" | "dismiss"
  // PROVIDER (34-37)
  | "provider-carousel" | "capability-reveal" | "verified-state" | "unavailable-state"
  // TRANSCRIPT (38-42)
  | "user-turn-enter" | "assistant-turn-stream" | "code-block-settle" | "jump-to-latest" | "history-expand"
  // MEMORY (43-46)
  | "consent-preview" | "memory-saved" | "memory-forgotten" | "privacy-cleared"
  // SYSTEM (47-50)
  | "reconnect" | "offline-error" | "budget-warning" | "maintenance";

export interface MotionSceneConfig {
  id: MotionSceneId;
  label: string;
  durationMs: number;
  easing: string;
  particleDensity: number;
  glowIntensity: number;
}

export const MOTION_SCENES: Record<MotionSceneId, MotionSceneConfig> = {
  "core-awakening":       { id: "core-awakening", label: "Core Awakening", durationMs: 800, easing: "ease-out", particleDensity: 0.2, glowIntensity: 0.4 },
  "logo-resolution":      { id: "logo-resolution", label: "Logo Resolution", durationMs: 600, easing: "ease-in-out", particleDensity: 0.3, glowIntensity: 0.5 },
  "particle-gather":      { id: "particle-gather", label: "Particle Gather", durationMs: 500, easing: "ease-out", particleDensity: 0.6, glowIntensity: 0.7 },
  "readiness-settle":     { id: "readiness-settle", label: "Readiness Settle", durationMs: 400, easing: "ease-out", particleDensity: 0.3, glowIntensity: 0.4 },
  "breathing":            { id: "breathing", label: "Idle Breathing", durationMs: 3000, easing: "ease-in-out", particleDensity: 0.25, glowIntensity: 0.35 },
  "subtle-orbit":         { id: "subtle-orbit", label: "Subtle Orbit", durationMs: 4000, easing: "linear", particleDensity: 0.3, glowIntensity: 0.4 },
  "ambient-drift":        { id: "ambient-drift", label: "Ambient Drift", durationMs: 5000, easing: "ease-in-out", particleDensity: 0.2, glowIntensity: 0.3 },
  "gaze-wander":          { id: "gaze-wander", label: "Gaze Wander", durationMs: 2500, easing: "ease-in-out", particleDensity: 0.25, glowIntensity: 0.35 },
  "inward-particles":     { id: "inward-particles", label: "Inward Particles", durationMs: 300, easing: "ease-out", particleDensity: 0.8, glowIntensity: 0.85 },
  "audio-rings":          { id: "audio-rings", label: "Audio Pulse Rings", durationMs: 400, easing: "ease-out", particleDensity: 0.7, glowIntensity: 0.8 },
  "microphone-pulse":     { id: "microphone-pulse", label: "Microphone Active Pulse", durationMs: 1200, easing: "ease-in-out", particleDensity: 0.6, glowIntensity: 0.75 },
  "transcript-emerge":    { id: "transcript-emerge", label: "Transcript Emerge", durationMs: 250, easing: "ease-out", particleDensity: 0.4, glowIntensity: 0.5 },
  "circuit-expand":       { id: "circuit-expand", label: "Thinking Circuit Expansion", durationMs: 600, easing: "ease-in-out", particleDensity: 0.5, glowIntensity: 0.9 },
  "neural-orbit":         { id: "neural-orbit", label: "Neural Orbit", durationMs: 1500, easing: "linear", particleDensity: 0.6, glowIntensity: 0.8 },
  "labyrinth-fold":       { id: "labyrinth-fold", label: "Labyrinth Fold", durationMs: 800, easing: "ease-in-out", particleDensity: 0.4, glowIntensity: 0.7 },
  "reasoning-pulse":      { id: "reasoning-pulse", label: "Reasoning Pulse", durationMs: 700, easing: "ease-in-out", particleDensity: 0.5, glowIntensity: 0.8 },
  "voice-wave":           { id: "voice-wave", label: "Voice Output Wave", durationMs: 200, easing: "ease-out", particleDensity: 0.7, glowIntensity: 0.8 },
  "face-expression":      { id: "face-expression", label: "Facial Expression Transition", durationMs: 300, easing: "ease-out", particleDensity: 0.4, glowIntensity: 0.6 },
  "word-materialization": { id: "word-materialization", label: "Word Materialization", durationMs: 150, easing: "ease-out", particleDensity: 0.3, glowIntensity: 0.5 },
  "ambient-ripple":       { id: "ambient-ripple", label: "Ambient Speech Ripple", durationMs: 500, easing: "ease-out", particleDensity: 0.5, glowIntensity: 0.6 },
  "immediate-audio-cut":  { id: "immediate-audio-cut", label: "Immediate Audio Cut", durationMs: 50, easing: "ease-out", particleDensity: 0.1, glowIntensity: 0.2 },
  "visual-recoil":        { id: "visual-recoil", label: "Interruption Recoil", durationMs: 200, easing: "ease-out", particleDensity: 0.3, glowIntensity: 0.4 },
  "new-listening-focus":  { id: "new-listening-focus", label: "New Listening Focus", durationMs: 250, easing: "ease-out", particleDensity: 0.7, glowIntensity: 0.8 },
  "task-start":           { id: "task-start", label: "Task Execution Start", durationMs: 350, easing: "ease-out", particleDensity: 0.5, glowIntensity: 0.6 },
  "real-progress":        { id: "real-progress", label: "Verified Action Progress", durationMs: 450, easing: "ease-in-out", particleDensity: 0.4, glowIntensity: 0.5 },
  "success-ripple":       { id: "success-ripple", label: "Success Ripple", durationMs: 600, easing: "ease-out", particleDensity: 0.8, glowIntensity: 0.9 },
  "recoverable-failure":  { id: "recoverable-failure", label: "Recoverable Failure Settle", durationMs: 500, easing: "ease-out", particleDensity: 0.2, glowIntensity: 0.3 },
  "slide-in":             { id: "slide-in", label: "Panel Slide In", durationMs: 300, easing: "cubic-bezier(0.16, 1, 0.3, 1)", particleDensity: 0.2, glowIntensity: 0.3 },
  "dock":                 { id: "dock", label: "Compact Dock Transition", durationMs: 350, easing: "cubic-bezier(0.16, 1, 0.3, 1)", particleDensity: 0.15, glowIntensity: 0.25 },
  "expand":               { id: "expand", label: "Full View Expand", durationMs: 350, easing: "cubic-bezier(0.16, 1, 0.3, 1)", particleDensity: 0.3, glowIntensity: 0.4 },
  "collapse":             { id: "collapse", label: "Panel Collapse", durationMs: 250, easing: "ease-out", particleDensity: 0.1, glowIntensity: 0.2 },
  "focus":                { id: "focus", label: "Element Focus", durationMs: 200, easing: "ease-out", particleDensity: 0.2, glowIntensity: 0.5 },
  "dismiss":              { id: "dismiss", label: "Panel Dismiss", durationMs: 200, easing: "ease-in", particleDensity: 0.1, glowIntensity: 0.1 },
  "provider-carousel":    { id: "provider-carousel", label: "Provider Carousel Shift", durationMs: 300, easing: "ease-out", particleDensity: 0.3, glowIntensity: 0.5 },
  "capability-reveal":    { id: "capability-reveal", label: "Capability Badge Reveal", durationMs: 250, easing: "ease-out", particleDensity: 0.2, glowIntensity: 0.4 },
  "verified-state":       { id: "verified-state", label: "Verified Provider Glow", durationMs: 400, easing: "ease-out", particleDensity: 0.4, glowIntensity: 0.7 },
  "unavailable-state":    { id: "unavailable-state", label: "Unavailable Provider Dim", durationMs: 300, easing: "ease-out", particleDensity: 0.1, glowIntensity: 0.2 },
  "user-turn-enter":      { id: "user-turn-enter", label: "User Turn Entry", durationMs: 250, easing: "ease-out", particleDensity: 0.4, glowIntensity: 0.5 },
  "assistant-turn-stream":{ id: "assistant-turn-stream", label: "Assistant Stream Entry", durationMs: 200, easing: "ease-out", particleDensity: 0.5, glowIntensity: 0.6 },
  "code-block-settle":    { id: "code-block-settle", label: "Code Block Settle", durationMs: 300, easing: "ease-out", particleDensity: 0.2, glowIntensity: 0.3 },
  "jump-to-latest":       { id: "jump-to-latest", label: "Jump to Latest Scroll", durationMs: 250, easing: "ease-out", particleDensity: 0.15, glowIntensity: 0.25 },
  "history-expand":       { id: "history-expand", label: "Full Transcript History Expand", durationMs: 350, easing: "cubic-bezier(0.16, 1, 0.3, 1)", particleDensity: 0.25, glowIntensity: 0.35 },
  "consent-preview":      { id: "consent-preview", label: "Memory Consent Preview", durationMs: 300, easing: "ease-out", particleDensity: 0.3, glowIntensity: 0.4 },
  "memory-saved":         { id: "memory-saved", label: "Memory Saved Glow", durationMs: 500, easing: "ease-out", particleDensity: 0.6, glowIntensity: 0.8 },
  "memory-forgotten":     { id: "memory-forgotten", label: "Memory Cleared Fade", durationMs: 400, easing: "ease-out", particleDensity: 0.1, glowIntensity: 0.2 },
  "privacy-cleared":      { id: "privacy-cleared", label: "Privacy Wipe Pulse", durationMs: 450, easing: "ease-out", particleDensity: 0.2, glowIntensity: 0.3 },
  "reconnect":            { id: "reconnect", label: "WebSocket Reconnecting Pulse", durationMs: 1000, easing: "ease-in-out", particleDensity: 0.4, glowIntensity: 0.5 },
  "offline-error":        { id: "offline-error", label: "Offline Error Notice", durationMs: 400, easing: "ease-out", particleDensity: 0.1, glowIntensity: 0.2 },
  "budget-warning":       { id: "budget-warning", label: "Quota Warning Highlight", durationMs: 500, easing: "ease-out", particleDensity: 0.3, glowIntensity: 0.6 },
  "maintenance":          { id: "maintenance", label: "Maintenance Mode Settle", durationMs: 600, easing: "ease-in-out", particleDensity: 0.2, glowIntensity: 0.3 },
};

export function mapExperienceToMotionScene(state: HinaaExperienceState): MotionSceneId {
  switch (state) {
    case "booting":
      return "core-awakening";
    case "intro":
      return "logo-resolution";
    case "idle":
      return "breathing";
    case "session_starting":
      return "particle-gather";
    case "listening":
      return "microphone-pulse";
    case "possible_speech":
    case "active_speech":
      return "inward-particles";
    case "hesitation":
      return "ambient-drift";
    case "committing":
    case "transcribing":
      return "transcript-emerge";
    case "thinking":
      return "circuit-expand";
    case "streaming_text":
      return "word-materialization";
    case "speaking":
      return "voice-wave";
    case "interrupted":
      return "immediate-audio-cut";
    case "reconnecting":
      return "reconnect";
    case "provider_unavailable":
    case "error":
      return "recoverable-failure";
    case "paused":
      return "readiness-settle";
    case "session_ending":
      return "dismiss";
    default:
      return "breathing";
  }
}
