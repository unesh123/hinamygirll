/**
 * brainThoughtExtractor.ts
 *
 * Extracts internal reasoning/thinking blocks (<think>, <thought>)
 * and appended bibliographic Sources sections from the assistant's stream/message:
 * - thought: The internal thinking content to be shown in Hina's Brain
 * - cleanText: The pure, articulate response to be shown in the chat bubble
 * - sources: Structured grounded evidence sources to be integrated into Hina's Brain
 */

import type { BrainSource } from "../components/ui/HinaBrainThinking";

export interface ExtractedBrainThought {
  thought: string;
  cleanText: string;
  sources: BrainSource[];
}

export function extractBrainThought(
  rawText: string,
  planThinking?: string | null
): ExtractedBrainThought {
  let thought = (planThinking || "").trim();
  let cleanText = rawText || "";
  const sources: BrainSource[] = [];

  if (!cleanText) {
    return { thought, cleanText: "", sources: [] };
  }

  // 1. Closed thinking blocks: <think>...</think> or <thought>...</thought>
  const closedRegex = /<(?:think|thought)>([\s\S]*?)<\/(?:think|thought)>/gi;
  let match: RegExpExecArray | null;

  while ((match = closedRegex.exec(cleanText)) !== null) {
    const extracted = match[1].trim();
    if (extracted) {
      thought = thought ? `${thought}\n\n${extracted}` : extracted;
    }
  }
  cleanText = cleanText.replace(closedRegex, "").trim();

  // 2. Unclosed thinking block (during live streaming): <think>...
  const unclosedRegex = /<(?:think|thought)>([\s\S]*)$/i;
  const unclosedMatch = cleanText.match(unclosedRegex);
  if (unclosedMatch) {
    const extracted = unclosedMatch[1].trim();
    if (extracted) {
      thought = thought ? `${thought}\n\n${extracted}` : extracted;
    }
    cleanText = cleanText.replace(unclosedRegex, "").trim();
  }

  // 3. Trailing closing tags: </think> or </thought> (leftover from partial streams)
  cleanText = cleanText.replace(/<\/(?:think|thought)>/gi, "").trim();

  // 4. Extract trailing Sources & References section into structured sources
  const sourcesSectionRegex = /(?:\n\s*#{1,4}\s*(?:Sources|References|Sources & References|References & Sources|Citations|External Links)[\s\S]*$)|(?:\n\s*(?:Sources & References|Sources|References)[\s\S]*$)/i;
  const sourcesMatch = cleanText.match(sourcesSectionRegex);
  if (sourcesMatch) {
    const sectionText = sourcesMatch[0];
    const items = sectionText.split(/(?=\[\d+\])/);
    for (const item of items) {
      const trimmed = item.trim();
      if (!trimmed.startsWith("[")) continue;
      const numMatch = trimmed.match(/^\[(\d+)\]\s*(.*)$/s);
      if (!numMatch) continue;
      const num = numMatch[1];
      const rest = numMatch[2].trim();

      // Check if markdown link format: [domain/title](url) — description
      const mdLinkMatch = rest.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)(?:\s*[—–-]\s*(.*))?$/s);
      if (mdLinkMatch) {
        const label = mdLinkMatch[1];
        const url = mdLinkMatch[2];
        const title = (mdLinkMatch[3] || label).trim();
        let domain = label;
        try {
          domain = new URL(url).hostname.replace(/^www\./, "");
        } catch {}
        sources.push({
          id: num,
          title,
          url,
          domain,
        });
        continue;
      }

      // Check for domain — title format: e.g. "rezero.fandom.com — Re:Zero Wiki"
      const dashMatch = rest.match(/^([^\s—–-]+(?:\.[a-zA-Z]{2,})?(?:\/[^\s—–-]*)?)\s*[—–-]\s*(.*)$/s);
      if (dashMatch) {
        const domOrUrl = dashMatch[1];
        const title = dashMatch[2].trim();
        const url = domOrUrl.startsWith("http") ? domOrUrl : `https://${domOrUrl}`;
        let domain = domOrUrl;
        try {
          domain = new URL(url).hostname.replace(/^www\./, "");
        } catch {}
        sources.push({
          id: num,
          title,
          url,
          domain,
        });
        continue;
      }

      // Fallback
      sources.push({
        id: num,
        title: rest,
        domain: "Web",
      });
    }

    cleanText = cleanText.replace(sourcesSectionRegex, "").trim();
  }

  return {
    thought: thought.trim(),
    cleanText,
    sources,
  };
}
