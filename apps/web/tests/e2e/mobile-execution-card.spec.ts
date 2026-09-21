import { expect, test } from "@playwright/test";
import { isolateSettings } from "./helpers";

/**
 * The mobile complaint this guards: the execution/progress card used to be an
 * overlay pinned above the composer, so on a phone it sat on top of the
 * transcript and hid the messages it was describing. It must now flow inline
 * inside the scrolling transcript.
 */
function streamBody(): string {
  const lines = [
    {
      type: "agent.run.created",
      event: { event_type: "agent.run.created", run_id: "e2e-run", sequence: 1, payload: {} },
    },
    {
      type: "agent.planning.started",
      event: { event_type: "agent.planning.started", run_id: "e2e-run", sequence: 2, payload: {} },
    },
    {
      type: "agent.plan.ready",
      event: { event_type: "agent.plan.ready", run_id: "e2e-run", sequence: 3, payload: {} },
    },
    {
      type: "agent.step.started",
      event: {
        event_type: "agent.step.started",
        run_id: "e2e-run",
        sequence: 4,
        step_id: "answer",
        payload: { title: "Generate assistant response" },
      },
    },
    {
      type: "agent.step.completed",
      event: {
        event_type: "agent.step.completed",
        run_id: "e2e-run",
        sequence: 5,
        step_id: "answer",
        payload: { title: "Generate assistant response" },
      },
    },
    {
      type: "plan",
      plan: {
        spokenText: "Here is what I found.",
        displayText: "Here is what I found. The execution card belongs in this thread.",
        language: "en-US",
        emotion: { primary: "neutral", intensity: 0.5, valence: 0.5, arousal: 0.5 },
        performance: {
          facePreset: "neutral",
          gesture: "none",
          gazeTarget: "camera",
          headMotion: "none",
          blinkRate: 0.5,
        },
        memoryCandidates: [],
        toolRequests: [],
      },
    },
    { type: "text.delta", delta: "Here is what I found.", sequence: 6 },
    { type: "usage", latencyMs: 1234 },
  ];
  return lines.map((line) => `${JSON.stringify(line)}\n`).join("");
}

test.describe("Mobile execution card placement", () => {
  test("flows the execution card inside the transcript instead of over it", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    test.skip(test.info().project.name === "desktop-chromium", "Mobile-only geometry check.");
    await isolateSettings(page);
    await page.route("**/api/v1/conversations/turns:stream", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/x-ndjson",
        body: streamBody(),
      }),
    );
    // The mobile shell has no settings dialog; the default companion is enough
    // because this check measures layout, not the 3D model.
    await page.goto("/");
    await page.getByRole("textbox", { name: "Message HINAA" }).fill("What is the current state of hina?");
    await page.getByRole("button", { name: "Send Message (Enter)" }).click();

    const card = page.getByTestId("agent-activity-card");
    await expect(card).toBeVisible({ timeout: 15_000 });
    const transcript = page.locator(".hinaa-work-transcript");
    const composer = page.getByTestId("work-composer");

    // Structural: the card lives inside the scrolling thread.
    await expect(transcript.locator('[data-testid="agent-activity-card"]')).toHaveCount(1);

    // "relative" is fine — the card keeps its own paint layer. What breaks the
    // thread is a position that takes the element out of flow and paints it
    // over the composer.
    const isInFlow = (position: string) => !["fixed", "absolute", "sticky"].includes(position);

    const measure = () =>
      Promise.all([
        card.boundingBox(),
        card.evaluate((el) => ({
          clipped: el.scrollHeight - el.clientHeight,
          position: getComputedStyle(el).position,
        })),
        transcript.evaluate((el) => ({
          box: el.getBoundingClientRect(),
          gap: el.scrollHeight - el.scrollTop - el.clientHeight,
        })),
        composer.boundingBox(),
      ]);

    // The card clears itself roughly two seconds after the turn settles, so all
    // of its geometry has to be read in one pass once the thread has stopped.
    let latest!: Awaited<ReturnType<typeof measure>>;
    await expect
      .poll(
        async () => {
          latest = await measure();
          const [, cardState, transcriptState] = latest;
          if (!isInFlow(cardState.position)) return `position=${cardState.position}`;
          if (transcriptState.gap > 2) return `gap=${Math.round(transcriptState.gap)}`;
          if (cardState.clipped > 1) return `clip=${Math.round(cardState.clipped)}`;
          return "settled";
        },
        { timeout: 15_000, message: "thread never settled with the card fully visible" },
      )
      .toBe("settled");
    const [cardBox, cardState, transcriptState, composerBox] = latest;
    expect(cardBox).not.toBeNull();
    // The card participates in the thread's flow. The old overlay was pulled out
    // of the flow and painted over the composer.
    expect(isInFlow(cardState.position)).toBe(true);
    const transcriptBox = transcriptState.box;

    // The scrolling transcript is the box that must clear the composer, and the
    // card must fit inside it rather than being squashed by it.
    expect(transcriptBox.y + transcriptBox.height).toBeLessThanOrEqual(composerBox!.y + 1);
    expect(cardBox!.y + cardBox!.height).toBeLessThanOrEqual(transcriptBox.y + transcriptBox.height + 1);
    // And it stays inside the phone width — no horizontal overflow.
    const viewportWidth = page.viewportSize()!.width;
    expect(cardBox!.x).toBeGreaterThanOrEqual(transcriptBox.x - 1);
    expect(cardBox!.x + cardBox!.width).toBeLessThanOrEqual(viewportWidth + 1);

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);

    await page.screenshot({
      path: `test-results/mobile-execution-card-${test.info().project.name}.png`,
      fullPage: false,
    });
    // The composer used to claim 311px of a 727px phone screen, leaving ~230px
    // for the whole conversation. The cap is absolute because the composer is
    // the same component on every phone; shrinking it further on a 568px-tall
    // device would clip its own toolbar.
    const viewportHeight = page.viewportSize()!.height;
    expect(composerBox!.height).toBeLessThanOrEqual(220);
    // The thread must stay the dominant surface. The absolute floor a reviewer
    // would reach for (300px) is unreachable on the 320x568 device, where
    // 187px of that screen is top bar, work header and bottom nav.
    expect(transcriptBox.height).toBeGreaterThanOrEqual(viewportHeight * 0.3);
    // The reply itself is still reachable below the card.
    await expect(page.getByText(/execution card belongs in this thread/)).toBeVisible();
  });
});
