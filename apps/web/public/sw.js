// HINAA self-destroying service worker.
//
// Why this file exists:
// An earlier production build shipped a Workbox/PWA service worker
// (vite-plugin-pwa, registerType: "autoUpdate") that precached the built app.
// That old worker stays registered in the browser and keeps serving the STALE
// bundle on localhost:5173 — so freshly edited code never appears, even though
// the Vite dev server is serving the new code correctly.
//
// This replacement worker takes over that registration and removes itself:
// it deletes every cache, unregisters, and reloads open tabs so the page is
// then served straight from the network (Vite) again. After one or two reloads
// the browser is clean and no service worker remains.
self.addEventListener("install", () => {
  // Activate immediately instead of waiting for old clients to close.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // 1. Nuke every Cache Storage entry (the stale precache lives here).
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map((key) => caches.delete(key)));
      } catch {
        // Best effort — continue to unregister regardless.
      }
      // 2. Remove this worker so nothing intercepts future requests.
      try {
        await self.registration.unregister();
      } catch {
        // Ignore; the reload below still recovers the page.
      }
      // 3. Force every open HINAA tab to reload from the network now.
      try {
        const clients = await self.clients.matchAll({ type: "window" });
        for (const client of clients) {
          client.navigate(client.url);
        }
      } catch {
        // If navigation is blocked, a manual refresh still completes cleanup.
      }
    })(),
  );
});

// While briefly active, never answer from cache — always hit the network.
self.addEventListener("fetch", () => {
  // No respondWith() => default network behavior (pass-through).
});
