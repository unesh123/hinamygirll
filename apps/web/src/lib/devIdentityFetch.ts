import { hinaaIdentityHeaders } from "./hinaaIdentity";

const API_PATH = /^\/(api|v1)(?:\/|$)/;

/**
 * Local dev auth has no Clerk interceptor, so panels that call fetch() directly
 * would reach the API anonymously and get "Dev user identity is required".
 * This adds the same identity header every other client call sends, to HINAA
 * API URLs only and never over a caller-supplied header.
 */
export function installDevIdentityFetch(apiBase = ""): () => void {
  const originalFetch = window.fetch;
  const base = apiBase.replace(/\/+$/, "");
  const apiOrigin = base ? new URL(base, window.location.origin).origin : null;

  window.fetch = (input, init) => {
    try {
      const raw = input instanceof Request ? input.url : String(input);
      const target = new URL(raw, window.location.origin);
      const sameApi = target.origin === window.location.origin || target.origin === apiOrigin;
      if (sameApi && API_PATH.test(target.pathname)) {
        const headers = new Headers(input instanceof Request ? input.headers : undefined);
        new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
        for (const [key, value] of Object.entries(hinaaIdentityHeaders())) {
          if (!headers.has(key)) headers.set(key, value);
        }
        return originalFetch(input, { ...init, headers });
      }
    } catch {
      // Fall through to the untouched request.
    }
    return originalFetch(input, init);
  };
  return () => {
    window.fetch = originalFetch;
  };
}
