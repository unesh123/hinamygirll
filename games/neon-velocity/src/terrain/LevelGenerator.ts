import type {
  BreakableProp,
  Checkpoint,
  Collectible,
  GameMode,
  HazardZone,
  LevelConfig,
  MovingPlatform,
  SurfaceType,
  TerrainPoint,
} from "../types/game.ts";

export interface GeneratedWorld {
  config: LevelConfig;
  points: TerrainPoint[];
  platforms: MovingPlatform[];
  props: BreakableProp[];
  hazards: HazardZone[];
  checkpoints: Checkpoint[];
  collectibles: Collectible[];
  seed: number;
  proceduralCursorX: number;
  proceduralLastY: number;
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

class TrackBuilder {
  points: TerrainPoint[] = [];
  platforms: MovingPlatform[] = [];
  props: BreakableProp[] = [];
  hazards: HazardZone[] = [];
  checkpoints: Checkpoint[] = [];
  collectibles: Collectible[] = [];
  cursorX = -160;
  cursorY = 360;
  private idCounter = 1;

  constructor(startX = -160, startY = 360) {
    this.cursorX = startX;
    this.cursorY = startY;
    this.points.push({ x: startX, y: startY, surface: "asphalt" });
  }

  private nextId(prefix: string): string {
    return `${prefix}-${this.idCounter++}`;
  }

  addSegment(len: number, deltaY: number, surface: SurfaceType, steps = 1, tunnelRoofOffset?: number): void {
    const startX = this.cursorX;
    const startY = this.cursorY;
    for (let i = 1; i <= steps; i++) {
      const t = i / steps;
      const smooth = steps > 1 ? t * t * (3 - 2 * t) : t;
      const nx = startX + len * t;
      const ny = startY + deltaY * smooth;
      this.points.push({
        x: nx,
        y: ny,
        surface,
        tunnelRoofY: tunnelRoofOffset !== undefined ? ny - tunnelRoofOffset : null,
      });
    }
    this.cursorX = startX + len;
    this.cursorY = startY + deltaY;
  }

  addRamp(len: number, liftY: number, surface: SurfaceType = "wood_ramp"): void {
    const startX = this.cursorX;
    const startY = this.cursorY;
    const sub = 6;
    for (let i = 1; i <= sub; i++) {
      const t = i / sub;
      const ease = t * t;
      this.points.push({
        x: startX + len * t,
        y: startY - liftY * ease,
        surface,
      });
    }
    this.cursorX = startX + len;
    this.cursorY = startY - liftY;
  }

  addStairs(stepsCount: number, stepWidth: number, stepHeight: number): void {
    for (let i = 0; i < stepsCount; i++) {
      this.points.push({ x: this.cursorX + stepWidth * 0.72, y: this.cursorY, surface: "stairs" });
      this.cursorY += stepHeight;
      this.cursorX += stepWidth;
      this.points.push({ x: this.cursorX, y: this.cursorY, surface: "stairs" });
    }
  }

  addGap(gapWidth: number, landingDropY = 24, landingSurface: SurfaceType = "asphalt"): void {
    const gapStartX = this.cursorX + 4;
    const gapEndX = this.cursorX + gapWidth;
    const landY = this.cursorY + landingDropY;
    this.points.push({ x: gapStartX, y: this.cursorY + 260, surface: landingSurface, gap: true });
    this.points.push({ x: gapEndX - 4, y: landY + 260, surface: landingSurface, gap: true });
    this.points.push({ x: gapEndX, y: landY, surface: landingSurface });
    this.cursorX = gapEndX;
    this.cursorY = landY;
  }

  addCollectibleArc(startX: number, baseY: number, count: number, spacing = 55, arcHeight = 85): void {
    for (let i = 0; i < count; i++) {
      const t = count === 1 ? 0.5 : i / (count - 1);
      const yOffset = Math.sin(t * Math.PI) * arcHeight + 34;
      this.collectibles.push({
        id: this.nextId("col"),
        x: startX + i * spacing,
        y: baseY - yOffset,
        kind: i === Math.floor(count / 2) ? "star" : "cell",
        collected: false,
        bobPhase: i * 0.7,
      });
    }
  }

