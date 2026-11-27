import type {
  BikeLiveryId,
  BikeState,
  GameMode,
  GameSettings,
  MedalTier,
  SaveState,
  ScreenState,
} from "../types/game.ts";
import { MODE_CONFIGS } from "../terrain/LevelGenerator.ts";
import { LIVERIES } from "../save/SaveManager.ts";
import type { TouchActionName } from "../input/InputManager.ts";

export interface UiCallbacks {
  onSelectMode: (mode: GameMode) => void;
  onResume: () => void;
  onRestart: () => void;
  onRespawnCheckpoint: () => void;
  onOpenSettings: () => void;
  onCloseSettings: () => void;
  onReturnTitle: () => void;
  onUpdateSettings: (patch: Partial<GameSettings>) => void;
  onResetSave: () => void;
  onTogglePause: () => void;
  onToggleMute: () => void;
  onToggleGhost: () => void;
  onToggleDebug: () => void;
  onTouchAction: (action: TouchActionName, pressed: boolean) => void;
}

const MEDAL_BADGE: Record<MedalTier, string> = {
  none: "No Medal",
  bronze: "BRONZE",
  silver: "SILVER",
  gold: "GOLD",
};

export function renderHudAndMenus(opts: {
  overlayRoot: HTMLElement;
  screen: ScreenState;
  mode: GameMode;
  bike: BikeState;
  saveState: SaveState;
  elapsedSec: number;
  finishMedal: MedalTier;
  finishBanner: string;
  activeHint: string;
  debugHtml: string;
  fps: number;
  cb: UiCallbacks;
}): void {
  const { overlayRoot, screen, mode, bike, saveState, elapsedSec, finishMedal, finishBanner, activeHint, debugHtml, fps, cb } = opts;
  const speedKmh = Math.round(Math.hypot(bike.vx, bike.vy) * 0.11);
  const cfg = MODE_CONFIGS[mode];
  const progressPct =
    cfg.finishX !== null ? Math.max(0, Math.min(100, Math.round((bike.x / cfg.finishX) * 100))) : null;

  let html = "";

  if (screen === "playing" || screen === "paused" || screen === "finished") {
    html += `
      <div class="nv-hud-top">
        <div class="nv-hud-card" data-testid="nv-hud-telemetry">
          <div class="nv-hud-row">
            <div>
              <div class="nv-stat-label">Speed</div>
              <div class="nv-stat-val" data-testid="nv-speed-val">${speedKmh} km/h</div>
            </div>
            <div>
              <div class="nv-stat-label">Time</div>
              <div class="nv-stat-val" data-testid="nv-time-val">${elapsedSec.toFixed(1)}s</div>
            </div>
            <div>
              <div class="nv-stat-label">Score</div>
              <div class="nv-stat-val" data-testid="nv-score-val">${Math.floor(bike.score)}</div>
            </div>
            ${
              progressPct !== null
                ? `<div><div class="nv-stat-label">Course</div><div class="nv-stat-val">${progressPct}%</div></div>`
                : `<div><div class="nv-stat-label">Dist</div><div class="nv-stat-val">${Math.max(0, Math.round(bike.x / 18))}m</div></div>`
            }
          </div>
          <div class="nv-hud-row" style="margin-top:4px; gap:8px;">
            <span class="nv-stat-label">Nitro</span>
            <div class="nv-boost-track"><div class="nv-boost-fill" style="width:${Math.round(bike.boostEnergy)}%"></div></div>
            <span class="nv-stat-label" style="margin-left:auto;">${fps} FPS</span>
          </div>
        </div>

        <div class="nv-btn-row">
          <button type="button" class="nv-btn" data-action="ghost">Ghost: ${saveState.settings.ghostEnabled ? "ON" : "OFF"}</button>
          <button type="button" class="nv-btn" data-action="mute">${saveState.settings.muted ? "Unmute" : "Sound On"}</button>
          <button type="button" class="nv-btn" data-action="debug">Debug</button>
          <button type="button" class="nv-btn" data-action="restart">Restart</button>
          <button type="button" class="nv-btn" data-action="pause">Pause</button>
        </div>
      </div>
    `;

    if (bike.stuntTimer > 0 && bike.stuntMessage) {
      html += `<div class="nv-stunt-banner" data-testid="nv-stunt-banner">${bike.stuntMessage}</div>`;
    }

    if (activeHint && screen === "playing") {
      html += `<div class="nv-hint-banner">${activeHint}</div>`;
    }

    html += `
      <div class="nv-controls-legend">
        W/Up: Pedal • S/Down: Brake • A/D or Left/Right: Wheelie & Flips • Space: Hop • Shift: Nitro • Tab: Ghost • R: Restart • P: Pause
      </div>
    `;

    if (saveState.settings.showTouchControls && screen === "playing") {
      html += `
        <div class="nv-touch-bar" data-testid="nv-touch-controls">
          <div class="nv-touch-group">
            <button type="button" class="nv-touch-btn" data-touch="leanLeft">LEAN L</button>
            <button type="button" class="nv-touch-btn" data-touch="leanRight">LEAN R</button>
          </div>
          <div class="nv-touch-group">
            <button type="button" class="nv-touch-btn" data-touch="brake">BRAKE</button>
            <button type="button" class="nv-touch-btn" data-touch="jump">HOP</button>
            <button type="button" class="nv-touch-btn" data-touch="boost">NITRO</button>
            <button type="button" class="nv-touch-btn nv-btn-primary" data-touch="throttle">PEDAL</button>
          </div>
        </div>
      `;
    }
  }

  html += debugHtml;

  if (screen === "title") {
    const modeCards = (["training", "free_ride", "time_trial", "challenge"] as GameMode[])
      .map((m) => {
        const mc = MODE_CONFIGS[m];
        const rec = saveState.records[m];
        const bestTime = rec.bestTimeSec !== null ? `${rec.bestTimeSec.toFixed(1)}s` : "—";
        return `
          <button type="button" class="nv-mode-card" data-mode="${m}" data-testid="nv-start-${m}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>${mc.title}</strong>
              <span style="font-size:11px;color:#22d3ee;">${MEDAL_BADGE[rec.bestMedal]}</span>
            </div>
            <div style="font-size:12px;color:#cbd5e1;">${mc.subtitle}</div>
            <div style="font-size:11px;color:#94a3b8;font-family:monospace;">Best Time: ${bestTime} • Best Score: ${rec.bestScore}</div>
          </button>
        `;
      })
      .join("");

    html += `
      <div class="nv-modal-backdrop" data-testid="nv-title-screen">
        <div class="nv-modal-card">
          <div>
            <div style="font-size:11px;letter-spacing:0.14em;color:#22d3ee;font-weight:700;">URBAN 2D BICYCLE PHYSICS ENGINE</div>
            <h1 class="nv-title-hero">NEON VELOCITY: URBAN PHYSICS</h1>
            <p style="font-size:13px;color:#cbd5e1;margin-top:6px;">
              Real 2-wheel spring suspension, articulated rider physics, rooftop gaps, stairs, tunnels, smashable props & TAB ghost trials.
            </p>
          </div>
          <div style="font-size:12px;color:#94a3b8;display:flex;gap:14px;flex-wrap:wrap;">
            <span>Energy Cells: <strong style="color:#22d3ee;">${saveState.totalCells}</strong></span>
            <span>Style Stars: <strong style="color:#facc15;">${saveState.totalStars}</strong></span>
            <span>Total Flips: <strong style="color:#f472b6;">${saveState.totalFlips}</strong></span>
            <span>Livery: <strong style="color:#e2e8f0;">${LIVERIES[saveState.settings.livery].name}</strong></span>
          </div>
          <div class="nv-mode-grid">${modeCards}</div>
          <div class="nv-btn-row">
            <button type="button" class="nv-btn" data-action="settings" data-testid="nv-open-settings">Garage & Settings</button>
            <button type="button" class="nv-btn" data-action="debug">Telemetry (F3)</button>
          </div>
        </div>
      </div>
    `;
  } else if (screen === "paused") {
    html += `
      <div class="nv-modal-backdrop" data-testid="nv-pause-modal">
        <div class="nv-modal-card" style="width:min(420px,100%);">
          <h2 style="font-size:20px;font-weight:700;">Run Paused</h2>
          <p style="font-size:13px;color:#94a3b8;">${cfg.title} • ${elapsedSec.toFixed(1)}s</p>
          <div class="nv-btn-row" style="flex-direction:column;">
            <button type="button" class="nv-btn nv-btn-primary" data-action="resume" data-testid="nv-resume-btn">Resume Ride</button>
            <button type="button" class="nv-btn" data-action="checkpoint">Respawn Last Checkpoint (C)</button>
            <button type="button" class="nv-btn" data-action="restart">Restart Track (R)</button>
            <button type="button" class="nv-btn" data-action="settings">Garage & Settings</button>
            <button type="button" class="nv-btn" data-action="title">Back to Mode Select</button>
          </div>
        </div>
      </div>
    `;
  } else if (screen === "settings") {
    const liveryButtons = (Object.entries(LIVERIES) as Array<[BikeLiveryId, (typeof LIVERIES)[BikeLiveryId]]>)
      .map(([id, spec]) => {
        const unlocked = saveState.unlockedLiveries.includes(id);
        const active = saveState.settings.livery === id;
        return `
          <button
            type="button"
            class="nv-btn ${active ? "nv-btn-primary" : ""}"
            data-livery="${id}"
            ${unlocked ? "" : "disabled"}
            style="opacity:${unlocked ? 1 : 0.48};"
          >
            ${spec.name} ${unlocked ? "" : `(Unlock ${spec.unlockCells} Cells)`}
          </button>
        `;
      })
      .join("");

    html += `
      <div class="nv-modal-backdrop" data-testid="nv-settings-modal">
        <div class="nv-modal-card">
          <h2 style="font-size:20px;font-weight:700;">Garage, Atmosphere & Accessibility</h2>
          <div>
            <div class="nv-stat-label" style="margin-bottom:6px;">Bike Livery</div>
            <div class="nv-btn-row">${liveryButtons}</div>
          </div>
          <div class="nv-hud-row">
            <div>
              <div class="nv-stat-label" style="margin-bottom:6px;">Time of Day</div>
              <div class="nv-btn-row">
                ${(["day", "evening", "night"] as const)
                  .map(
                    (tod) =>
                      `<button type="button" class="nv-btn ${saveState.settings.timeOfDay === tod ? "nv-btn-primary" : ""}" data-tod="${tod}">${tod.toUpperCase()}</button>`,
                  )
                  .join("")}
              </div>
            </div>
            <div>
              <div class="nv-stat-label" style="margin-bottom:6px;">Weather</div>
              <div class="nv-btn-row">
                ${(["clear", "rain", "neon_fog"] as const)
                  .map(
                    (w) =>
                      `<button type="button" class="nv-btn ${saveState.settings.weather === w ? "nv-btn-primary" : ""}" data-weather="${w}">${w.replace("_", " ").toUpperCase()}</button>`,
                  )
                  .join("")}
              </div>
            </div>
          </div>
          <div class="nv-hud-row">
            <label style="font-size:12px;display:flex;align-items:center;gap:8px;">
              Volume
              <input type="range" min="0" max="100" value="${Math.round(saveState.settings.volume * 100)}" data-setting="volume" />
            </label>
            <button type="button" class="nv-btn" data-setting-toggle="lowQuality">Low Quality: ${saveState.settings.lowQuality ? "ON" : "OFF"}</button>
            <button type="button" class="nv-btn" data-setting-toggle="reducedMotion">Reduced Motion: ${saveState.settings.reducedMotion ? "ON" : "OFF"}</button>
            <button type="button" class="nv-btn" data-setting-toggle="showTouchControls">Touch Pad: ${saveState.settings.showTouchControls ? "ON" : "OFF"}</button>
          </div>
          <div class="nv-btn-row" style="justify-content:space-between;">
            <button type="button" class="nv-btn nv-btn-danger" data-action="reset-save" data-testid="nv-reset-save">Reset Save Progress</button>
            <button type="button" class="nv-btn nv-btn-primary" data-action="close-settings" data-testid="nv-close-settings">Done</button>
          </div>
        </div>
      </div>
    `;
  } else if (screen === "finished") {
    html += `
      <div class="nv-modal-backdrop" data-testid="nv-finish-modal">
        <div class="nv-modal-card" style="width:min(460px,100%);">
          <div style="font-size:12px;color:#22d3ee;font-weight:700;">COURSE COMPLETE</div>
          <h2 style="font-size:24px;font-weight:800;">${cfg.title}</h2>
          <div class="nv-hud-row">
            <div><div class="nv-stat-label">Time</div><div class="nv-stat-val">${elapsedSec.toFixed(2)}s</div></div>
            <div><div class="nv-stat-label">Score</div><div class="nv-stat-val">${Math.floor(bike.score)}</div></div>
            <div><div class="nv-stat-label">Medal</div><div class="nv-stat-val" style="color:#facc15;">${MEDAL_BADGE[finishMedal]}</div></div>
          </div>
          ${finishBanner ? `<div style="font-size:13px;color:#f472b6;font-weight:600;">${finishBanner}</div>` : ""}
          <div class="nv-btn-row">
            <button type="button" class="nv-btn nv-btn-primary" data-action="restart">Ride Again</button>
            <button type="button" class="nv-btn" data-action="title">Mode Select</button>
          </div>
        </div>
      </div>
    `;
  }

  overlayRoot.innerHTML = html;

  overlayRoot.querySelectorAll<HTMLElement>("[data-mode]").forEach((el) => {
    el.addEventListener("click", () => cb.onSelectMode(el.dataset.mode as GameMode));
  });
  overlayRoot.querySelectorAll<HTMLElement>("[data-action]").forEach((el) => {
    el.addEventListener("click", () => {
      const act = el.dataset.action;
      if (act === "resume") cb.onResume();
      else if (act === "restart") cb.onRestart();
      else if (act === "checkpoint") cb.onRespawnCheckpoint();
      else if (act === "pause") cb.onTogglePause();
      else if (act === "mute") cb.onToggleMute();
      else if (act === "ghost") cb.onToggleGhost();
      else if (act === "debug") cb.onToggleDebug();
      else if (act === "settings") cb.onOpenSettings();
      else if (act === "close-settings") cb.onCloseSettings();
      else if (act === "title") cb.onReturnTitle();
      else if (act === "reset-save") cb.onResetSave();
    });
  });
  overlayRoot.querySelectorAll<HTMLElement>("[data-livery]").forEach((el) => {
    el.addEventListener("click", () => cb.onUpdateSettings({ livery: el.dataset.livery as BikeLiveryId }));
  });
  overlayRoot.querySelectorAll<HTMLElement>("[data-tod]").forEach((el) => {
    el.addEventListener("click", () => cb.onUpdateSettings({ timeOfDay: el.dataset.tod as GameSettings["timeOfDay"] }));
  });
  overlayRoot.querySelectorAll<HTMLElement>("[data-weather]").forEach((el) => {
    el.addEventListener("click", () => cb.onUpdateSettings({ weather: el.dataset.weather as GameSettings["weather"] }));
  });
  overlayRoot.querySelectorAll<HTMLElement>("[data-setting-toggle]").forEach((el) => {
    el.addEventListener("click", () => {
      const k = el.dataset.settingToggle as "lowQuality" | "reducedMotion" | "showTouchControls";
      cb.onUpdateSettings({ [k]: !saveState.settings[k] });
    });
  });
  overlayRoot.querySelector<HTMLInputElement>('[data-setting="volume"]')?.addEventListener("input", (e) => {
    const val = Number((e.target as HTMLInputElement).value) / 100;
    cb.onUpdateSettings({ volume: val });
  });
  overlayRoot.querySelectorAll<HTMLElement>("[data-touch]").forEach((el) => {
    const act = el.dataset.touch as TouchActionName;
    el.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      el.setPointerCapture?.(e.pointerId);
      cb.onTouchAction(act, true);
    });
    const end = () => cb.onTouchAction(act, false);
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("pointerleave", end);
  });
}
