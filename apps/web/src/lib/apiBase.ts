/**
 * Decides where the web app sends API calls.
 *
 * An empty VITE_HINAA_API_BASE_URL makes every call relative, which on the
 * hosted site means the Vercel rewrite to a Cloudflare quick tunnel. Those
 * tunnels change on restart, so the sign-in gate reports "reconnecting" with
 * no cause. This keeps the empty-base case explicit so it can be reported.
 */

export type ApiBaseStatus =
  | { kind: "configured"; base: string }
  | { kind: "relative-dev" }
  | { kind: "relative-production"; reason: string };

export function resolveApiBase(raw: string | undefined, isProduction: boolean): ApiBaseStatus {
  const base = String(raw ?? "").trim().replace(/\/+$/, "");
  if (base) {
    if (isProduction && !base.startsWith("https://")) {
      return {
        kind: "relative-production",
        reason: "The API base URL must be an https:// address on the hosted site.",
      };
    }
    return { kind: "configured", base };
  }
  if (isProduction) {
    return {
      kind: "relative-production",
      reason: "No API base URL is set for this build, so requests go through the hosting route instead of the backend.",
    };
  }
  return { kind: "relative-dev" };
}