  addProp(xOffset: number, kind: BreakableProp["kind"]): void {
    const size = kind === "crate" ? { w: 34, h: 34 } : kind === "barrier" ? { w: 22, h: 48 } : { w: 18, h: 24 };
    this.props.push({
      id: this.nextId("prop"),
      x: this.cursorX + xOffset,
      y: this.cursorY - size.h,
      width: size.w,
      height: size.h,
      kind,
      broken: false,
      breakTimer: 0,
    });
  }

  addHazard(xOffset: number, width: number, kind: HazardZone["kind"]): void {
    this.hazards.push({
      id: this.nextId("haz"),
      x: this.cursorX + xOffset,
      y: this.cursorY - 14,
      width,
      height: 14,
      kind,
    });
  }

  addCheckpoint(): void {
    this.checkpoints.push({
      id: this.nextId("cp"),
      index: this.checkpoints.length,
      x: this.cursorX,
      y: this.cursorY,
      triggered: false,
    });
  }

  addMovingPlatform(width: number, surface: SurfaceType, ampX: number, ampY: number, speed: number): void {
    this.platforms.push({
      id: this.nextId("plat"),
      x: this.cursorX,
      y: this.cursorY,
      width,
      height: 18,
      baseX: this.cursorX,
      baseY: this.cursorY,
      ampX,
      ampY,
      speed,
      phase: 0,
      surface,
    });
  }
}

export const MODE_CONFIGS: Record<GameMode, LevelConfig> = {
  training: {
    mode: "training",
    title: "01 // Neon Training Yard",
    subtitle: "Learn pedal drive, wheelies, stairs, smash crates, and ramp hops",
    finishX: 4300,
    fallY: 1150,
    goldSeconds: 28,
    silverSeconds: 38,
    bronzeSeconds: 52,
    defaultTimeOfDay: "evening",
    defaultWeather: "clear",
    tutorialHints: [
      { xStart: -80, xEnd: 520, text: "Hold W / UP to Pedal • Hold S / DOWN to Brake" },
      { xStart: 560, xEnd: 1350, text: "Hold A / LEFT for Wheelie • D / RIGHT to Tuck Forward" },
      { xStart: 1360, xEnd: 2250, text: "Press SPACE to Bunny Hop onto stairs and crates!" },
      { xStart: 2280, xEnd: 3500, text: "Hold SHIFT for Nitro Boost across the rooftop gap!" },
    ],
  },
  free_ride: {
    mode: "free_ride",
    title: "02 // Endless Skyline Corridor",
    subtitle: "Seeded procedural cityscapes: rooftops, beams, dirt tracks, tunnels & bridges",
    finishX: null,
    fallY: 1200,
    goldSeconds: 90,
    silverSeconds: 60,
    bronzeSeconds: 30,
    defaultTimeOfDay: "night",
    defaultWeather: "neon_fog",
    tutorialHints: [
      { xStart: -80, xEnd: 480, text: "Infinite Skyline Run — chain wheelies, flips & cells!" },
    ],
  },
  time_trial: {
    mode: "time_trial",
    title: "03 // Rainy Time Trial",
    subtitle: "Fast technical neon sprint against your TAB Ghost Replay",
    finishX: 6800,
    fallY: 1150,
    goldSeconds: 36,
    silverSeconds: 47,
    bronzeSeconds: 62,
    defaultTimeOfDay: "night",
    defaultWeather: "rain",
    tutorialHints: [
      { xStart: -80, xEnd: 600, text: "Press TAB anytime to toggle Ghost Rider" },
    ],
  },
  challenge: {
    mode: "challenge",
    title: "04 // Sky-Beam Gauntlet",
    subtitle: "Elevated construction girders, elevator lifts, and electric hazards",
    finishX: 7200,
    fallY: 1150,
    goldSeconds: 42,
    silverSeconds: 56,
    bronzeSeconds: 75,
    defaultTimeOfDay: "day",
    defaultWeather: "clear",
    tutorialHints: [
      { xStart: -80, xEnd: 600, text: "Feather throttle over girders • Watch electric strips!" },
    ],
  },
};

export function generateLevel(mode: GameMode, seed = 1337): GeneratedWorld {
  const b = new TrackBuilder(-180, 360);
  const config = MODE_CONFIGS[mode];

  if (mode === "training") {
    b.addSegment(620, 0, "asphalt", 4);
    b.addCheckpoint();
    b.addCollectibleArc(320, 360, 3, 60, 36);
    b.addSegment(340, -24, "asphalt", 4);
    b.addRamp(180, 72, "wood_ramp");
    b.addGap(175, 44, "rooftop");
    b.addCollectibleArc(1010, 340, 3, 55, 80);
    b.addSegment(380, 0, "rooftop", 4);
    b.addProp(-180, "crate");
    b.addProp(-90, "cone");
    b.addCheckpoint();
    b.addStairs(7, 46, 18);
    b.addSegment(440, 0, "dirt", 6);
    b.addCollectibleArc(2050, 445, 4, 52, 42);
    b.addSegment(460, 0, "tunnel", 4, 138);
    b.addCheckpoint();
    b.addRamp(220, 96, "wood_ramp");
    b.addGap(220, 56, "bridge");
    b.addCollectibleArc(3160, 340, 4, 58, 98);
    b.addSegment(540, 12, "bridge", 6);
    b.addSegment(520, 0, "asphalt", 3);
  } else if (mode === "time_trial") {
    b.addSegment(480, 0, "asphalt", 3);
    b.addSegment(420, 58, "asphalt", 6); // Fast downhill acceleration
    b.addRamp(210, 88, "wood_ramp");
    b.addGap(220, 40, "rooftop");
    b.addCollectibleArc(940, 365, 4, 54, 92);
    b.addSegment(480, 0, "rooftop", 4);
    b.addProp(-140, "crate");
    b.addCheckpoint();
    b.addStairs(8, 42, 16);
    b.addSegment(520, -28, "tunnel", 6, 132);
    b.addSegment(420, 44, "dirt", 6);
    b.addCheckpoint();
    b.addRamp(240, 110, "wood_ramp");
    b.addGap(260, 74, "beam");
    b.addCollectibleArc(3320, 355, 5, 52, 115);
    b.addSegment(620, 0, "beam", 4);
    b.addHazard(-320, 92, "spikes");
    b.addCheckpoint();
    b.addSegment(540, 68, "asphalt", 6);
    b.addRamp(200, 82, "wood_ramp");
    b.addGap(210, 46, "bridge");
    b.addSegment(760, -18, "bridge", 8);
    b.addProp(-280, "barrier");
    b.addSegment(700, 0, "asphalt", 4);
  } else if (mode === "challenge") {
    b.addSegment(440, 0, "asphalt", 3);
    b.addRamp(180, 76, "wood_ramp");
    b.addGap(190, 24, "beam");
    b.addSegment(420, 0, "beam", 4);
    b.addProp(-120, "barrier");
    b.addCheckpoint();
    // Moving elevator gap!
    b.addGap(70, 0, "beam");
    b.addMovingPlatform(190, "beam", 0, -72, 1.85);
    b.addGap(220, -45, "rooftop");
    b.addCollectibleArc(1320, 240, 4, 56, 85);
    b.addSegment(520, 0, "rooftop", 5);
    b.addHazard(-250, 96, "electric");
    b.addCheckpoint();
    b.addStairs(9, 44, 18);
    b.addSegment(480, 20, "dirt", 6);
    b.addHazard(-220, 88, "spikes");
    b.addRamp(230, 108, "wood_ramp");
    b.addGap(250, 50, "tunnel");
    b.addSegment(620, 0, "tunnel", 4, 134);
    b.addCheckpoint();
    b.addSegment(340, -18, "beam", 3);
    // Horizontal ferry bridge
    b.addGap(40, 0, "beam");
    b.addMovingPlatform(210, "bridge", 110, 0, 1.45);
    b.addGap(270, 12, "bridge");
    b.addSegment(640, 0, "bridge", 6);
    b.addProp(-240, "crate");
    b.addSegment(640, 0, "asphalt", 4);
  } else {
    // Free Ride curated opener before procedural extension takes over seamlessly
    b.addSegment(560, 0, "asphalt", 4);
    b.addRamp(190, 78, "wood_ramp");
    b.addGap(180, 32, "rooftop");
    b.addSegment(460, 0, "rooftop", 4);
    b.addProp(-140, "crate");
    b.addCheckpoint();
    b.addStairs(6, 46, 17);
    b.addSegment(480, 0, "dirt", 6);
  }

  const world: GeneratedWorld = {
    config,
    points: b.points,
    platforms: b.platforms,
    props: b.props,
    hazards: b.hazards,
    checkpoints: b.checkpoints,
    collectibles: b.collectibles,
    seed,
    proceduralCursorX: b.cursorX,
    proceduralLastY: b.cursorY,
  };

  if (mode === "free_ride") {
    appendProceduralChunks(world, 4);
  }
  return world;
}

export function appendProceduralChunks(world: GeneratedWorld, chunkCount = 2): void {
  const rand = mulberry32(world.seed + Math.floor(world.proceduralCursorX));
  const b = new TrackBuilder(world.proceduralCursorX, world.proceduralLastY);
  b.points = []; // only append newly generated points cleanly

  for (let c = 0; c < chunkCount; c++) {
    const archetype = Math.floor(rand() * 6);
    if (archetype === 0) {
      // Skyline rooftop hop
      b.addRamp(190 + rand() * 50, 74 + rand() * 34, "wood_ramp");
      b.addGap(180 + rand() * 80, 26, "rooftop");
      b.addCollectibleArc(b.cursorX - 130, b.cursorY - 25, 3, 52, 75);
      b.addSegment(440 + rand() * 140, (rand() - 0.5) * 40, "rooftop", 5);
      if (rand() > 0.35) b.addProp(-140, "crate");
    } else if (archetype === 1) {
      // Construction girder & moving platform
      b.addSegment(340, -18, "beam", 4);
      b.addGap(45, 0, "beam");
      b.addMovingPlatform(185, "beam", 0, -52, 1.6 + rand() * 0.6);
      b.addGap(220, 0, "asphalt");
      b.addSegment(360, 12, "asphalt", 4);
    } else if (archetype === 2) {
      // Subway tunnel run
      b.addSegment(220, 56, "asphalt", 5);
      b.addSegment(560, 0, "tunnel", 5, 136);
      b.addCollectibleArc(b.cursorX - 360, b.cursorY - 12, 3, 75, 28);
      b.addSegment(240, -48, "asphalt", 5);
    } else if (archetype === 3) {
      // Dirt pump park + rolling hills
      b.addSegment(320, -42, "dirt", 6);
      b.addSegment(340, 64, "dirt", 6);
      b.addSegment(320, -28, "dirt", 6);
      if (rand() > 0.45) b.addHazard(-160, 82, "spikes");
    } else if (archetype === 4) {
      // Urban stairs into cable bridge
      b.addStairs(6 + Math.floor(rand() * 4), 44, 16);
      b.addSegment(540, -24, "bridge", 6);
      b.addProp(-200, "cone");
    } else {
      // High-speed asphalt boost zone + breakable barrier
      b.addSegment(580, 48, "asphalt", 6);
      b.addProp(-220, "barrier");
      b.addRamp(210, 96, "wood_ramp");
      b.addGap(210, 44, "asphalt");
      b.addSegment(320, 0, "asphalt", 3);
    }
    b.addCheckpoint();
    // Clamp vertical band so procedural terrain stays inside comfortable camera corridor
    if (b.cursorY > 560) {
      b.addSegment(280, -140, "asphalt", 5);
    } else if (b.cursorY < 160) {
      b.addSegment(280, 140, "asphalt", 5);
    }
  }

  for (const p of b.points) world.points.push(p);
  for (const pl of b.platforms) {
    pl.id = `plat-proc-${world.platforms.length + 1}`;
    world.platforms.push(pl);
  }
  for (const pr of b.props) {
    pr.id = `prop-proc-${world.props.length + 1}`;
    world.props.push(pr);
  }
  for (const hz of b.hazards) {
    hz.id = `haz-proc-${world.hazards.length + 1}`;
    world.hazards.push(hz);
  }
  for (const cp of b.checkpoints) {
    cp.index = world.checkpoints.length;
    cp.id = `cp-proc-${cp.index}`;
    world.checkpoints.push(cp);
  }
  for (const co of b.collectibles) {
    co.id = `col-proc-${world.collectibles.length + 1}`;
    world.collectibles.push(co);
  }

  world.proceduralCursorX = b.cursorX;
  world.proceduralLastY = b.cursorY;
}
