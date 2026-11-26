import type { BikeState } from "../types/game.ts";

export class CameraSystem {
  x = 0;
  y = 260;
  zoom = 0.92;
  private shakeAmp = 0;
  private shakeX = 0;
  private shakeY = 0;

  reset(x: number, y: number): void {
    this.x = x + 110;
    this.y = y - 20;
    this.zoom = 0.94;
    this.shakeAmp = 0;
    this.shakeX = 0;
    this.shakeY = 0;
  }

  addShake(amount: number, reducedMotion: boolean): void {
    if (reducedMotion) return;
    this.shakeAmp = Math.min(22, Math.max(this.shakeAmp, amount));
  }

  update(bike: BikeState, dt: number, reducedMotion: boolean): void {
    const speed = Math.hypot(bike.vx, bike.vy);
    const lookAheadX = bike.finished ? 20 : Math.max(-90, Math.min(270, bike.vx * 0.42 + 85));
    const lookAheadY = Math.max(-70, Math.min(90, bike.vy * 0.14)) - 32;

    const targetX = bike.x + lookAheadX;
    const targetY = Math.max(-180, Math.min(720, bike.y + lookAheadY));

    const smoothX = 1 - Math.exp(-7.5 * dt);
    const smoothY = 1 - Math.exp(-5.8 * dt);
    this.x += (targetX - this.x) * smoothX;
    this.y += (targetY - this.y) * smoothY;

    let targetZoom = bike.finished
      ? 1.12
      : Math.max(0.68, Math.min(0.98, 0.97 - (speed / 950) * 0.28));
    if (reducedMotion) targetZoom = Math.max(0.84, targetZoom);

    const smoothZ = 1 - Math.exp(-4.0 * dt);
    this.zoom += (targetZoom - this.zoom) * smoothZ;

    if (this.shakeAmp > 0.08 && !reducedMotion) {
      this.shakeX = (Math.random() * 2 - 1) * this.shakeAmp;
      this.shakeY = (Math.random() * 2 - 1) * this.shakeAmp;
      this.shakeAmp *= Math.exp(-11 * dt);
    } else {
      this.shakeAmp = 0;
      this.shakeX = 0;
      this.shakeY = 0;
    }
  }

  getRenderOffset(viewWidth: number, viewHeight: number): { offsetX: number; offsetY: number; zoom: number } {
    return {
      offsetX: viewWidth * 0.5 - (this.x + this.shakeX) * this.zoom,
      offsetY: viewHeight * 0.54 - (this.y + this.shakeY) * this.zoom,
      zoom: this.zoom,
    };
  }
}
