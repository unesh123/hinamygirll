/**
 * motionLedger — the frontend half of Hina's audit trail.
 *
 * Every companion state change (including the final `idle` after a reply is
 * delivered) is written to the backend run ledger, so the owner can prove from
 * the server that she really stopped instead of trusting the screen.
 *
 * The write is deliberately fire-and-forget: a ledger that is slow, down, or
 * misconfigured must never delay a turn or surface an error to the user.
 */

export const MOTION_LEDGER_ENDPOINT = "/api/v1/ledger/motion";

export function recordMotionState(state: string, detail?: string): void {
  try {
    if (typeof fetch !== "function") return;
    void fetch(MOTION_LEDGER_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // `keepalive` lets the last event of a closing page still land.
      keepalive: true,
      body: JSON.stringify({ state, detail: detail ?? null }),
    }).catch(() => undefined);
  } catch {
    // Never let auditing break the product.
  }
}
