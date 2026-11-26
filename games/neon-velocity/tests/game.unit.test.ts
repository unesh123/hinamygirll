import { describe, expect, it } from "vitest";
import { createBikeState, respawnAtCheckpoint, stepBikePhysics } from "../src/physics/BikePhysics.ts";
import { appendProceduralChunks, generateLevel } from "../src/terrain/LevelGenerator.ts";
import { sampleTerrainAtX, SURFACE_TABLE } from "../src/terrain/TerrainSystem.ts";
import { SaveManager, sanitizeSaveState } from "../src/save/SaveManager.ts";
import type { InputSnapshot } from "../src/types/game.ts";

const IDLE_INPUT: InputSnapshot = {
  throttle: 0,
  brake: 0,
  lean: 0,
  jumpPressed: false,
  jumpHeld: false,
  boost: false,
};

describe("BikePhysics & TerrainSystem", () => {
  it("settles onto asphalt and accelerates forward under pedal throttle", () => {
    const world = generateLevel("training", 1337);
    const bike = createBikeState(40, 320);
    const dt = 1 / 120;

    for (let i = 0; i < 60; i++) {
      stepBikePhysics(bike, world, IDLE_INPUT, dt, i * dt, { x: 40, y: 360 });
    }
    expect(bike.rearContact.grounded || bike.frontContact.grounded).toBe(true);
    const startX = bike.x;

    for (let i = 0; i < 90; i++) {
      stepBikePhysics(bike, world, { ...IDLE_INPUT, throttle: 1 }, dt, (60 + i) * dt, { x: 40, y: 360 });
    }
    expect(bike.x).toBeGreaterThan(startX + 40);
    expect(bike.vx).toBeGreaterThan(140);
  });

  it("executes bunny-hop jump impulse cleanly from grounded state", () => {
    const world = generateLevel("training", 1337);
    const bike = createBikeState(40, 330);
    const dt = 1 / 120;
    for (let i = 0; i < 45; i++) {
      stepBikePhysics(bike, world, IDLE_INPUT, dt, i * dt, { x: 40, y: 360 });
    }
    const ev = stepBikePhysics(
      bike,
      world,
      { ...IDLE_INPUT, jumpPressed: true, jumpHeld: true },
      dt,
      0.5,
      { x: 40, y: 360 },
    );
    expect(ev.jumped).toBe(true);
    expect(bike.vy).toBeLessThan(-300);
  });

  it("distinguishes dirt vs asphalt grip & detects abyss falls", () => {
    expect(SURFACE_TABLE.dirt.grip).toBeLessThan(SURFACE_TABLE.asphalt.grip);
    const world = generateLevel("training", 1337);
    const bike = createBikeState(40, 1250);
    const ev = stepBikePhysics(bike, world, IDLE_INPUT, 1 / 120, 0.1, { x: 40, y: 360 });
    expect(ev.crashed).toBe(true);
    respawnAtCheckpoint(bike, { x: 240, y: 360 });
    expect(bike.crashed).toBe(false);
    expect(bike.x).toBe(240);
  });

  it("handles gaps without false ground collision and extends procedural chunks", () => {
    const world = generateLevel("free_ride", 42);
    const beforeCursor = world.proceduralCursorX;
    appendProceduralChunks(world, 2);
    expect(world.proceduralCursorX).toBeGreaterThan(beforeCursor);

    const training = generateLevel("training", 1337);
    const gapPoint = training.points.find((p) => p.gap);
    expect(gapPoint).toBeDefined();
    if (gapPoint) {
      const s = sampleTerrainAtX(training.points, gapPoint.x + 2, []);
      expect(s.exists).toBe(false);
    }
  });
});

describe("SaveManager persistence and corruption safety", () => {
  it("recovers cleanly from corrupt JSON and unlocks Sakura Strike at 6 cells", () => {
    const store = new Map<string, string>();
    const memoryStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    };
    memoryStorage.setItem("neon_velocity_save_v1", "{corrupted-json!!!");
    const mgr = new SaveManager(memoryStorage);
    expect(mgr.getState().unlockedLiveries).toEqual(["cyan_pulse"]);

    const res = mgr.recordRun({
      mode: "training",
      elapsedSec: 25.4,
      score: 1850,
      medal: "gold",
      cellsCollected: 6,
      starsCollected: 2,
      flipsDone: 1,
      ghost: [{ t: 0, x: 40, y: 310, angle: 0 }],
      completed: true,
    });
    expect(res.newBestTime).toBe(true);
    expect(res.newlyUnlocked).toContain("sakura_strike");

    const reloaded = new SaveManager(memoryStorage);
    expect(reloaded.getState().records.training.bestMedal).toBe("gold");
    expect(reloaded.getState().unlockedLiveries).toContain("sakura_strike");

    reloaded.resetProgress();
    expect(reloaded.getState().totalCells).toBe(0);
    expect(reloaded.getState().records.training.bestTimeSec).toBeNull();
    expect(sanitizeSaveState(null).version).toBe(1);
  });
});
