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

// ── localStorage / sessionStorage ─────────────────────────────────────────────
// jsdom does not expose Web Storage on an opaque origin, and Node's experimental
// localStorage is disabled unless --localstorage-file is passed. Without this,
// `localStorage.clear()` in tests throws "Cannot read properties of undefined".
// Provide a deterministic in-memory implementation so settings-persistence
// tests (and anything else touching storage) run reliably.
const makeMemoryStorage = (): Storage => {
  const store = new Map<string, string>();
  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  } as Storage;
};

for (const name of ["localStorage", "sessionStorage"] as const) {
  const storage = makeMemoryStorage();
  Object.defineProperty(window, name, {
    writable: true,
    configurable: true,
    value: storage,
  });
  Object.defineProperty(globalThis, name, {
    writable: true,
    configurable: true,
    value: storage,
  });
}

