import type {
  BikeLiveryId,
  GameMode,
  GameSettings,
  GhostSample,
  MedalTier,
  ModeRecord,
  SaveState,
} from "../types/game.ts";

const STORAGE_KEY = "neon_velocity_save_v1";

export const LIVERIES: Record<
  BikeLiveryId,
  { name: string; frame: string; fork: string; rim: string; glow: string; unlockCells: number }
> = {
  cyan_pulse: {
    name: "Cyber Pulse",
    frame: "#22d3ee",
    fork: "#0ea5e9",
    rim: "#38bdf8",
    glow: "rgba(34, 211, 238, 0.55)",
    unlockCells: 0,
  },
  sakura_strike: {
    name: "Sakura Strike",
    frame: "#f472b6",
    fork: "#ec4899",
    rim: "#f9a8d4",
    glow: "rgba(244, 114, 182, 0.55)",
    unlockCells: 6,
  },
  solar_apex: {
    name: "Solar Apex",
    frame: "#facc15",
    fork: "#f97316",
    rim: "#fde047",
    glow: "rgba(250, 204, 21, 0.55)",
    unlockCells: 14,
  },
  void_phantom: {
    name: "Void Phantom",
    frame: "#c084fc",
    fork: "#9333ea",
    rim: "#e879f9",
    glow: "rgba(192, 132, 252, 0.55)",
    unlockCells: 24,
  },
};

export function createDefaultSettings(): GameSettings {
  const prefersReduced =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const coarsePointer =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(pointer: coarse)").matches;
  return {
    timeOfDay: "night",
    weather: "clear",
    livery: "cyan_pulse",
    volume: 0.55,
    muted: false,
    lowQuality: false,
    reducedMotion: prefersReduced,
    ghostEnabled: true,
    showTouchControls: coarsePointer,
  };
}

function emptyRecord(): ModeRecord {
  return { bestTimeSec: null, bestScore: 0, bestMedal: "none", ghost: [] };
}

export function createDefaultSaveState(): SaveState {
  return {
    version: 1,
    totalCells: 0,
    totalStars: 0,
    totalFlips: 0,
    unlockedLiveries: ["cyan_pulse"],
    records: {
      training: emptyRecord(),
      free_ride: emptyRecord(),
      time_trial: emptyRecord(),
      challenge: emptyRecord(),
    },
    settings: createDefaultSettings(),
  };
}

const MEDAL_RANK: Record<MedalTier, number> = {
  none: 0,
  bronze: 1,
  silver: 2,
  gold: 3,
};

export function sanitizeSaveState(raw: unknown): SaveState {
  const fallback = createDefaultSaveState();
  if (!raw || typeof raw !== "object") return fallback;
  const obj = raw as Record<string, unknown>;
  if (obj.version !== 1) return fallback;

  const settingsRaw = (obj.settings && typeof obj.settings === "object" ? obj.settings : {}) as Record<string, unknown>;
  const settings: GameSettings = {
    timeOfDay: settingsRaw.timeOfDay === "day" || settingsRaw.timeOfDay === "evening" || settingsRaw.timeOfDay === "night"
      ? settingsRaw.timeOfDay
      : fallback.settings.timeOfDay,
    weather: settingsRaw.weather === "clear" || settingsRaw.weather === "rain" || settingsRaw.weather === "neon_fog"
      ? settingsRaw.weather
      : fallback.settings.weather,
    livery: typeof settingsRaw.livery === "string" && settingsRaw.livery in LIVERIES
      ? (settingsRaw.livery as BikeLiveryId)
      : "cyan_pulse",
    volume: typeof settingsRaw.volume === "number" && Number.isFinite(settingsRaw.volume)
      ? Math.max(0, Math.min(1, settingsRaw.volume))
      : fallback.settings.volume,
    muted: Boolean(settingsRaw.muted),
    lowQuality: Boolean(settingsRaw.lowQuality),
    reducedMotion: typeof settingsRaw.reducedMotion === "boolean" ? settingsRaw.reducedMotion : fallback.settings.reducedMotion,
    ghostEnabled: typeof settingsRaw.ghostEnabled === "boolean" ? settingsRaw.ghostEnabled : true,
    showTouchControls: typeof settingsRaw.showTouchControls === "boolean" ? settingsRaw.showTouchControls : fallback.settings.showTouchControls,
  };

  const modes: GameMode[] = ["training", "free_ride", "time_trial", "challenge"];
  const rawRecords = (obj.records && typeof obj.records === "object" ? obj.records : {}) as Record<string, unknown>;
  const records = { ...fallback.records };
  for (const mode of modes) {
    const r = (rawRecords[mode] && typeof rawRecords[mode] === "object" ? rawRecords[mode] : {}) as Record<string, unknown>;
    const ghostArr = Array.isArray(r.ghost)
      ? r.ghost
          .filter(
            (g): g is GhostSample =>
              Boolean(g) &&
              typeof g === "object" &&
              typeof (g as GhostSample).t === "number" &&
              typeof (g as GhostSample).x === "number" &&
              typeof (g as GhostSample).y === "number" &&
              typeof (g as GhostSample).angle === "number",
          )
          .slice(0, 1200)
      : [];
    const medal =
      r.bestMedal === "gold" || r.bestMedal === "silver" || r.bestMedal === "bronze" || r.bestMedal === "none"
        ? r.bestMedal
        : "none";
    records[mode] = {
      bestTimeSec: typeof r.bestTimeSec === "number" && Number.isFinite(r.bestTimeSec) && r.bestTimeSec > 0 ? r.bestTimeSec : null,
      bestScore: typeof r.bestScore === "number" && Number.isFinite(r.bestScore) && r.bestScore >= 0 ? r.bestScore : 0,
      bestMedal: medal,
      ghost: ghostArr,
    };
  }

  const totalCells = typeof obj.totalCells === "number" && Number.isFinite(obj.totalCells) && obj.totalCells >= 0 ? Math.floor(obj.totalCells) : 0;
  const unlockedRaw = Array.isArray(obj.unlockedLiveries) ? obj.unlockedLiveries : ["cyan_pulse"];
  const unlockedSet = new Set<BikeLiveryId>(["cyan_pulse"]);
  for (const l of unlockedRaw) {
    if (typeof l === "string" && l in LIVERIES) unlockedSet.add(l as BikeLiveryId);
  }
  for (const [id, spec] of Object.entries(LIVERIES) as Array<[BikeLiveryId, (typeof LIVERIES)[BikeLiveryId]]>) {
    if (totalCells >= spec.unlockCells) unlockedSet.add(id);
  }
  if (!unlockedSet.has(settings.livery)) {
    settings.livery = "cyan_pulse";
  }

  return {
    version: 1,
    totalCells,
    totalStars: typeof obj.totalStars === "number" && Number.isFinite(obj.totalStars) && obj.totalStars >= 0 ? Math.floor(obj.totalStars) : 0,
    totalFlips: typeof obj.totalFlips === "number" && Number.isFinite(obj.totalFlips) && obj.totalFlips >= 0 ? Math.floor(obj.totalFlips) : 0,
    unlockedLiveries: Array.from(unlockedSet),
    records,
    settings,
  };
}

