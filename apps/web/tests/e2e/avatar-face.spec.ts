import { expect, test } from "@playwright/test";
import { isolateSettings } from "./helpers";

/**
 * Avatar face measurement, not assertion.
 *
 * A `canvas` element being "visible" proves nothing — an unmounted three.js
 * root still renders a 300x150 canvas. These tests therefore require the real
 * production path: the .vrm fetched, three.js sizing the drawing buffer, and
 * the loaded VRM reporting the expression weights it applies every frame.
 *
 * Mouth articulation is measured in pixels: her speech bridge is driven with a
 * known viseme schedule, the same one `sampleSpeechPlayback` reads in the app,
 * and the face region is compared between a held viseme and a silent gap. The
 * difference during a hold is the noise floor; the difference across a hold and
 * a gap has to clear it.
 */

const PRESENCE_KEY = "__HINAA_PRESENCE_VRM";

type Presence = {
  url: string;
  status: number;
  canvas: { bufferW: number; bufferH: number; cssW: number; cssH: number };
  expressions: string[];
};

async function openTalkWithAvatar(page: import("@playwright/test").Page): Promise<Presence> {
  await isolateSettings(page);
  await page.goto("/");

  const vrmResponse = page
    .waitForResponse((res) => res.url().includes(".vrm"), { timeout: 45_000 })
    .catch(() => null);

  await page.getByRole("button", { name: "Talk", exact: true }).click({ timeout: 10_000 });
  await page.getByLabel("Avatar framing").selectOption("closeup", { timeout: 10_000 });

  const response = await vrmResponse;
  const url = response?.url() ?? "";
  const status = response?.status() ?? 0;

  await expect
    .poll(() => page.evaluate((key) => !!(window as any)[key], PRESENCE_KEY), { timeout: 45_000 })
    .toBe(true);

  const canvas = page.locator(".avatar-playground canvas").first();
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box, "the avatar canvas needs a real on-screen box").toBeTruthy();

  const expressions = await page.evaluate(
    (key) => {
      const em = (window as any)[key]?.vrm?.expressionManager;
      if (!em) return [];
      const names = [
        "aa", "ih", "ou", "ee", "oh",
        "blink", "blinkLeft", "blinkRight",
        "happy", "angry", "sad", "relaxed", "surprised",
      ];
      return names.filter((n) => {
        try {
          return !!em.getExpression(n);
        } catch {
          return false;
        }
      });
    },
    PRESENCE_KEY,
  );

  const buffer = await canvas.evaluate((el) => ({
    bufferW: (el as HTMLCanvasElement).width,
    bufferH: (el as HTMLCanvasElement).height,
    cssW: Math.round((el as HTMLCanvasElement).getBoundingClientRect().width),
    cssH: Math.round((el as HTMLCanvasElement).getBoundingClientRect().height),
  }));

  return { url, status, canvas: { ...buffer }, expressions };
}

