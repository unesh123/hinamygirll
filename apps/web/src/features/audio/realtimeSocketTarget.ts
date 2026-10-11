/**
 * Chooses where the live voice socket should connect, from the backend's answer.
 *
 * A same-origin wss:// on the hosted site can never upgrade (Vercel does not
 * carry WebSocket upgrades), so it is only a fallback for local development.
 * When the backend says the socket is unavailable, the client must not open
 * the dead same-origin socket and retry ten times for nothing.
 */

export type RealtimeTarget =
  | { kind: "advertised"; url: string }
  | { kind: "same-origin"; url: string }
  | { kind: "unavailable"; reason: string };

export function chooseRealtimeTarget(input: {
  advertisedUrl: unknown;
  pageHost: string;
  isHttps: boolean;
  sameOriginUrl: string;
  answered: boolean;
}): RealtimeTarget {
  if (!input.isHttps) return { kind: "same-origin", url: input.sameOriginUrl };
  if (input.answered && input.advertisedUrl === null) {
    return {
      kind: "unavailable",
      reason: "The backend has no realtime address for this site. Live voice needs a configured realtime origin.",
    };
  }
  const advertised = typeof input.advertisedUrl === "string" ? input.advertisedUrl : null;
  if (advertised?.startsWith("wss://") && !advertised.includes(`//${input.pageHost}/`)) {
    return { kind: "advertised", url: advertised };
  }
  return { kind: "same-origin", url: input.sameOriginUrl };
}
