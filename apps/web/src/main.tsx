import { ClerkProvider } from "@clerk/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./design-system/global.css";
import App from "./App.tsx";
import { ClerkSessionGate } from "./features/auth/ClerkSessionGate";

// NOTE: BrowserRouter removed — no routes are registered yet.
// Reintroduce when /playground, /settings, or another genuine route exists.

if (
  typeof window !== "undefined" &&
  (import.meta.env.DEV ||
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1") &&
  "serviceWorker" in navigator
) {
  void navigator.serviceWorker
    .getRegistrations()
    .then((registrations) =>
      Promise.all(
        registrations.map((registration) => registration.unregister()),
      ),
    )
    .then(() => ("caches" in window ? caches.keys() : []))
    .then((keys) => Promise.all(keys.map((key) => caches.delete(key))))
    .catch(() => {
      // Best-effort dev cleanup only
    });
}

const authMode = import.meta.env.VITE_HINAA_AUTH_MODE;
const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {authMode === "clerk" && PUBLISHABLE_KEY ? (
      <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
        <ClerkSessionGate />
      </ClerkProvider>
    ) : (
      <App />
    )}
  </StrictMode>,
);
