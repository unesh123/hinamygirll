import { describe, expect, it } from "vitest";
import { browserSpeechLocale, recognitionLocale, resolveConversationLocale } from "./languagePolicy";

describe("language routing", () => {
  it("keeps Nepali-English voice recognition in Nepali", () => {
    expect(recognitionLocale("ne-en")).toBe("ne-NP");
    expect(resolveConversationLocale("mero project explain gara", "ne-en")).toBe("ne-NP");
    expect(browserSpeechLocale("मेरो project तयार छ", "ne-en")).toBe("ne-NP");
  });
  it("distinguishes Nepali and Hindi markers instead of script alone", () => {
    expect(resolveConversationLocale("मलाई यो project बुझाउनुहोस्", "auto")).toBe("ne-NP");
    expect(resolveConversationLocale("मुझे यह project समझाओ", "auto")).toBe("hi-IN");
    expect(resolveConversationLocale("नमस्ते", "auto")).toBe("mixed");
    expect(resolveConversationLocale("mero project", "auto")).toBe("mixed");
  });
  it("honors explicit language choices", () => {
    expect(resolveConversationLocale("hello", "ne-NP")).toBe("ne-NP");
    expect(recognitionLocale("hi-en")).toBe("hi-IN");
    expect(recognitionLocale("en-US")).toBe("en-US");
  });
});
