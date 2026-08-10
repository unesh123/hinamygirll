import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

// ── matchMedia ────────────────────────────────────────────────────────────────
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

// ── scrollIntoView ────────────────────────────────────────────────────────────
// jsdom does not implement scrollIntoView; this no-op prevents the TypeError
// that was causing all 8 App.test.tsx failures.
window.HTMLElement.prototype.scrollIntoView = function () {};

// ── scrollTo ──────────────────────────────────────────────────────────────────
window.HTMLElement.prototype.scrollTo = function () {};

// ── ResizeObserver ────────────────────────────────────────────────────────────
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  value: MockResizeObserver,
});

// ── IntersectionObserver ──────────────────────────────────────────────────────
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, "IntersectionObserver", {
  writable: true,
  value: MockIntersectionObserver,
});

// ── HTMLCanvasElement.getContext ──────────────────────────────────────────────
// Prevents WebGL detection from throwing in jsdom.
HTMLCanvasElement.prototype.getContext = function () {
  return null;
};

