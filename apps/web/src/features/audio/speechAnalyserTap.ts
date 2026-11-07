/**
 * Shares the TTS playback AnalyserNode with the avatar without prop plumbing.
 * The avatar reads a derived, higher-resolution analyser (formant peaks need ≥1024 FFT)
 * so the playback hook's own jaw-energy analyser settings stay untouched.
 */
let source: AnalyserNode | null = null;
let derived: AnalyserNode | null = null;

export function publishSpeechAnalyser(node: AnalyserNode | null): void {
  if (node === source) return;
  try { derived?.disconnect(); } catch { /* already disconnected */ }
  derived = null;
  source = node;
}

export function getLipSyncAnalyser(): AnalyserNode | null {
  if (derived) return derived;
  if (!source || typeof source.context?.createAnalyser !== "function") return null;
  try {
    const node = source.context.createAnalyser();
    node.fftSize = 1024;
    node.smoothingTimeConstant = 0.25;
    source.connect(node);
    derived = node;
  } catch {
    derived = null;
  }
  return derived;
}
