export type ResponseBlockKind =
  | "text"
  | "heading"
  | "list"
  | "table"
  | "code"
  | "terminal"
  | "diff"
  | "math"
  | "diagram"
  | "chart"
  | "image"
  | "gallery"
  | "citation"
  | "file"
  | "artifact"
  | "progress"
  | "warning"
  | "error"
  | "steps"
  | "quote"
  | "callout"
  | "collapsible"
  | "action_card"
  | "status"
  | "metadata"
  | "video"
  | "audio";

export interface BaseBlock {
  id?: string;
  kind: ResponseBlockKind;
  priority?: number;
  sourceRefs?: string[];
  accessibility?: {
    label?: string;
    role?: string;
    live?: "off" | "polite" | "assertive";
  };
  renderHints?: {
    collapsedByDefault?: boolean;
    variant?: string;
  };
}

export interface TextBlock extends BaseBlock {
  kind: "text";
  content: string;
}

export interface HeadingBlock extends BaseBlock {
  kind: "heading";
  level: 1 | 2 | 3 | 4 | 5 | 6;
  text: string;
}

export interface ListBlock extends BaseBlock {
  kind: "list";
  ordered: boolean;
  items: string[];
}

export interface TableBlock extends BaseBlock {
  kind: "table";
  headers: string[];
  rows: string[][];
}

export interface CodeBlockItem extends BaseBlock {
  kind: "code";
  language: string;
  code: string;
  filename?: string;
}

export interface TerminalBlock extends BaseBlock {
  kind: "terminal";
  command: string;
  output: string;
  exitCode?: number;
}

export interface DiffBlock extends BaseBlock {
  kind: "diff";
  filepath?: string;
  before: string;
  after: string;
}

export interface MathBlock extends BaseBlock {
  kind: "math";
  expression: string;
  displayMode: boolean;
}

export interface DiagramBlock extends BaseBlock {
  kind: "diagram";
  diagramType: "mermaid" | "plantuml" | "svg";
  definition: string;
}

export interface ChartBlock extends BaseBlock {
  kind: "chart";
  chartType: "bar" | "line" | "pie";
  data: Record<string, any>;
}

export interface ImageBlock extends BaseBlock {
  kind: "image";
  url: string;
  alt?: string;
  caption?: string;
}

export interface GalleryBlock extends BaseBlock {
  kind: "gallery";
  items: Array<{ url: string; title?: string; alt?: string }>;
}

export interface CitationBlock extends BaseBlock {
  kind: "citation";
  label: string;
  url: string;
  snippet?: string;
}

export interface FileBlock extends BaseBlock {
  kind: "file";
  filename: string;
  sizeBytes?: number;
  downloadUrl?: string;
  mimeType?: string;
}

export interface ArtifactBlock extends BaseBlock {
  kind: "artifact";
  artifactId: string;
  title: string;
  artifactType: string;
  content?: string;
}

export interface ProgressBlock extends BaseBlock {
  kind: "progress";
  percentage: number; // 0..100
  message: string;
  status?: "running" | "completed" | "failed";
}

export interface WarningBlock extends BaseBlock {
  kind: "warning";
  message: string;
  title?: string;
}

export interface ErrorBlock extends BaseBlock {
  kind: "error";
  message: string;
  code?: string;
}

export interface StepItem {
  title: string;
  description?: string;
  status?: "pending" | "running" | "completed" | "failed";
}

export interface StepsBlock extends BaseBlock {
  kind: "steps";
  steps: StepItem[];
}

export interface QuoteBlock extends BaseBlock {
  kind: "quote";
  quote: string;
  author?: string;
  source?: string;
  url?: string;
}

export type CalloutType = "note" | "tip" | "important" | "warning" | "caution";

export interface CalloutBlock extends BaseBlock {
  kind: "callout";
  calloutType: CalloutType;
  title?: string;
  message: string;
}

export interface CollapsibleBlock extends BaseBlock {
  kind: "collapsible";
  title: string;
  defaultOpen?: boolean;
  content: string;
}

export interface ActionCardItem {
  label: string;
  actionId: string;
  primary?: boolean;
  url?: string;
}

export interface ActionCardBlock extends BaseBlock {
  kind: "action_card";
  title: string;
  description?: string;
  actions: ActionCardItem[];
}

export interface StatusBlock extends BaseBlock {
  kind: "status";
  status: "idle" | "running" | "completed" | "failed";
  label: string;
  details?: string;
}

export interface MetadataBlock extends BaseBlock {
  kind: "metadata";
  data: Record<string, any>;
}

export interface VideoBlock extends BaseBlock {
  kind: "video";
  url: string;
  title?: string;
  poster?: string;
}

export interface AudioBlock extends BaseBlock {
  kind: "audio";
  url: string;
  title?: string;
  duration?: number;
}

