const KEY = "hinaa.pc.session";
export function pcSessionToken(): string {
  try { return sessionStorage.getItem(KEY) || ""; } catch { return ""; }
}
export function setPCSession(token: string): void {
  if (token && !/^[A-Za-z0-9_-]{40,100}$/.test(token)) throw new Error("Invalid pairing code");
  if (token) sessionStorage.setItem(KEY, token); else sessionStorage.removeItem(KEY);
}
