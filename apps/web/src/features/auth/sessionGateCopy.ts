/**
 * Copy for the sign-in gate's signed-in states. Pure, so the wording for each
 * failure is tested and the screen never shows a generic "connecting" when the
 * backend is actually unreachable.
 */

export type GateAccess = "checking" | "allowed" | "denied" | "offline";

export type GateCopy = {
  headline: string;
  headlineSecond: string;
  intro: string;
};

export function signedInGateCopy(access: GateAccess): GateCopy {
  if (access === "denied") {
    return {
      headline: "Your workspace",
      headlineSecond: "stays private.",
      intro: "This account does not have owner access. Switch to the owner account, or retry after access is configured.",
    };
  }
  if (access === "offline") {
    return {
      headline: "Hina can't be reached",
      headlineSecond: "right now.",
      intro: "Your sign-in is fine, but this site can't reach Hina's backend. Retry in a moment; if it keeps failing, the backend needs to be started or configured.",
    };
  }
  return {
    headline: "Almost there.",
    headlineSecond: "Connecting to Hina.",
    intro: "Think, create, and build with Hina. Your conversations, memories, and projects stay behind your sign-in.",
  };
}

export function signedOutGateCopy(): GateCopy {
  return {
    headline: "A little closer.",
    headlineSecond: "A lot more possible.",
    intro: "Think, create, and build with Hina. Your conversations, memories, and projects stay behind your sign-in.",
  };
}
