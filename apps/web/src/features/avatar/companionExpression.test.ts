import { describe, expect, it } from "vitest";
import {
  expressionIntentFor,
  parseExpressionSegments,
  getTemporalIntent,
  computeAffectiveProfile,
  computeDirectMorphTargets,
} from "./companionExpression";

describe("companion expression director", () => {
  it("selects a warm celebratory accent from HINAA's reply text", () => {
    expect(expressionIntentFor("Congratulations, I am proud of you!", "speaking")).toBe("celebratory");
    expect(expressionIntentFor("कमाल, बहुत अच्छा किया।", "speaking")).toBe("celebratory");
  });

  it("selects empathy and concern without camera analysis", () => {
    expect(expressionIntentFor("I understand. I am here with you.", "speaking")).toBe("empathetic");
    expect(expressionIntentFor("There was an error, but we can retry safely.", "error")).toBe("concerned");
  });

  it("selects rich anime emotional expressions across diverse situations", () => {
    expect(expressionIntentFor("Hahaha that is so hilarious! 😂", "speaking")).toBe("laughing");
    expect(expressionIntentFor("Just kidding, you silly! 😉", "speaking")).toBe("playful");
    expect(expressionIntentFor("Hey darling, you look adorable today 🥰", "speaking")).toBe("flirty_warm");
    expect(expressionIntentFor("Hmph! That's not fair at all 😤", "speaking")).toBe("pouting");
    expect(expressionIntentFor("Whoa, that is unbelievable! 😲", "speaking")).toBe("surprised");
    expect(expressionIntentFor("I wonder what will happen next?", "speaking")).toBe("curious");
    expect(expressionIntentFor("Hmm, let's see how this works...", "speaking")).toBe("thinking");
    expect(expressionIntentFor("Leave it to me, I got this! 😎", "speaking")).toBe("confident");
    expect(expressionIntentFor("I'm so happy and delightful! 💖", "speaking")).toBe("joyful");
  });

  it("honours assistant plan explicit emotion overrides", () => {
    expect(expressionIntentFor("General message", "speaking", "playful")).toBe("playful");
    expect(expressionIntentFor("General message", "speaking", "excited")).toBe("excited");
    expect(expressionIntentFor("General message", "speaking", "thinking")).toBe("thinking");
  });

  it("selects the extended emotional range a real face actually has", () => {
    expect(expressionIntentFor("I'm so excited, I can't wait! 🤩", "speaking")).toBe("excited");
    expect(expressionIntentFor("Don't look at me, I'm blushing 😳", "speaking")).toBe("shy");
    expect(expressionIntentFor("I really miss you... 💔", "speaking")).toBe("sad");
    expect(expressionIntentFor("Thank you so much for everything 🙏", "speaking")).toBe("grateful");
    expect(expressionIntentFor("We will finish this, no matter what 🔥", "speaking")).toBe("determined");
    expect(expressionIntentFor("Told you it would work 😼", "speaking")).toBe("smug");
    expect(expressionIntentFor("I'm a little nervous about this 😬", "speaking")).toBe("nervous");
    expect(expressionIntentFor("I'm so sleepy, time to rest 😴", "speaking")).toBe("sleepy");
    expect(expressionIntentFor("That view is breathtaking 🌌", "speaking")).toBe("awe");
  });

  it("computes extended affective profiles for the new archetypes", () => {
    const sleepy = computeAffectiveProfile("I'm so sleepy 😴", "speaking");
    expect(sleepy.scenarioArchetype).toBe("serene_cozy");
    expect(sleepy.drowsy).toBeGreaterThan(0.5);

    const sad = computeAffectiveProfile("I really miss you... 💔", "speaking");
    expect(sad.scenarioArchetype).toBe("melancholy_soft");
    expect(sad.valence).toBeLessThan(0);

    const morphs = computeDirectMorphTargets(sleepy, 1.0, 0, false);
    expect(morphs.Fcl_EYE_Close).toBeGreaterThan(0.2);
    expect(morphs.Fcl_EYE_Sorrow).toBe(0);
    const sadMorphs = computeDirectMorphTargets(sad, 1.0, 0, false);
    expect(sadMorphs.Fcl_EYE_Sorrow).toBeGreaterThan(0.1);
  });

  it("uses a warm neutral conversational presence when no cue is present", () => {
    expect(expressionIntentFor("", "listening")).toBe("warm");
    expect(expressionIntentFor("", "idle")).toBe("neutral");
  });

  it("splits multi-sentence text into dynamic emotional temporal segments", () => {
    const text = "Hahaha that is so hilarious! 😂 What do you think we should do next? I am sure we will succeed! 😎";
    const segments = parseExpressionSegments(text, "speaking");
    expect(segments.length).toBe(3);
    expect(segments[0].intent).toBe("laughing");
    expect(segments[1].intent).toBe("curious");
    expect(segments[2].intent).toBe("confident");

    // Progress at beginning resolves first sentence
    expect(getTemporalIntent(segments, 0.1)).toBe("laughing");
    // Progress midway resolves second sentence
    expect(getTemporalIntent(segments, 0.5)).toBe("curious");
    // Progress near end resolves third sentence
    expect(getTemporalIntent(segments, 0.95)).toBe("confident");
  });

  it("computes continuous affective profiles with non-repeating scenario hashes and micro-asymmetry", () => {
    const profile1 = computeAffectiveProfile("Hey babe, I love you so much! 🥰", "speaking");
    const profile2 = computeAffectiveProfile("What if we refactor this algorithm completely? 🤔", "speaking");

    // Dimensions differ across scenarios
    expect(profile1.warmth).toBeGreaterThan(0.7);
    expect(profile1.valence).toBeGreaterThan(0.5);
    expect(profile2.thoughtfulness).toBeGreaterThan(0.6);
    expect(profile2.surprise).toBeGreaterThan(0.4);

    // Hashes are distinct and deterministic
    expect(profile1.scenarioHash).not.toBe(profile2.scenarioHash);
    expect(typeof profile1.browAsymmetry).toBe("number");
    expect(typeof profile1.mouthAsymmetry).toBe("number");
  });

  it("computes high-level morph targets including asymmetric eyes, mouth smirks, and cute fang peek", () => {
    const profile = computeAffectiveProfile("Just kidding, you silly! 😉", "speaking");
    const morphs = computeDirectMorphTargets(profile, 1.5, 0.6, true);

    expect(morphs.Fcl_EYE_Joy).toBeGreaterThan(0.2);
    expect(morphs.Fcl_MTH_Up).toBeGreaterThan(0.3);
    expect(morphs.Fcl_MTH_SkinFung_R).toBeGreaterThanOrEqual(0);
    expect(morphs.Fcl_EYE_Joy_R).toBeGreaterThan(0);
    expect(morphs.Fcl_EYE_Joy_L).toBeGreaterThan(0);
  });

  it("classifies 'Perfect, okay, bro' as casual_bro with relaxed warmth and zero surprise", () => {
    const profile = computeAffectiveProfile("Perfect, okay, bro, let's do this!", "speaking", undefined, 0, true);
    expect(profile.scenarioArchetype).toBe("casual_bro");
    expect(profile.surprise).toBe(0);
    expect(profile.confidence).toBeGreaterThan(0.7);
    expect(profile.warmth).toBeGreaterThan(0.6);
    expect(profile.headNodBias).toBeGreaterThan(0.05);

    const morphs = computeDirectMorphTargets(profile, 1.0, 0.4, true);
    expect(morphs.Fcl_EYE_Surprised).toBe(0);
    expect(morphs.Fcl_HA_Fung1).toBe(0);
    expect(morphs.Fcl_MTH_Up).toBeGreaterThan(0.2);
  });

  it("relaxes gracefully into living idle with zero wide eyes, zero tooth gaps, and zero fang holes", () => {
    const profile = computeAffectiveProfile("Hey babe, I'm right here. Kya chal raha hai?", "idle", undefined, 0, false);
    expect(profile.surprise).toBe(0);
    expect(profile.arousal).toBeLessThanOrEqual(0.25);
    expect(profile.fangBias).toBe(0);

    const morphs = computeDirectMorphTargets(profile, 2.0, 0, false);
    expect(morphs.Fcl_EYE_Surprised).toBe(0);
    expect(morphs.Fcl_HA_Fung1).toBe(0);
    expect(morphs.Fcl_MTH_SkinFung).toBe(0);
    expect(morphs.Fcl_MTH_SkinFung_R).toBe(0);
    expect(morphs.Fcl_MTH_SkinFung_L).toBe(0);
    // Mouth rests in gentle, soft closed smile
    expect(morphs.Fcl_MTH_Up).toBeGreaterThan(0.1);
    expect(morphs.Fcl_MTH_Up).toBeLessThan(0.2);
  });

  it("never repeats identical micro-acting across deliveries of the same line", () => {
    const args = ["ok bro, perfect, let's go!", "speaking", undefined, 0.4, true] as const;
    const first = computeAffectiveProfile(...args, 0);

    // 25 redeliveries of the exact same line all act differently
    for (let occurrence = 1; occurrence <= 25; occurrence++) {
      expect(computeAffectiveProfile(...args, occurrence)).not.toEqual(first);
    }

    // ...while a fixed occurrence stays perfectly reproducible (replay-stable)
    expect(computeAffectiveProfile(...args, 7)).toEqual(computeAffectiveProfile(...args, 7));
  });
});


