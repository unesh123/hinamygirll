export const NEWS_BASE = "/v1/news";
export const SOCIAL_BASE = "/v1/social";

export const CADENCES = ["daily", "hourly", "manual"] as const;
export type Cadence = (typeof CADENCES)[number];

export interface Watchlist {
  id: string;
  name: string;
  topics: string[];
  keywords: string[];
  sources: string[];
  cadence: Cadence;
  dailyHour: number;
  enabled: boolean;
  lastRunAt: string | null;
  nextRunAt: string | null;
}

export interface DigestItem {
  text: string;
  urls: string[];
}

export interface Digest {
  id: string;
  watchlistId: string;
  title: string;
  items: DigestItem[];
  sources: string[];
  generatedBy: "llm" | "extractive";
  articleCount: number;
  createdAt: string | null;
}

export interface RunResult {
  digest: Digest | null;
  warnings: string[];
  deliveries: { channel: string; ok: boolean }[];
}

export interface SocialConnection {
  id: string;
  name: string;
  status: "connected" | "ready" | "requires_setup";
  connected: boolean;
  account: string;
  requirements: string;
}

export interface List<T> {
  items: T[];
  total?: number;
}

/** Call the API and return JSON; problem+json `message` becomes the Error text. */
export async function call<T>(method: "GET" | "POST" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T | null> {
  const res = await fetch(path, {
    method,
    headers: { Accept: "application/json", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return null;
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }
  if (!res.ok) {
    const p = payload as { message?: unknown; detail?: unknown } | null;
    throw new Error(typeof p?.message === "string" ? p.message : typeof p?.detail === "string" ? p.detail : `Request failed (${res.status})`);
  }
  return payload as T;
}

export const splitList = (raw: string): string[] => raw.split(",").map((s) => s.trim()).filter(Boolean);

export function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kathmandu" })} NPT`;
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