export class SaveManager {
  private storage: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null;
  private state: SaveState;

  constructor(customStorage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null) {
    if (customStorage !== undefined) {
      this.storage = customStorage;
    } else if (typeof window !== "undefined" && window.localStorage) {
      this.storage = window.localStorage;
    } else {
      this.storage = null;
    }
    this.state = this.load();
  }

  load(): SaveState {
    if (!this.storage) return createDefaultSaveState();
    try {
      const raw = this.storage.getItem(STORAGE_KEY);
      if (!raw) return createDefaultSaveState();
      return sanitizeSaveState(JSON.parse(raw));
    } catch {
      return createDefaultSaveState();
    }
  }

  getState(): SaveState {
    return this.state;
  }

  save(): void {
    if (!this.storage) return;
    try {
      this.storage.setItem(STORAGE_KEY, JSON.stringify(this.state));
    } catch {
      // ignore quota/private-mode storage failure
    }
  }

  updateSettings(patch: Partial<GameSettings>): void {
    this.state = sanitizeSaveState({
      ...this.state,
      settings: { ...this.state.settings, ...patch },
    });
    this.save();
  }

  recordRun(opts: {
    mode: GameMode;
    elapsedSec: number;
    score: number;
    medal: MedalTier;
    cellsCollected: number;
    starsCollected: number;
    flipsDone: number;
    ghost: GhostSample[];
    completed: boolean;
  }): { newBestTime: boolean; newlyUnlocked: BikeLiveryId[] } {
    this.state.totalCells += Math.max(0, opts.cellsCollected);
    this.state.totalStars += Math.max(0, opts.starsCollected);
    this.state.totalFlips += Math.max(0, opts.flipsDone);

    const rec = this.state.records[opts.mode];
    let newBestTime = false;
    if (opts.completed && (rec.bestTimeSec === null || opts.elapsedSec < rec.bestTimeSec)) {
      rec.bestTimeSec = Number(opts.elapsedSec.toFixed(2));
      rec.ghost = opts.ghost.slice(0, 1200);
      newBestTime = true;
    }
    if (opts.score > rec.bestScore) {
      rec.bestScore = Math.floor(opts.score);
    }
    if (MEDAL_RANK[opts.medal] > MEDAL_RANK[rec.bestMedal]) {
      rec.bestMedal = opts.medal;
    }

    const before = new Set(this.state.unlockedLiveries);
    const newlyUnlocked: BikeLiveryId[] = [];
    for (const [id, spec] of Object.entries(LIVERIES) as Array<[BikeLiveryId, (typeof LIVERIES)[BikeLiveryId]]>) {
      if (this.state.totalCells >= spec.unlockCells && !before.has(id)) {
        this.state.unlockedLiveries.push(id);
        newlyUnlocked.push(id);
      }
    }

    this.save();
    return { newBestTime, newlyUnlocked };
  }

  resetProgress(): SaveState {
    const preservedSettings = this.state.settings;
    this.state = createDefaultSaveState();
    this.state.settings = { ...preservedSettings, livery: "cyan_pulse" };
    this.save();
    return this.state;
  }
}
