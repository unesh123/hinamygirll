export type GameMode = "training" | "free_ride" | "time_trial" | "challenge";

export type SurfaceType =
  | "asphalt"
  | "wood_ramp"
  | "stairs"
  | "rooftop"
  | "beam"
  | "dirt"
  | "bridge"
  | "tunnel";

export type TimeOfDay = "day" | "evening" | "night";
export type WeatherMode = "clear" | "rain" | "neon_fog";
export type MedalTier = "none" | "bronze" | "silver" | "gold";
export type BikeLiveryId = "cyan_pulse" | "sakura_strike" | "solar_apex" | "void_phantom";

export type ScreenState = "title" | "playing" | "paused" | "settings" | "finished";

export interface Vec2 {
  x: number;
  y: number;
}

export interface TerrainPoint {
  x: number;
  y: number;
  surface: SurfaceType;
  tunnelRoofY?: number | null;
  gap?: boolean;
}

export interface MovingPlatform {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  baseX: number;
  baseY: number;
  ampX: number;
  ampY: number;
  speed: number;
  phase: number;
  surface: SurfaceType;
}

export interface BreakableProp {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  kind: "crate" | "barrier" | "cone";
  broken: boolean;
  breakTimer: number;
}

export interface HazardZone {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  kind: "spikes" | "electric";
}

export interface Checkpoint {
  id: string;
  index: number;
  x: number;
  y: number;
  triggered: boolean;
}

export interface Collectible {
  id: string;
  x: number;
  y: number;
  kind: "cell" | "star";
  collected: boolean;
  bobPhase: number;
}

export interface LevelConfig {
  mode: GameMode;
  title: string;
  subtitle: string;
  finishX: number | null; // null = endless seeded procedural
  fallY: number;
  goldSeconds: number;
  silverSeconds: number;
  bronzeSeconds: number;
  defaultTimeOfDay: TimeOfDay;
  defaultWeather: WeatherMode;
  tutorialHints: Array<{ xStart: number; xEnd: number; text: string }>;
}

export interface WheelContact {
  grounded: boolean;
  surface: SurfaceType;
  normal: Vec2;
  groundY: number;
  grip: number;
  drag: number;
  compression: number; // 0..1
  inTunnel: boolean;
}

export interface BikeState {
  x: number;
  y: number;
  vx: number;
  vy: number;
  angle: number; // radians
  angularVel: number;
  rearWheelAngle: number;
  frontWheelAngle: number;
  rearContact: WheelContact;
  frontContact: WheelContact;
  airTime: number;
  wheelieTime: number;
  stoppieTime: number;
  cumulativeAirSpin: number;
  stuntMessage: string;
  stuntTimer: number;
  boostEnergy: number; // 0..100
  isBoosting: boolean;
  inTunnel: boolean;
  pedalPhase: number;
  crashed: boolean;
  crashTimer: number;
  finished: boolean;
  landingImpulse: number;
  score: number;
  flipsDone: number;
  comboCount: number;
  comboTimer: number;
  brakingHard?: boolean;
}

export interface GhostSample {
  t: number;
  x: number;
  y: number;
  angle: number;
}

export interface InputSnapshot {
  throttle: number; // 0..1
  brake: number; // 0..1
  lean: number; // -1 (wheelie / pitch back) .. +1 (tuck / pitch forward)
  jumpPressed: boolean; // edge trigger
  jumpHeld: boolean;
  boost: boolean;
}

export interface GameSettings {
  timeOfDay: TimeOfDay;
  weather: WeatherMode;
  livery: BikeLiveryId;
  volume: number; // 0..1
  muted: boolean;
  lowQuality: boolean;
  reducedMotion: boolean;
  ghostEnabled: boolean;
  showTouchControls: boolean;
}

export interface ModeRecord {
  bestTimeSec: number | null;
  bestScore: number;
  bestMedal: MedalTier;
  ghost: GhostSample[];
}

export interface SaveState {
  version: number;
  totalCells: number;
  totalStars: number;
  totalFlips: number;
  unlockedLiveries: BikeLiveryId[];
  records: Record<GameMode, ModeRecord>;
  settings: GameSettings;
}

export interface SurfaceStats {
  grip: number;
  drag: number;
  bumpiness: number;
  restitution: number;
  color: string;
  accent: string;
}
