import type { SourceItem } from "../../components/ui/SourceCard";

export type ResearchSourceSaveOutcome = {
  state: "saved" | "needs_project" | "failed";
  message: string;
};

type CompletedToolResult = { toolName?: unknown; result?: unknown };

type UntrustedResearchSource = {
  id?: unknown;
  title?: unknown;
  url?: unknown;
  snippet?: unknown;
};

const RESEARCH_TOOL_NAMES = new Set([
  "web_search",
  "web_answer",
  "web_research",
  "web_research_status",
  "web_extract",
  "finance_research",
]);

/** Convert completed, attributable research results into card-safe source data. */
export function collectResearchSources(toolResults: CompletedToolResult[]): SourceItem[] {
  const seenUrls = new Set<string>();
  const sources: SourceItem[] = [];
  for (const entry of toolResults) {
    if (typeof entry.toolName !== "string" || !RESEARCH_TOOL_NAMES.has(entry.toolName)) continue;
    const envelope = entry.result && typeof entry.result === "object" ? entry.result as Record<string, unknown> : null;
    const data = envelope && envelope.data && typeof envelope.data === "object" ? envelope.data as Record<string, unknown> : envelope;
    if (!data || data.status === "error" || envelope?.status === "error" || data.error) continue;
    const rawSources = Array.isArray(data.sources) ? data.sources : [];
    for (const rawSource of rawSources) {
      const source = rawSource && typeof rawSource === "object" ? rawSource as UntrustedResearchSource : null;
      if (!source || typeof source.url !== "string" || !/^https?:\/\//i.test(source.url) || seenUrls.has(source.url)) continue;
      let domain = "Source";
      try { domain = new URL(source.url).hostname.replace(/^www\./, "") || "Source"; } catch { continue; }
      seenUrls.add(source.url);
      sources.push({
        id: typeof source.id === "string" && source.id ? source.id : `source-${sources.length + 1}`,
        title: typeof source.title === "string" && source.title ? source.title : "Untitled source",
        url: source.url,
        snippet: typeof source.snippet === "string" && source.snippet ? source.snippet : "No preview was provided.",
        domain,
        index: sources.length,
      });
    }
  }
  return sources;
}

/**
 * Persist one user-selected research source to the currently selected local
 * project. This is a local artifact write only; it never opens the source,
 * requests a provider, or performs an external browser action.
 */
export async function saveResearchSourceToActiveProject(source: SourceItem): Promise<ResearchSourceSaveOutcome> {
  const projectId = window.localStorage.getItem("hinaa-active-project-id");
  if (!projectId) {
    return { state: "needs_project", message: "Select a local project first to save this source." };
  }

  try {
    const response = await fetch(`/api/v1/projects/${encodeURIComponent(projectId)}/artifacts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "research",
        title: source.title,
        content: source.snippet,
        sourceUrl: source.url,
        metadata: { sourceId: source.id, domain: source.domain, origin: "research-source-card" },
      }),
    });
    if (!response.ok) {
      return { state: "failed", message: "Could not save this source locally." };
    }
    return { state: "saved", message: "Saved to the active local project." };
  } catch {
    return { state: "failed", message: "Could not save this source locally." };
  }
}
