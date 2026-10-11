import { describe, expect, it } from "vitest";
import { signedInGateCopy, signedOutGateCopy } from "./sessionGateCopy";

describe("signedInGateCopy", () => {
  it("names the backend when it cannot be reached, instead of a generic connecting line", () => {
    const copy = signedInGateCopy("offline");
    expect(copy.headline).toBe("Hina can't be reached");
    expect(copy.intro).toContain("can't reach Hina's backend");
    expect(copy.intro).not.toMatch(/Connecting to Hina/);
  });

  it("keeps the owner-access message for a denied account", () => {
    expect(signedInGateCopy("denied").intro).toContain("does not have owner access");
  });

  it("keeps the connecting copy while the access check runs", () => {
    expect(signedInGateCopy("checking").headlineSecond).toBe("Connecting to Hina.");
  });

  it("gives each failure its own headline", () => {
    const headlines = new Set([
      signedInGateCopy("offline").headline,
      signedInGateCopy("denied").headline,
      signedInGateCopy("checking").headline,
      signedOutGateCopy().headline,
    ]);
    expect(headlines.size).toBe(4);
  });
});
