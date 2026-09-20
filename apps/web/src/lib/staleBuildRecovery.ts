// A redeploy deletes the lazy chunks the previous build referenced, so a client
// still running the old shell fails on `import()` and renders nothing. The
// service worker then re-serves that same stale shell, which is why the only
// recovery a user could find was a manual hard reload. Reload once after
// dropping the cached shell, and never twice in a row so a genuinely broken
// build cannot put the app in a reload loop.

const RECOVERY_FLAG = "hinaa-stale-build-recovered";

const STALE_CHUNK =
  /failed to fetch dynamically imported module|error loading dynamically imported module|importing a module script failed|could not load chunk|unable to preload css/i;

export function isStaleChunkError(error: unknown): boolean {
  const message =
    typeof error === "string"
      ? error
      : (error as { message?: unknown } | null)?.message;
  return typeof message === "string" && STALE_CHUNK.test(message);
}

interface RecoveryGlobals {
  sessionStorage: Pick<Storage, "getItem" | "setItem">;
  location: { reload(): void };
  unregisterServiceWorkers(): Promise<unknown>;
}

export type RecoveryOutcome =
  | "ignored"
  | "already-recovered"
  | "reloaded";

export async function recoverFromStaleChunk(
  globals: RecoveryGlobals,
  error: unknown,
): Promise<RecoveryOutcome> {
  if (!isStaleChunkError(error)) return "ignored";
  let alreadyRecovered = false;
  try {
    alreadyRecovered = globals.sessionStorage.getItem(RECOVERY_FLAG) === "1";
  } catch {
    // Private-mode storage throws; recovering is worth the reload risk anyway.
  }
  if (alreadyRecovered) return "already-recovered";
  try {
    globals.sessionStorage.setItem(RECOVERY_FLAG, "1");
  } catch {
    // Ignored: the flag is a loop breaker, not data.
  }
  // Awaited so the old shell cannot be served again from the SW cache while the
  // reload is in flight.
  try {
    await globals.unregisterServiceWorkers();
  } catch {
    // A purge that fails still beats a blank screen; reload anyway.
  }
  globals.location.reload();
  return "reloaded";
}

export async function purgeServiceWorkerCache(): Promise<void> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  const registrations = await navigator.serviceWorker.getRegistrations();
  await Promise.all(registrations.map((r) => r.unregister()));
  if (typeof caches === "undefined") return;
  const keys = await caches.keys();
  await Promise.all(keys.map((key) => caches.delete(key)));
}

export function installStaleBuildRecovery(): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handle = (error: unknown) =>
    void recoverFromStaleChunk(
      {
        sessionStorage: window.sessionStorage,
        location: window.location,
        unregisterServiceWorkers: purgeServiceWorkerCache,
      },
      error,
    );
  // Vite's own signal for a failed chunk preload, then the generic rejection
  // path that React.lazy() failures land on instead.
  const onPreloadError = (event: Event) =>
    handle((event as CustomEvent<{ error?: unknown }>).detail?.error ?? event);
  const onRejection = (event: PromiseRejectionEvent) => handle(event.reason);
  window.addEventListener("vite:preloadError", onPreloadError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => {
    window.removeEventListener("vite:preloadError", onPreloadError);
    window.removeEventListener("unhandledrejection", onRejection);
  };
}
