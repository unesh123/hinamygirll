import { beforeEach, describe, expect, it } from "vitest";
import { SETTINGS_KEY } from "../types/settings";
import { loadSettings } from "./settingsStore";

describe("CX provider default", () => {
  beforeEach(() => localStorage.clear());

  it("uses CX Gateway for a fresh local installation", () => {
    expect(loadSettings().provider.preferredMode).toBe("cx-gateway");
  });

  it("migrates a previously automatic installation to CX", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 1,
      appearance: {},
      provider: { preferredMode: "auto", preferredModelByProvider: {} },
    }));
    expect(loadSettings().provider.preferredMode).toBe("cx-gateway");
  });

  it("does not overwrite an explicit existing provider choice", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 1,
      appearance: {},
      provider: { preferredMode: "local", preferredModelByProvider: {} },
    }));
    expect(loadSettings().provider.preferredMode).toBe("local");
  });
});


describe("active language policy", () => {
  beforeEach(() => localStorage.clear());

  it("defaults existing version-two settings to Hindi and English auto mode", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 2,
      appearance: {},
      provider: { preferredMode: "mock", preferredModelByProvider: {} },
    }));
    const settings = loadSettings();
    expect(settings.provider.preferredMode).toBe("mock");
    expect(settings.language.activePolicy).toBe("auto-hi-en");
  });
});