export type ResponseBlock =
  | TextBlock
  | HeadingBlock
  | ListBlock
  | TableBlock
  | CodeBlockItem
  | TerminalBlock
  | DiffBlock
  | MathBlock
  | DiagramBlock
  | ChartBlock
  | ImageBlock
  | GalleryBlock
  | CitationBlock
  | FileBlock
  | ArtifactBlock
  | ProgressBlock
  | WarningBlock
  | ErrorBlock
  | StepsBlock
  | QuoteBlock
  | CalloutBlock
  | CollapsibleBlock
  | ActionCardBlock
  | StatusBlock
  | MetadataBlock
  | VideoBlock
  | AudioBlock;

/**
 * Parses raw text or structured JSON into a normalized list of ResponseBlocks (Response AST v2).
 */
export function parseResponseBlocks(input: string | ResponseBlock[]): ResponseBlock[] {
  if (Array.isArray(input)) {
    return input;
  }
  if (!input || !input.trim()) {
    return [];
  }

  const raw = input.trim();

  // 1. Try parsing JSON if structured block payload was sent
  if (raw.startsWith("[") && raw.endsWith("]")) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.every((b) => b && typeof b.kind === "string")) {
        return parsed as ResponseBlock[];
      }
    } catch {
      // Fallback to text parsing
    }
  }

  // 2. Parse Markdown fences, alert callouts, quotes, details into structured blocks
  const blocks: ResponseBlock[] = [];
  const lines = raw.split("\n");
  let currentTextBuffer: string[] = [];

  const flushText = () => {
    if (currentTextBuffer.length > 0) {
      const content = currentTextBuffer.join("\n").trim();
      if (content) {
        blocks.push({ kind: "text", content });
      }
      currentTextBuffer = [];
    }
  };

  let inFence = false;
  let fenceLanguage = "";
  let fenceBuffer: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Fenced code detection
    if (line.startsWith("```")) {
      if (inFence) {
        // Closing fence
        flushText();
        const codeContent = fenceBuffer.join("\n");
        if (fenceLanguage === "diff") {
          blocks.push({
            kind: "diff",
            before: "",
            after: codeContent,
          });
        } else if (fenceLanguage === "terminal" || fenceLanguage === "bash" || fenceLanguage === "sh") {
          blocks.push({
            kind: "terminal",
            command: codeContent.split("\n")[0] || "",
            output: codeContent.split("\n").slice(1).join("\n"),
          });
        } else if (fenceLanguage === "mermaid") {
          blocks.push({
            kind: "diagram",
            diagramType: "mermaid",
            definition: codeContent,
          });
        } else {
          blocks.push({
            kind: "code",
            language: fenceLanguage || "text",
            code: codeContent,
          });
        }
        inFence = false;
        fenceBuffer = [];
        fenceLanguage = "";
      } else {
        // Opening fence
        flushText();
        inFence = true;
        fenceLanguage = line.slice(3).trim();
      }
      continue;
    }

    if (inFence) {
      fenceBuffer.push(line);
      continue;
    }

    // Callout alert detection: > [!NOTE], > [!TIP], > [!IMPORTANT], > [!WARNING], > [!CAUTION]
    const calloutMatch = line.match(/^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$/i);
    if (calloutMatch) {
      flushText();
      const calloutType = calloutMatch[1].toLowerCase() as CalloutType;
      const title = calloutMatch[2].trim() || undefined;
      const calloutLines: string[] = [];
      while (i + 1 < lines.length && lines[i + 1].startsWith(">")) {
        i++;
        calloutLines.push(lines[i].replace(/^>\s?/, ""));
      }
      const message = calloutLines.join("\n").trim();
      if (calloutType === "warning") {
        blocks.push({
          kind: "warning",
          title,
          message: message || "Warning",
        });
      } else if (calloutType === "caution") {
        blocks.push({
          kind: "error",
          message: message || "Caution",
        });
      } else {
        blocks.push({
          kind: "callout",
          calloutType,
          title,
          message: message || title || "",
        });
      }
      continue;
    }

    // Blockquote detection: lines starting with `> ` (not a callout)
    if (line.startsWith("> ") || line === ">") {
      flushText();
      const quoteLines: string[] = [line.replace(/^>\s?/, "")];
      while (i + 1 < lines.length && (lines[i + 1].startsWith("> ") || lines[i + 1] === ">")) {
        i++;
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
      }
      blocks.push({
        kind: "quote",
        quote: quoteLines.join("\n").trim(),
      });
      continue;
    }

    // Collapsible <details><summary> detection
    if (line.trim().startsWith("<details>")) {
      flushText();
      let summaryTitle = "Details";
      const detailLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].includes("</details>")) {
        const cur = lines[i];
        const sumMatch = cur.match(/<summary>(.*?)<\/summary>/i);
        if (sumMatch) {
          summaryTitle = sumMatch[1];
        } else {
          detailLines.push(cur);
        }
        i++;
      }
      blocks.push({
        kind: "collapsible",
        title: summaryTitle,
        content: detailLines.join("\n").trim(),
      });
      continue;
    }

    currentTextBuffer.push(line);
  }

  if (inFence) {
    // Unclosed fence: recover as code
    flushText();
    blocks.push({
      kind: "code",
      language: fenceLanguage || "text",
      code: fenceBuffer.join("\n"),
    });
  } else {
    flushText();
  }

  return blocks;
}