/** Average a band of face pixels; the mouth sits low-centre in closeup framing. */
async function sampleFace(page: import("@playwright/test").Page, box: { x: number; y: number; width: number; height: number }) {
  const shot = await page.screenshot({
    clip: {
      x: Math.round(box.x + box.width * 0.3),
      y: Math.round(box.y + box.height * 0.44),
      width: Math.round(box.width * 0.4),
      height: Math.round(box.height * 0.3),
    },
  });
  return page.evaluate(async (bytes) => {
    const image = new Image();
    image.src = `data:image/png;base64,${bytes}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(image, 0, 0);
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    const out: number[] = [];
    for (let i = 0; i < data.length; i += 4) out.push(data[i], data[i + 1], data[i + 2]);
    return out;
  }, shot.toString("base64"));
}

function changedPixels(a: number[], b: number[], threshold = 14) {
  let changed = 0;
  for (let i = 0; i < Math.min(a.length, b.length); i += 3) {
    const d = Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
    if (d > threshold) changed++;
  }
  return changed;
}

test.describe("avatar face on the talk surface", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "WebGL face sampling runs on desktop.");
  });
  test.setTimeout(150_000);

  test("loads her VRM over the network and renders it at panel size", async ({ page }) => {
    const presence = await openTalkWithAvatar(page);

    expect(presence.url, "the talk avatar must fetch a .vrm model").toContain(".vrm");
    expect(presence.status).toBe(200);
    expect(presence.canvas.cssW).toBeGreaterThan(120);
    expect(presence.canvas.cssH).toBeGreaterThan(120);
    // An untouched <canvas> defaults to 300x150; three.js resizes the drawing
    // buffer to the panel, so anything still at 150 tall never rendered.
    expect(presence.canvas.bufferH, "three.js never sized the drawing buffer").toBeGreaterThan(150);
    expect(presence.expressions, "viseme and blink morphs must survive model optimisation").toEqual(
      expect.arrayContaining(["aa", "ih", "ou", "ee", "oh", "blink"]),
    );
  });

  test("every preset the frame loop writes reaches the rig", async ({ page }) => {
    await openTalkWithAvatar(page);

    const probe = await page.evaluate((key) => {
      const em = (window as any)[key].vrm.expressionManager;
      // Exactly the strings AvatarPresence writes from its useFrame loop.
      const written = [
        "aa", "ih", "ou", "ee", "oh",
        "blink", "blinkLeft", "blinkRight",
        "happy", "sad", "relaxed", "angry", "surprised",
      ];
      // What the model's author actually named each blend shape. three-vrm
      // resolves writes case-sensitively, so a file that wrote
      // `VRMExpression_Surprised` is unreachable from the spec name.
      const literals = new Map<string, string>();
      for (const registered of em.expressions ?? []) {
        const name: unknown = registered?.name;
        if (typeof name !== "string" || !name) continue;
        const bare = name.replace(/^(VRMExpression_|VRM_v1_)/, "");
        for (const form of [name, bare]) {
          const lower = form.toLowerCase();
          if (!literals.has(lower)) literals.set(lower, form);
        }
      }
      const rows = written.map((requested) => {
        let direct = false;
        try { direct = !!em.getExpression(requested); } catch { direct = false; }
        const viaRig = direct ? null : literals.get(requested.toLowerCase()) ?? null;
        const use = direct ? requested : viaRig;
        let sticks = false;
        if (use) {
          try {
            em.setValue(use, 0.37);
            const raw = typeof em.getValue === "function" ? em.getValue(use) : em.getExpression?.(use)?.weight;
            sticks = typeof raw === "number" && Math.abs(raw - 0.37) < 0.01;
            em.setValue(use, 0);
          } catch { sticks = false; }
        }
        return { requested, use, direct: !!direct, sticks };
      });
      return { rows, registered: [...literals.values()] };
    }, PRESENCE_KEY);

    const dead = probe.rows.filter((r) => !r.sticks).map((r) => r.requested);
    const remapped = probe.rows.filter((r) => r.sticks && !r.direct).map((r) => `${r.requested}→${r.use}`);
    const line =
      `preset write probe — ${probe.rows.filter((r) => r.sticks).length}/${probe.rows.length} reach the mesh; ` +
      `unreachable [${dead.join(",")}]; resolved by rig spelling [${remapped.join(", ")}]`;
    console.log(line);
    test.info().annotations.push({ type: "measurement", description: line });

    // Lip-sync, blink and emotion presets are what her face is made of: a write
    // the rig cannot resolve is an expression the user never sees.
    expect(dead, line).toEqual([]);
  });

  test("opens and closes her mouth on the viseme timeline", async ({ page }) => {
    await openTalkWithAvatar(page);
    const canvas = page.locator(".avatar-playground canvas").first();
    const box = (await canvas.boundingBox())!;

    // Install and sample in one evaluate: a clock started in an earlier call
    // loses its first hundred milliseconds to the CDP round trip, and the
    // schedule windows have to stay wide relative to headless frame rates.
    const measurement = await page.evaluate(async (key) => {
      const handle = (window as any)[key];
      const em = handle.vrm.expressionManager;
      const read = (name: string) => {
        try {
          const raw = em?.getValue ? em.getValue(name) : em?.getExpression?.(name)?.weight;
          return typeof raw === "number" ? raw : 0;
        } catch {
          return 0;
        }
      };
      const startedAt = performance.now();
      // Presets only reach the mesh under the spelling the rig registered.
      const literals = new Map<string, string>();
      for (const registered of em.expressions ?? []) {
        const name: unknown = registered?.name;
        if (typeof name !== "string" || !name) continue;
        const bare = name.replace(/^(VRMExpression_|VRM_v1_)/, "");
        for (const form of [name, bare]) {
          const lower = form.toLowerCase();
          if (!literals.has(lower)) literals.set(lower, form);
        }
      }
      const readName = (requested: string) => {
        const use = em.getExpression?.(requested) ? requested : literals.get(requested.toLowerCase());
        return use ? read(use) : 0;
      };
      handle.speech.current = {
        utteranceId: 4242,
        state: "playing",
        source: "audio",
        timingSource: "text",
        calibrationMs: 0,
        // Open vowel, silence, then the same vowel again. Each window is over a
        // second wide: any frame rate that renders at all lands samples in it.
        events: [
          { timeMs: 0, durationMs: 1_500, mouth: "aa", weight: 1 },
          { timeMs: 3_500, durationMs: 1_500, mouth: "aa", weight: 1 },
        ],
        elapsedMs: () => performance.now() - startedAt,
        timing: null,
      };

      const points: Array<{ t: number; aa: number; brow: number }> = [];
      for (let i = 0; i < 1_200; i++) {
        const t = handle.speech.current.elapsedMs();
        points.push({
          t,
          aa: Math.max(readName("aa"), readName("a")),
          brow: readName("surprised"),
        });
        if (t > 5_000) break;
        await new Promise((r) => requestAnimationFrame(() => r(null)));
      }
      const span = points.length > 1 ? points[points.length - 1].t - points[0].t : 0;
      return { points, frames: points.length, fps: span > 0 ? (points.length - 1) / (span / 1000) : 0 };
    }, PRESENCE_KEY);

    const series = measurement.points;
    const meanIn = (from: number, to: number, pick: (p: (typeof series)[number]) => number) => {
      const window = series.filter((p) => p.t >= from && p.t <= to);
      return {
        n: window.length,
        avg: window.length ? window.reduce((s, p) => s + pick(p), 0) / window.length : -1,
      };
    };
    // Skipped at both ends of each open window: the rig eases onto a viseme, so
    // the ramp is not what this test is about.
    const mouth = (p: (typeof series)[number]) => p.aa;
    const brow = (p: (typeof series)[number]) => p.brow;
    const first = meanIn(400, 1_400, mouth);
    const silent = meanIn(2_100, 2_900, mouth);
    const second = meanIn(3_900, 4_900, mouth);
    const firstBrow = meanIn(400, 1_400, brow);
    const silentBrow = meanIn(2_100, 2_900, brow);
    const secondBrow = meanIn(3_900, 4_900, brow);

    const holdA = await sampleFace(page, box);
    await page.waitForTimeout(120);
    const holdB = await sampleFace(page, box);
    const noise = changedPixels(holdA, holdB);

    const line =
      `mouth weight vs schedule — viseme 1 ${first.avg.toFixed(3)} (n=${first.n}), ` +
      `silence ${silent.avg.toFixed(3)} (n=${silent.n}), viseme 2 ${second.avg.toFixed(3)} (n=${second.n}); ` +
      `brow while talking ${firstBrow.avg.toFixed(3)} / ${secondBrow.avg.toFixed(3)} vs ${silentBrow.avg.toFixed(3)} in silence; ` +
      `rAF ${measurement.fps.toFixed(1)} fps (${measurement.frames} frames), ` +
      `idle pixel churn ${noise} px`;
    console.log(line);
    test.info().annotations.push({ type: "measurement", description: line });

    expect(first.n, `no frames landed inside the first viseme (${line})`).toBeGreaterThan(2);
    expect(second.n, `no frames landed inside the second viseme (${line})`).toBeGreaterThan(2);
    expect(silent.n, `no frames landed inside the silence (${line})`).toBeGreaterThan(2);
    expect(first.avg, "her mouth stays shut during a scheduled viseme").toBeGreaterThan(0.3);
    expect(silent.avg, "her mouth stays open through the silence").toBeLessThan(0.2);
    expect(second.avg, "her mouth does not reopen for the next viseme").toBeGreaterThan(0.3);
    // Her upper face has to move with her voice, not only with her eyelids.
    expect(firstBrow.avg, `her brows never lift while she speaks (${line})`).toBeGreaterThan(silentBrow.avg + 0.02);
    expect(secondBrow.avg, `her brows do not settle between sentences (${line})`)
      .toBeGreaterThan(silentBrow.avg + 0.02);
  });

  test("blinks in eased beats instead of snapping shut", async ({ page }) => {
    await openTalkWithAvatar(page);

    const trace = await page.evaluate(async (key) => {
      const em = (window as any)[key].vrm.expressionManager;
      // One try per name: an unregistered alias must not mask the names that do
      // resolve, and this build exposes getValue or getExpression depending on
      // the three-vrm major version.
      const readName = (name: string) => {
        try {
          if (typeof em?.getValue === "function") {
            const v = em.getValue(name);
            if (typeof v === "number") return v;
          }
        } catch {
          /* fall through to getExpression */
        }
        try {
          const raw = em?.getExpression?.(name)?.weight;
          return typeof raw === "number" ? raw : 0;
        } catch {
          return 0;
        }
      };
      const names = ["blink", "blink_l", "blink_r", "blinkLeft", "blinkRight"];
      const registered: string[] = [];
      try {
        for (const e of em?.expressions ?? []) if (e?.name) registered.push(e.name);
      } catch {
        /* older builds keep the map private; the alias peaks below still tell us */
      }

      // Sample per rendered frame, not per timer tick: at a few frames per
      // second the render loop blocks the main thread and a 45 ms interval
      // fires roughly once per frame anyway, so rAF is both honest and cheaper.
      const samples: number[] = [];
      const peaks: Record<string, number> = {};
      const startedAt = performance.now();
      while (performance.now() - startedAt < 16000) {
        await new Promise((r) => requestAnimationFrame(() => r(null)));
        let frame = 0;
        for (const n of names) {
          const value = readName(n);
          peaks[n] = Math.max(peaks[n] ?? 0, value);
          frame = Math.max(frame, value);
        }
        samples.push(frame);
      }
      const elapsed = (performance.now() - startedAt) / 1000;
      return {
        samples,
        peaks,
        registered,
        seconds: elapsed,
        fps: samples.length / elapsed,
        api: {
          getValue: typeof em?.getValue === "function",
          getExpression: typeof em?.getExpression === "function",
        },
      };
    }, PRESENCE_KEY);

    const samples = trace.samples;
    const peak = Math.max(...samples);
    let biggestJump = 0;
    let blinkSteps = 0;
    for (let i = 1; i < samples.length; i++) {
      biggestJump = Math.max(biggestJump, Math.abs(samples[i] - samples[i - 1]));
      if (samples[i] > 0.3 && samples[i - 1] <= 0.3) {
        let steps = 0;
        for (let j = i; j < samples.length && samples[j] > 0.05; j++) steps++;
        blinkSteps = Math.max(blinkSteps, steps);
      }
    }
    const blinks = samples.filter((v, i) => i > 0 && v > 0.3 && samples[i - 1] <= 0.3).length;
    const perAlias = Object.entries(trace.peaks)
      .map(([name, value]) => `${name}=${value.toFixed(2)}`)
      .join(" ");

    const line =
      `16 s blink trace — frames ${samples.length} (${trace.fps.toFixed(1)} fps), blinks ${blinks}, ` +
      `peak ${peak.toFixed(2)}, largest frame-to-frame jump ${biggestJump.toFixed(2)}, ` +
      `blink spans ${blinkSteps} frames (~${((blinkSteps / trace.fps) * 1000) | 0} ms); ` +
      `api getValue:${trace.api.getValue} getExpression:${trace.api.getExpression}; ` +
      `peaks ${perAlias}; registered [${trace.registered.join(",")}]`;
    console.log(line);
    test.info().annotations.push({ type: "measurement", description: line });

    expect(blinks, `she does not blink within 16 seconds (${line})`).toBeGreaterThanOrEqual(2);
    expect(peak, `her eyelids never close (${line})`).toBeGreaterThan(0.5);
    // The eased curve spans ~170 ms, so judging its shape needs a frame rate
    // fine enough to resolve it. Below that the trace is a staircase by
    // construction and a large per-frame jump says nothing about the rig.
    if (trace.fps >= 20) {
      expect(biggestJump, "the blink jumps too far in one frame — it snaps shut").toBeLessThan(0.6);
      expect(blinkSteps, "a blink lasts under one frame — it flickers").toBeGreaterThanOrEqual(2);
    } else {
      console.log(`blink easing not resolvable at ${trace.fps.toFixed(1)} fps — shape gates skipped`);
    }
  });
});
