import { describe, it, expect } from "vitest";
import { matchLocalActionIntent } from "./intentMatcher";

describe("HINA Action Engine — Fast Local Intent Matcher (< 80ms)", () => {
  it("matches 'split 2400 between 3' into a Split action card", () => {
    const draft = matchLocalActionIntent("split 2400 between 3");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("split");
    const data = draft?.fields.data as any;
    expect(data.totalAmount).toBe(2400);
    expect(data.peopleCount).toBe(3);
    expect(data.perPerson).toBe(800);
  });

  it("matches '2400 / 3' into a Split action card", () => {
    const draft = matchLocalActionIntent("2400 / 3");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("split");
    const data = draft?.fields.data as any;
    expect(data.totalAmount).toBe(2400);
    expect(data.peopleCount).toBe(3);
    expect(data.perPerson).toBe(800);
  });

  it("matches '25 min focus' into a Timer action card", () => {
    const draft = matchLocalActionIntent("25 min focus");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("timer.start");
    const data = draft?.fields.data as any;
    expect(data.durationSeconds).toBe(1500);
    expect(data.label).toContain("Focus");
  });

  it("matches 'dinner with priya friday 8pm' into an Event action card", () => {
    const draft = matchLocalActionIntent("dinner with priya friday 8pm");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("event.create");
    const data = draft?.fields.data as any;
    expect(data.title).toBe("Dinner");
    expect(data.participant).toBe("Priya");
    expect(data.dateStr).toBe("Friday");
    expect(data.timeStr).toBe("8:00 PM");
  });

  it("matches 'buy milk, eggs, bread and coffee' into a Checklist action card", () => {
    const draft = matchLocalActionIntent("buy milk, eggs, bread and coffee");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("checklist.create");
    const data = draft?.fields.data as any;
    expect(data.items.length).toBe(4);
    expect(data.items[0].text).toBe("Milk");
  });

  it("matches '3pm pst in ist' into a Timezone action card", () => {
    const draft = matchLocalActionIntent("3pm pst in ist");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("timezone.convert");
    const data = draft?.fields.data as any;
    expect(data.sourceTime).toBe("3PM");
    expect(data.sourceTz).toBe("PST");
    expect(data.targetTz).toBe("IST");
  });

  it("matches 'remind me to pay rent tomorrow urgent' into a Reminder action card", () => {
    const draft = matchLocalActionIntent("remind me to pay rent tomorrow urgent");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("reminder.create");
    const data = draft?.fields.data as any;
    expect(data.title).toBe("Pay rent");
    expect(data.isUrgent).toBe(true);
  });

  it("matches 'roll 2d6' into a Random roll action card", () => {
    const draft = matchLocalActionIntent("roll 2d6");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("random.roll");
    const data = draft?.fields.data as any;
    expect(data.diceCount).toBe(2);
    expect(data.diceSides).toBe(6);
    expect(data.rolls.length).toBe(2);
    expect(data.total).toBeGreaterThanOrEqual(2);
    expect(data.total).toBeLessThanOrEqual(12);
  });

  it("matches '#4AEDD9' into a Color inspector action card", () => {
    const draft = matchLocalActionIntent("#4AEDD9");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("color.inspect");
    const data = draft?.fields.data as any;
    expect(data.hex).toBe("#4AEDD9");
    expect(data.rgb).toContain("rgb(");
  });

  it("Law 5: 'Who is Mikasa?' stays chat and does NOT morph", () => {
    const draft = matchLocalActionIntent("Who is Mikasa?");
    expect(draft).toBeNull();
  });

  it("Law 5: 'Explain relativity' stays chat and does NOT morph", () => {
    const draft = matchLocalActionIntent("Explain relativity");
    expect(draft).toBeNull();
  });

  it("Law 5: 'hello hina' stays chat and does NOT morph", () => {
    const draft = matchLocalActionIntent("hello hina");
    expect(draft).toBeNull();
  });

  it("matches 'remind me tomorrow at 8 to call Alex' with extracted task and time", () => {
    const draft = matchLocalActionIntent("remind me tomorrow at 8 to call Alex");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("reminder.create");
    const data = draft?.fields.data as any;
    expect(data.title).toBe("Call Alex");
    expect(data.when).toBe("Tomorrow · 8:00 AM");
  });

  it("matches 'remind me at 8 pay rent' with extracted task and time", () => {
    const draft = matchLocalActionIntent("remind me at 8 pay rent");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("reminder.create");
    const data = draft?.fields.data as any;
    expect(data.title).toBe("Pay rent");
    expect(data.when).toBe("Today · 8:00 AM");
  });

  it("incomplete 'remind me at' stays null and does NOT open an empty broken card", () => {
    const draft = matchLocalActionIntent("remind me at");
    expect(draft).toBeNull();
  });

  it("matches 'generate a red mug' into an Image job action", () => {
    const draft = matchLocalActionIntent("generate a red mug");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("image.job");
    const data = draft?.fields.data as any;
    expect(data.prompt).toBe("A red mug");
    expect(data.stage).toBe("generating");
  });

  it("matches 'generate image of a red mug' into an Image job action", () => {
    const draft = matchLocalActionIntent("generate image of a red mug");
    expect(draft).not.toBeNull();
    expect(draft?.intent).toBe("image.job");
    const data = draft?.fields.data as any;
    expect(data.prompt).toBe("A red mug");
  });
});
