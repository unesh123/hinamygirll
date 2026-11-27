import "./styles/game.css";
import type { BikeState, GameMode, GhostSample, MedalTier, ScreenState } from "./types/game.ts";
import { SaveManager } from "./save/SaveManager.ts";
import { InputManager } from "./input/InputManager.ts";
import { generateLevel, MODE_CONFIGS, type GeneratedWorld } from "./terrain/LevelGenerator.ts";
import { computeMedal, createBikeState, respawnAtCheckpoint, stepBikePhysics } from "./physics/BikePhysics.ts";
import { CameraSystem } from "./camera/CameraSystem.ts";
import { ParticleSystem } from "./effects/ParticleSystem.ts";
import { AudioManager } from "./audio/AudioManager.ts";
import { DebugOverlay } from "./debug/DebugOverlay.ts";
import { GameRenderer } from "./render/Renderer.ts";
import { renderHudAndMenus, type UiCallbacks } from "./ui/HudAndMenus.ts";

class NeonVelocityGame {
  private root: HTMLElement;
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private overlayRoot: HTMLDivElement;

  private saveManager = new SaveManager();
  private audio = new AudioManager();
  private input: InputManager;
  private camera = new CameraSystem();
  private particles = new ParticleSystem(520);
  private debug = new DebugOverlay();
  private renderer = new GameRenderer();

  private screen: ScreenState = "title";
  private prevScreenBeforeSettings: ScreenState = "title";
  private mode: GameMode = "training";
  private world: GeneratedWorld = generateLevel("training", 1337);
  private bike: BikeState = createBikeState(40, 310);

  private activeCheckpoint = { x: 40, y: 360 };
  private elapsedSec = 0;
  private runCells = 0;
  private runStars = 0;
  private finishMedal: MedalTier = "none";
  private finishBanner = "";

  private ghostRecording: GhostSample[] = [];
  private lastGhostRecordTime = -1;
  private activeGhostPlayback: GhostSample[] = [];

  private rafId: number | null = null;
  private lastFrameMs = 0;
  private accumulator = 0;
  private uiRefreshAccum = 0;
  private lastRenderedUiKey = "";
  private tabHidden = false;

  constructor(mountEl: HTMLElement) {
    this.root = document.createElement("div");
    this.root.className = "nv-root";
    this.canvas = document.createElement("canvas");
    this.canvas.className = "nv-canvas";
    this.canvas.setAttribute("aria-label", "Neon Velocity interactive cycling viewport");
    this.overlayRoot = document.createElement("div");
    this.root.appendChild(this.canvas);
    this.root.appendChild(this.overlayRoot);
    mountEl.innerHTML = "";
    mountEl.appendChild(this.root);

    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas context unavailable");
    this.ctx = ctx;

    this.input = new InputManager(() => this.audio.unlock());
    this.applySavedAudio();

    window.addEventListener("resize", this.onResize);
    document.addEventListener("visibilitychange", this.onVisibility);
    this.onResize();
    this.startMode("training", false);
    this.screen = "title";
    this.syncUi(true);
    this.lastFrameMs = performance.now();
    this.rafId = requestAnimationFrame(this.loop);
  }

  private onResize = (): void => {
    this.renderer.resize(this.canvas, this.saveManager.getState().settings.lowQuality);
  };

  private onVisibility = (): void => {
    this.tabHidden = document.hidden;
    if (this.tabHidden && this.screen === "playing") {
      this.screen = "paused";
      this.input.clearAll();
      this.audio.updateContinuum(0, false, false, false, false);
      this.syncUi(true);
    }
    this.lastFrameMs = performance.now();
  };

  private applySavedAudio(): void {
    const s = this.saveManager.getState().settings;
    this.audio.setVolumeAndMute(s.volume, s.muted);
  }

  private startMode(mode: GameMode, enterPlaying = true): void {
    this.mode = mode;
    this.world = generateLevel(mode, 1337);
    const cfg = MODE_CONFIGS[mode];
    if (enterPlaying) {
      const settings = this.saveManager.getState().settings;
      if (this.screen === "title") {
        // Respect explicit user settings when coming from settings; otherwise apply track atmosphere on first launch cleanly
        if (!settings.timeOfDay) {
          this.saveManager.updateSettings({ timeOfDay: cfg.defaultTimeOfDay, weather: cfg.defaultWeather });
        }
      }
    }
    this.activeCheckpoint = { x: 40, y: 360 };
    this.bike = createBikeState(40, 310);
    this.camera.reset(this.bike.x, this.bike.y);
    this.particles.clear();
    this.elapsedSec = 0;
    this.runCells = 0;
    this.runStars = 0;
    this.finishMedal = "none";
    this.finishBanner = "";
    this.ghostRecording = [{ t: 0, x: this.bike.x, y: this.bike.y, angle: this.bike.angle }];
    this.lastGhostRecordTime = 0;
    this.activeGhostPlayback = this.saveManager.getState().records[mode].ghost ?? [];
    if (enterPlaying) {
      this.screen = "playing";
    }
    this.syncUi(true);
  }

