/** Both synthesis attempts share one deadline and the turn's cancellation. */
export async function withSpeechFallback<T>(
  parentSignal: AbortSignal,
  timed: (signal: AbortSignal) => Promise<T>,
  audioOnly: (signal: AbortSignal) => Promise<T>,
  timeoutMs = 15_000,
): Promise<T> {
  const signal = AbortSignal.any([parentSignal, AbortSignal.timeout(timeoutMs)]);
  signal.throwIfAborted();
  try {
    return await timed(signal);
  } catch {
    signal.throwIfAborted();
    return await audioOnly(signal);
  }
}
