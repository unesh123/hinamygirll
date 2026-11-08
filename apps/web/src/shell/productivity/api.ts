export const PRODUCTIVITY_BASE = "/v1/productivity";

export const PLATFORMS = ["instagram", "tiktok", "youtube", "x", "linkedin", "facebook", "other"] as const;
export const POST_STATUSES = ["idea", "draft", "scheduled", "published"] as const;
export const PROJECT_STATUSES = ["planning", "active", "blocked", "done"] as const;
export const PRIORITIES = ["low", "medium", "high"] as const;

export type Platform = (typeof PLATFORMS)[number];
export type PostStatus = (typeof POST_STATUSES)[number];
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];
export type Priority = (typeof PRIORITIES)[number];

export interface ContentPost {
  id: string;
  platform: Platform;
  title: string;
  caption: string;
  scheduledFor: string | null;
  status: PostStatus;
  tags: string[];
  notes: string;
}

export interface WeekDay {
  date: string;
  weekday: string;
  posts: ContentPost[];
}

export interface WeekView {
  weekStart: string;
  weekEnd: string;
  total: number;
  days: WeekDay[];
}

export interface SalesRecord {
  id: string;
  occurredOn: string;
  amount: number;
  currency: string;
  source: string;
  customer: string;
  product: string;
  notes: string;
}

export interface SalesSummary {
  period: "day" | "week" | "month";
  currency: string;
  total: number;
  count: number;
  trend: { previousTotal: number; change: number; changePct: number | null; direction: "up" | "down" | "flat" };
  series: { date: string; total: number }[];
}

export interface Project {
  id: string;
  name: string;
  status: ProjectStatus;
  priority: Priority;
  dueDate: string | null;
  progress: number;
  nextAction: string;
  notes: string;
}

export interface Page<T> {
  items: T[];
  total: number;
}

/** Send a JSON mutation; the backend's problem+json `message` becomes the Error text. */
export async function send<T>(method: "POST" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T | null> {
  const res = await fetch(`${PRODUCTIVITY_BASE}${path}`, {
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
    const message = (payload as { message?: unknown; detail?: unknown } | null)?.message;
    const detail = (payload as { detail?: unknown } | null)?.detail;
    throw new Error(
      typeof message === "string" ? message : typeof detail === "string" ? detail : `Request failed (${res.status})`,
    );
  }
  return payload as T;
}

// ---- dates (local calendar days, never UTC) ----

const pad = (n: number) => String(n).padStart(2, "0");

export function toIsoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function parseIsoDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function mondayOf(d: Date): Date {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  out.setDate(out.getDate() - ((out.getDay() + 6) % 7));
  return out;
}

export function addDays(iso: string, days: number): string {
  const d = parseIsoDate(iso);
  d.setDate(d.getDate() + days);
  return toIsoDate(d);
}

export function formatDay(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function formatMoney(amount: number, currency: string): string {
  return `${currency} ${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function trendPercent(summary: SalesSummary): number | null {
  const { changePct, previousTotal, change } = summary.trend;
  if (changePct != null) return changePct;
  return previousTotal > 0 ? (change / previousTotal) * 100 : null;
}

/** Points for an inline SVG polyline, scaled into a width x height box. */
export function sparklinePoints(values: number[], width: number, height: number, pad = 2): string {
  if (values.length === 0) return "";
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const step = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;
  return values
    .map((v, i) => `${(pad + i * step).toFixed(1)},${(height - pad - ((v - min) / span) * (height - pad * 2)).toFixed(1)}`)
    .join(" ");
}