  private sampleGhostAtTime(t: number): GhostSample | null {
    const arr = this.activeGhostPlayback;
    if (arr.length === 0) return null;
    if (t >= arr[arr.length - 1]!.t) return arr[arr.length - 1]!;
    for (let i = 0; i < arr.length - 1; i++) {
      const a = arr[i]!;
      const b = arr[i + 1]!;
      if (t >= a.t && t <= b.t) {
        const ratio = (t - a.t) / Math.max(1e-4, b.t - a.t);
        return {
          t,
          x: a.x + (b.x - a.x) * ratio,
          y: a.y + (b.y - a.y) * ratio,
          angle: a.angle + (b.angle - a.angle) * ratio,
        };
      }
    }
    return arr[0]!;
  }

  private currentTutorialHint(): string {
    for (const h of this.world.config.tutorialHints) {
      if (this.bike.x >= h.xStart && this.bike.x <= h.xEnd) return h.text;
    }
    return "";
  }

  private getCallbacks(): UiCallbacks {
    return {
      onSelectMode: (m) => {
        this.audio.unlock();
        this.startMode(m, true);
      },
      onResume: () => {
        this.audio.unlock();
        this.screen = "playing";
        this.syncUi(true);
      },
      onRestart: () => {
        this.audio.unlock();
        this.startMode(this.mode, true);
      },
      onRespawnCheckpoint: () => {
        respawnAtCheckpoint(this.bike, this.activeCheckpoint);
        this.screen = "playing";
        this.syncUi(true);
      },
      onOpenSettings: () => {
        this.prevScreenBeforeSettings = this.screen;
        this.screen = "settings";
        this.syncUi(true);
      },
      onCloseSettings: () => {
        this.screen = this.prevScreenBeforeSettings === "paused" ? "paused" : "title";
        this.syncUi(true);
      },
      onReturnTitle: () => {
        this.screen = "title";
        this.audio.updateContinuum(0, false, false, false, false);
        this.syncUi(true);
      },
      onUpdateSettings: (patch) => {
        this.saveManager.updateSettings(patch);
        this.applySavedAudio();
        this.onResize();
        this.syncUi(true);
      },
      onResetSave: () => {
        this.saveManager.resetProgress();
        this.syncUi(true);
      },
      onTogglePause: () => {
        if (this.screen === "playing") this.screen = "paused";
        else if (this.screen === "paused") this.screen = "playing";
        this.syncUi(true);
      },
      onToggleMute: () => {
        const cur = this.saveManager.getState().settings.muted;
        this.saveManager.updateSettings({ muted: !cur });
        this.applySavedAudio();
        this.syncUi(true);
      },
      onToggleGhost: () => {
        const cur = this.saveManager.getState().settings.ghostEnabled;
        this.saveManager.updateSettings({ ghostEnabled: !cur });
        this.syncUi(true);
      },
      onToggleDebug: () => {
        this.debug.flags.enabled = !this.debug.flags.enabled;
        this.syncUi(true);
      },
      onTouchAction: (act, pressed) => this.input.setTouchAction(act, pressed),
    };
  }

