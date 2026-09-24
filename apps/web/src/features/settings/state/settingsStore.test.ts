import { beforeEach, describe, expect, it } from "vitest";
import { SETTINGS_KEY } from "../types/settings";
import { loadSettings } from "./settingsStore";

describe("persisted brain preference", () => {
  beforeEach(() => localStorage.clear());

  it("defers to measured health on a fresh installation", () => {
    expect(loadSettings().provider.preferredMode).toBe("auto");
  });

  it("keeps the CX Gateway model to use once that gateway is healthy", () => {
    expect(loadSettings().provider.preferredModelByProvider["cx-gateway"]).toBe("cx/gpt-5.6-sol");
  });

  it("migrates an old automatic installation through the gateway pin back to auto", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 1,
      appearance: {},
      provider: { preferredMode: "auto", preferredModelByProvider: {} },
    }));
    expect(loadSettings().provider.preferredMode).toBe("auto");
  });

  it("un-pins the gateway choice written by the shipped version-8 build", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 8,
      appearance: {},
      provider: {
        preferredMode: "cx-gateway",
        preferredModelByProvider: { "cx-gateway": "cx/gpt-5.6-sol" },
      },
    }));
    const provider = loadSettings().provider;
    expect(provider.preferredMode).toBe("auto");
    expect(provider.preferredModelByProvider["cx-gateway"]).toBe("cx/gpt-5.6-sol");
  });

  it("does not overwrite an explicit existing provider choice", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 1,
      appearance: {},
      provider: { preferredMode: "local", preferredModelByProvider: {} },
    }));
    expect(loadSettings().provider.preferredMode).toBe("local");
  });

  it("leaves a Claude choice made on the current version alone", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 9,
      appearance: {},
      provider: { preferredMode: "claude", preferredModelByProvider: { claude: "claude-opus-4-6" } },
    }));
    expect(loadSettings().provider.preferredMode).toBe("claude");
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

describe("automation autonomy", () => {
  beforeEach(() => localStorage.clear());

  it("runs actions automatically on a fresh installation", () => {
    expect(loadSettings().automation.autoRunTools).toBe(true);
  });

  it("grants autonomy when migrating settings saved before the toggle existed", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 5,
      appearance: {},
      provider: { preferredMode: "claude", preferredModelByProvider: {} },
    }));
    expect(loadSettings().automation.autoRunTools).toBe(true);
  });

  it("keeps autonomy switched off when the user has disabled it", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 6,
      appearance: {},
      provider: { preferredMode: "claude", preferredModelByProvider: {} },
      automation: { autoRunTools: false },
    }));
    expect(loadSettings().automation.autoRunTools).toBe(false);
  });

  it("preserves a disabled choice made before the version bump", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 5,
      appearance: {},
      provider: { preferredMode: "claude", preferredModelByProvider: {} },
      automation: { autoRunTools: false },
    }));
    expect(loadSettings().automation.autoRunTools).toBe(false);
  });

  it("falls back to autonomy when the stored value is malformed", () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      _version: 6,
      appearance: {},
      provider: { preferredMode: "claude", preferredModelByProvider: {} },
      automation: { autoRunTools: "yes please" },
    }));
    expect(loadSettings().automation.autoRunTools).toBe(true);
  });
});
