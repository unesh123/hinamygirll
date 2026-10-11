// Fails a hosted (production) build that has no https API backend configured.
// A build without one ships a sign-in gate that can only report "reconnecting".
// Run before `vite build` so the failure happens at deploy time, not in front of the owner.
// Rule mirrors src/lib/apiBase.ts; see scripts/check-hosted-api-base.test.mjs.

export function hostedApiBaseProblem(raw, isProduction) {
  const base = String(raw ?? "").trim().replace(/\/+$/, "");
  if (!isProduction) return null;
  if (!base) {
    return "VITE_HINAA_API_BASE_URL is not set for a production build. Set it to the https:// backend origin.";
  }
  if (!base.startsWith("https://")) {
    return `VITE_HINAA_API_BASE_URL must start with https:// for a production build (got "${base}").`;
  }
  return null;
}

const isMain = import.meta.url === `file://${process.argv[1].replace(/\\/g, "/")}`
  || process.argv[1]?.endsWith("check-hosted-api-base.mjs");

if (isMain) {
  const isProduction = process.env.NODE_ENV === "production" || process.argv.includes("--production");
  const problem = hostedApiBaseProblem(process.env.VITE_HINAA_API_BASE_URL, isProduction);
  if (problem) {
    console.error(`[check-hosted-api-base] ${problem}`);
    process.exit(1);
  }
  console.log("[check-hosted-api-base] API base OK for this build.");
}