  private syncUi(force = false): void {
    const hint = this.currentTutorialHint();
    const uiKey = [
      this.screen,
      this.mode,
      Math.round(this.bike.x),
      Math.round(this.bike.vx),
      Math.floor(this.bike.score),
      Math.round(this.bike.boostEnergy),
      this.bike.stuntTimer > 0 ? this.bike.stuntMessage : "",
      this.elapsedSec.toFixed(1),
      hint,
      this.debug.flags.enabled ? `dbg:${this.debug.getFps()}` : "",
    ].join("|");

    if (!force && uiKey === this.lastRenderedUiKey) return;
    this.lastRenderedUiKey = uiKey;

    renderHudAndMenus({
      overlayRoot: this.overlayRoot,
      screen: this.screen,
      mode: this.mode,
      bike: this.bike,
      saveState: this.saveManager.getState(),
      elapsedSec: this.elapsedSec,
      finishMedal: this.finishMedal,
      finishBanner: this.finishBanner,
      activeHint: hint,
      debugHtml: this.debug.renderHtml(this.bike),
      fps: this.debug.getFps(),
      cb: this.getCallbacks(),
    });

    if (this.debug.flags.enabled) {
      this.overlayRoot.querySelectorAll<HTMLElement>("[data-debug-toggle]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const k = btn.dataset.debugToggle;
          if (k === "hitboxes") this.debug.flags.showHitboxes = !this.debug.flags.showHitboxes;
          if (k === "splines") this.debug.flags.showSplines = !this.debug.flags.showSplines;
          if (k === "invuln") this.debug.flags.invulnerable = !this.debug.flags.invulnerable;
          if (k === "slowmo") this.debug.flags.slowMotion = !this.debug.flags.slowMotion;
          this.syncUi(true);
        });
      });
    }
  }

  private loop = (nowMs: number): void => {
    const rawDt = Math.min(0.05, Math.max(0.001, (nowMs - this.lastFrameMs) / 1000));
    this.lastFrameMs = nowMs;
    this.debug.updateTiming(rawDt);

    const ctrl = this.input.consumeControlEvents();
    if (ctrl.pauseToggled) {
      if (this.screen === "playing") {
        this.screen = "paused";
        this.syncUi(true);
      } else if (this.screen === "paused") {
        this.screen = "playing";
        this.syncUi(true);
      }
    }
    if (ctrl.restartPressed && (this.screen === "playing" || this.screen === "paused" || this.screen === "finished")) {
      this.startMode(this.mode, true);
    }
    if (ctrl.checkpointRespawnPressed && (this.screen === "playing" || this.screen === "paused")) {
      respawnAtCheckpoint(this.bike, this.activeCheckpoint);
      this.screen = "playing";
      this.syncUi(true);
    }
    if (ctrl.ghostToggled) {
      const cur = this.saveManager.getState().settings.ghostEnabled;
      this.saveManager.updateSettings({ ghostEnabled: !cur });
      this.syncUi(true);
    }
    if (ctrl.muteToggled) {
      const cur = this.saveManager.getState().settings.muted;
      this.saveManager.updateSettings({ muted: !cur });
      this.applySavedAudio();
      this.syncUi(true);
    }
    if (ctrl.debugToggled) {
      this.debug.flags.enabled = !this.debug.flags.enabled;
      this.syncUi(true);
    }

    const settings = this.saveManager.getState().settings;

    if (this.screen === "playing" && !this.tabHidden) {
      const timeScale = this.debug.flags.slowMotion ? 0.35 : 1.0;
      const scaledDt = rawDt * timeScale;
      this.accumulator += scaledDt;
      const fixedDt = 1 / 120;
      const snap = this.input.readSnapshot();

      let brakingAny = false;
      while (this.accumulator >= fixedDt) {
        this.elapsedSec += fixedDt;
        const ev = stepBikePhysics(this.bike, this.world, snap, fixedDt, this.elapsedSec, this.activeCheckpoint);

        if (this.debug.flags.invulnerable && ev.crashed) {
          this.bike.crashed = false;
          this.bike.angle = 0;
          this.bike.angularVel = 0;
          this.bike.y = Math.min(this.bike.y, 320);
          ev.crashed = false;
        }

        if (ev.jumped) {
          this.audio.playJump();
          this.particles.emitDust(this.bike.x - 24, this.bike.y + 26, "#38bdf8", 5);
        }
        if (ev.landedImpulse > 180) {
          this.audio.playLanding(ev.landedImpulse);
          this.camera.addShake(Math.min(12, ev.landedImpulse / 70), settings.reducedMotion);
          const col = this.bike.rearContact.surface === "dirt" ? "#d97706" : "#94a3b8";
          this.particles.emitDust(this.bike.x, this.bike.y + 26, col, 6);
        }
        if (ev.brokePropKind) {
          this.audio.playSmash();
          this.camera.addShake(7, settings.reducedMotion);
          this.particles.emitDebris(this.bike.x + 26, this.bike.y, ev.brokePropKind);
        }
        if (ev.collectedKind) {
          this.audio.playCollect(ev.collectedKind === "star");
          if (ev.collectedKind === "star") this.runStars += 1;
          else this.runCells += 1;
          this.particles.emitBurst(this.bike.x, this.bike.y - 8, 12, ev.collectedKind === "star" ? "#facc15" : "#22d3ee");
        }
        if (ev.checkpointIndex !== null) {
          const cp = this.world.checkpoints[ev.checkpointIndex];
          if (cp) {
            this.activeCheckpoint = { x: cp.x, y: cp.y };
            this.audio.playCheckpoint();
            this.particles.emitBurst(cp.x, cp.y - 45, 16, "#34d399");
          }
        }
        if (ev.crashed) {
          this.audio.playCrash();
          this.camera.addShake(18, settings.reducedMotion);
          this.particles.emitBurst(this.bike.x, this.bike.y, 24, "#f43f5e", 300, "spark");
        }
        if (ev.brakingHard) brakingAny = true;

        if (ev.finished) {
          this.audio.playFinish();
          this.particles.emitBurst(this.bike.x, this.bike.y - 40, 32, "#facc15", 320, "spark");
          this.finishMedal = computeMedal(this.world, this.elapsedSec, this.bike.score);
          const saveRes = this.saveManager.recordRun({
            mode: this.mode,
            elapsedSec: this.elapsedSec,
            score: this.bike.score,
            medal: this.finishMedal,
            cellsCollected: this.runCells,
            starsCollected: this.runStars,
            flipsDone: this.bike.flipsDone,
            ghost: this.ghostRecording,
            completed: true,
          });
          const notes: string[] = [];
          if (saveRes.newBestTime) notes.push("NEW PERSONAL BEST!");
          if (saveRes.newlyUnlocked.length > 0) notes.push(`UNLOCKED LIVERY: ${saveRes.newlyUnlocked.join(", ")}`);
          this.finishBanner = notes.join(" • ");
          this.screen = "finished";
          this.syncUi(true);
        }

        if (this.elapsedSec - this.lastGhostRecordTime >= 0.08) {
          this.lastGhostRecordTime = this.elapsedSec;
          this.ghostRecording.push({
            t: Number(this.elapsedSec.toFixed(2)),
            x: Math.round(this.bike.x),
            y: Math.round(this.bike.y),
            angle: Number(this.bike.angle.toFixed(3)),
          });
        }

        this.accumulator -= fixedDt;
      }

      if (this.bike.isBoosting && !this.bike.crashed) {
        this.particles.emitBoostFlame(this.bike.x - Math.cos(this.bike.angle) * 28, this.bike.y - Math.sin(this.bike.angle) * 28, this.bike.vx, this.bike.vy);
      }
      if (this.bike.rearContact.grounded && this.bike.rearContact.surface === "dirt" && Math.abs(this.bike.vx) > 150) {
        if (Math.random() < 0.45) this.particles.emitDust(this.bike.x - 28, this.bike.y + 24, "#b45309", 1);
      }
      if (brakingAny && Math.random() < 0.6) {
        this.particles.emitDust(this.bike.x + 24, this.bike.y + 24, "#e2e8f0", 1);
      }

      this.particles.update(rawDt);
      this.camera.update(this.bike, rawDt, settings.reducedMotion);
      this.audio.updateContinuum(
        Math.hypot(this.bike.vx, this.bike.vy),
        this.bike.isBoosting,
        this.bike.rearContact.grounded || this.bike.frontContact.grounded,
        brakingAny,
        true,
      );

      this.uiRefreshAccum += rawDt;
      if (this.uiRefreshAccum >= 0.08) {
        this.uiRefreshAccum = 0;
        this.syncUi(false);
      }
    } else {
      this.audio.updateContinuum(0, false, false, false, false);
      this.camera.update(this.bike, rawDt * 0.35, settings.reducedMotion);
      this.particles.update(rawDt);
    }

    this.renderer.render({
      ctx: this.ctx,
      world: this.world,
      bike: this.bike,
      camera: this.camera,
      particles: this.particles,
      settings,
      elapsedSec: this.elapsedSec,
      ghostSample: this.screen === "playing" ? this.sampleGhostAtTime(this.elapsedSec) : null,
      debugFlags: this.debug.flags,
    });

    this.rafId = requestAnimationFrame(this.loop);
  };

  destroy(): void {
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    window.removeEventListener("resize", this.onResize);
    document.removeEventListener("visibilitychange", this.onVisibility);
    this.input.destroy();
    this.audio.destroy();
  }
}

const appRoot = document.getElementById("app");
if (appRoot) {
  const game = new NeonVelocityGame(appRoot);
  (window as unknown as { __neonVelocity?: NeonVelocityGame }).__neonVelocity = game;
}
