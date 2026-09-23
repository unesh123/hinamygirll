/**
 * turnFailure.ts — one human line for a failed request.
 *
 * A failed turn used to throw `HTTP 502 (<whole response body>)`, and the body
 * was whatever the network edge handed back. With the API behind a Cloudflare
 * quick tunnel, that meant a dead tunnel put a ~7KB HTML error page inside an
 * assistant chat bubble. Nothing here can promise the backend is healthy, so it
 * promises two things instead: the reader gets one line, and that line never
 * contains upstream markup.
 */

const MAX_LINE = 220;

/** Statuses the edge produces on its own when the origin never answered. */
const GATEWAY_STATUSES = new Set([500, 502, 503, 504, 521, 522, 523, 524, 530]);

export class TurnFailure extends Error {
  readonly code?: string;
  readonly status?: number;
  readonly retryable?: boolean;

  constructor(
    message: string,
    init?: { code?: string; status?: number; retryable?: boolean },
  ) {
    super(message);
    this.name = "TurnFailure";
    this.code = init?.code;
    this.status = init?.status;
    this.retryable = init?.retryable;
  }
}

export function looksLikeHtml(text: string): boolean {
  const head = text.slice(0, 512).trimStart().toLowerCase();
  if (!head.startsWith("<")) return false;
  return head.startsWith("<!doctype html") || head.startsWith("<html") || head.startsWith("<head") ||
    /<\/[a-z][a-z0-9]*>/i.test(head);
}

/**
 * Flatten anything into a single displayable line: markup dropped, whitespace
 * collapsed, length capped.
 */
export function singleLine(value: unknown, fallback = ""): string {
  let text = typeof value === "string" ? value : value == null ? "" : String(value);
  text = text.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ");
  text = text.replace(/<[^>]*>/g, " ").replace(/&(?:nbsp|amp|lt|gt|quot|#39);/gi, " ");
  text = text.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
  if (!text) return fallback;
  if (text.length <= MAX_LINE) return text;
  return `${text.slice(0, MAX_LINE - 1).trimEnd()}…`;
}

/**
 * The backend's own error vocabulary, worded the way the realtime WebSocket
 * words it, so a REST turn and a live turn blame the same thing in the same
 * sentence. Unknown codes fall through to the caller's message.
 */
const CODE_LINES: Record<string, string> = {
  PROVIDER_CONFIGURATION_MISSING:
    "No brain is configured for this mode, so HINAA could not answer.",
  PROVIDER_KEY_INVALID: "The selected brain rejected its API key.",
  PROVIDER_AUTH_FAILED: "The selected brain refused its credentials.",
  PROVIDER_RATE_LIMIT: "The selected brain is rate limited — try again shortly or switch brains.",
  PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE:
    "The selected gateway has no upstream account free right now.",
  PROVIDER_TIMEOUT: "The selected brain did not answer before the live safety timeout.",
  PROVIDER_UNAVAILABLE: "The selected brain could not complete this turn.",
  PROVIDER_UNREACHABLE: "The selected brain is unreachable from the local backend.",
  PROVIDER_HOST_UNREACHABLE: "The selected brain's host is unreachable from this machine.",
  MODEL_UNAVAILABLE: "The selected model is not available on this brain.",
  OFFLINE: "This machine has no route to the selected brain.",
  VALIDATION_ERROR: "HINAA rejected the request as malformed.",
  AUTH_ERROR: "HINAA refused the request — the caller was not recognised.",
};

export function describeCode(code?: string, detail?: string): string | null {
  if (!code) return null;
  const mapped = CODE_LINES[code.toUpperCase()];
  if (mapped) return mapped;
  const upper = code.toUpperCase();
  if (upper.startsWith("PROVIDER_"))
    return singleLine(detail, `The selected brain failed (${upper}).`);
  return null;
}

/**
 * A request that threw never produced a response, so there is no status and no
 * body — only the caller's own words plus the transport reason. `String(error)`
 * would render "TypeError: Failed to fetch", which names no layer.
 */
export function describeThrownFailure(value: unknown, prefix: string): string {
  const reason = singleLine(value instanceof Error ? value.message : value);
  return singleLine(reason ? `${prefix} — ${reason}.` : `${prefix}.`);
}

export interface ResponseFailureInput {
  status: number;
  body?: string;
  contentType?: string | null;
}

/**
 * Turn an HTTP response into the one line a user should read. JSON error bodies
 * keep their own message; HTML bodies (an edge error page) are never quoted,
 * because the only thing they prove is which layer answered.
 */
export function describeResponseFailure(input: ResponseFailureInput): string {
  const { status, body = "", contentType } = input;
  const isHtml =
    looksLikeHtml(body) ||
    (contentType ?? "").toLowerCase().includes("text/html");

  // An HTML answer came from a proxy or an edge node, so the status band is the
  // only evidence available. The page itself is never quoted.
  if (isHtml) {
    if (status === 401 || status === 403) {
      return `HINAA's edge refused this request (HTTP ${status}).`;
    }
    if (GATEWAY_STATUSES.has(status)) {
      return `HINAA's backend did not answer — the network edge returned HTTP ${status} instead of her.`;
    }
    if (status >= 500) return `HINAA's backend failed this request (HTTP ${status}).`;
    if (status >= 400) {
      return `Something between this window and HINAA answered this request (HTTP ${status}).`;
    }
    return `HINAA's API answered with a web page instead of its own response (HTTP ${status}).`;
  }

  const parsed = safeJson(body);
  const detail = detailFromBody(parsed);
  if (detail) {
    return singleLine(
      describeCode(readCode(parsed), detail) || detail,
      fallbackFor(status),
    );
  }

  if (status === 401 || status === 403) {
    return `HINAA refused the request — this browser was not recognised (HTTP ${status}).`;
  }
  if (status === 404) return `HINAA has no endpoint for that (HTTP ${status}).`;
  if (status === 429) return "HINAA is being rate limited — wait a moment and try again.";
  if (status >= 500) return `HINAA's backend failed this request (HTTP ${status}).`;
  return `HINAA could not complete the request (HTTP ${status}).`;
}

function fallbackFor(status: number): string {
  return `HINAA could not complete the request (HTTP ${status}).`;
}

function safeJson(body: string): unknown {
  try {
    return JSON.parse(body);
  } catch {
    return null;
  }
}

function readCode(value: unknown): string | undefined {
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of ["code", "error_code", "errorCode"]) {
      if (typeof record[key] === "string") return record[key] as string;
    }
  }
  return undefined;
}

/** FastAPI puts the reason in `detail`, which can be a string or a validation list. */
function detailFromBody(value: unknown): string {
  if (typeof value === "string") return singleLine(value);
  if (!value || typeof value !== "object") return "";
  const record = value as Record<string, unknown>;
  for (const key of ["detail", "message", "error", "userMessage", "user_message"]) {
    const candidate = record[key];
    if (typeof candidate === "string" && candidate.trim()) return singleLine(candidate);
    if (Array.isArray(candidate) && candidate.length > 0) {
      const first = candidate[0];
      const text =
        typeof first === "string"
          ? first
          : first && typeof first === "object"
          ? String((first as Record<string, unknown>).msg ?? "")
          : "";
      if (text.trim()) return singleLine(text);
    }
    if (Array.isArray(candidate)) continue;
  }
  return "";
}
