import type { BikeState } from "../types/game.ts";

export interface DebugFlags {
  enabled: boolean;
  showHitboxes: boolean;
  showSplines: boolean;
  invulnerable: boolean;
  slowMotion: boolean;
}

export class DebugOverlay {
  flags: DebugFlags = {
    enabled: false,
    showHitboxes: false,
    showSplines: false,
    invulnerable: false,
    slowMotion: false,
  };

  private fps = 60;
  private frameMs = 16.6;

  updateTiming(rawDt: number): void {
    if (rawDt <= 0) return;
    const instantFps = 1 / rawDt;
    this.fps = this.fps * 0.9 + instantFps * 0.1;
    this.frameMs = this.frameMs * 0.9 + rawDt * 1000 * 0.1;
  }

  getFps(): number {
    return Math.round(this.fps);
  }

  getFrameMs(): number {
    return Number(this.frameMs.toFixed(1));
  }

  renderHtml(bike: BikeState): string {
    if (!this.flags.enabled) return "";
    const pitchDeg = Math.round((bike.angle * 180) / Math.PI);
    const speedKmh = Math.round(Math.hypot(bike.vx, bike.vy) * 0.11);
    return `
      <div class="nv-debug-panel" data-testid="nv-debug-panel">
        <div class="nv-debug-title">DEV TELEMETRY (F3)</div>
        <div>FPS: <strong>${this.getFps()}</strong> (${this.getFrameMs()}ms)</div>
        <div>Pos: (${Math.round(bike.x)}, ${Math.round(bike.y)})</div>
        <div>Vel: (${Math.round(bike.vx)}, ${Math.round(bike.vy)}) | ${speedKmh} km/h</div>
        <div>Pitch: ${pitchDeg}&deg; | &omega;: ${bike.angularVel.toFixed(2)}</div>
        <div>Rear: ${bike.rearContact.surface} (${Math.round(bike.rearContact.compression * 100)}%)</div>
        <div>Front: ${bike.frontContact.surface} (${Math.round(bike.frontContact.compression * 100)}%)</div>
        <div>Tunnel: ${bike.inTunnel ? "YES" : "NO"} | Boost: ${Math.round(bike.boostEnergy)}%</div>
        <div class="nv-debug-toggles">
          <button type="button" data-debug-toggle="hitboxes">Hitboxes: ${this.flags.showHitboxes ? "ON" : "OFF"}</button>
          <button type="button" data-debug-toggle="splines">Splines: ${this.flags.showSplines ? "ON" : "OFF"}</button>
          <button type="button" data-debug-toggle="invuln">Invuln: ${this.flags.invulnerable ? "ON" : "OFF"}</button>
          <button type="button" data-debug-toggle="slowmo">Slow-Mo: ${this.flags.slowMotion ? "0.35x" : "1.0x"}</button>
        </div>
      </div>
    `;
  }
}
