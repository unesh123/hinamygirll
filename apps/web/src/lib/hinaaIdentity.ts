export const HINAA_DEV_USER = "local-dev-user";

/** Identity headers every browser request must carry. */
export function hinaaIdentityHeaders(): Record<string, string> {
  return { "X-HINAA-Dev-User": HINAA_DEV_USER };
}

function isLocalHinaApiUrl(url: string, apiBase: string): boolean {
  try {
    const target = new URL(url, window.location.origin);
    const origins = [window.location.origin];
    if (apiBase) origins.push(new URL(apiBase, window.location.origin).origin);
    return origins.includes(target.origin) && /^\/(api|v1)(?:\/|$)/.test(target.pathname);
  } catch {
    return false;
  }
}

let installed = false;

/**
 * Local (non-Clerk) mode counterpart of ClerkFetchInterceptor: every Hina API
 * call carries the dev identity, so pages that use plain fetch are authorized.
 * Headers the caller already set are kept.
 */
export function installLocalIdentityFetch(apiBase = ""): void {
  if (installed || typeof window === "undefined") return;
  installed = true;
  const originalFetch = window.fetch.bind(window);
  window.fetch = (resource, config) => {
    const url = typeof resource === "string" ? resource : resource instanceof URL ? resource.toString() : resource.url;
    if (!isLocalHinaApiUrl(url, apiBase)) return originalFetch(resource, config);
    const headers = new Headers(resource instanceof Request ? resource.headers : undefined);
    new Headers(config?.headers).forEach((value, key) => headers.set(key, value));
    for (const [key, value] of Object.entries(hinaaIdentityHeaders())) {
      if (!headers.has(key)) headers.set(key, value);
    }
    return originalFetch(resource, { ...config, headers });
  };
}
