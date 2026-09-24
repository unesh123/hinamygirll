import { memo, useEffect, useRef, useState, type ReactNode } from "react";
import Markdown, { type Components, defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import "./ResponseMarkdown.css";

/** No raw HTML or executable URL protocols may enter a conversation surface. */
export function responseUrlTransform(url: string): string {
  const safe = defaultUrlTransform(url);
  if (!safe || /[\u0000-\u0020\u007f]/.test(safe) || /^(?:\/\/|\\)/.test(safe)) return "";
  return /^(?:https?:|mailto:|#|\/)/i.test(safe) || !/^[a-z][a-z\d+.-]*:/i.test(safe) ? safe : "";
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const block = useRef<HTMLPreElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(block.current?.textContent ?? "");
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopyState("idle"), 2000);
  };
  return (
    <div className="response-code-block">
      <div className="response-code-toolbar">
        <span>Code</span>
        <button type="button" onClick={() => void copy()} aria-label="Copy code">
          {copyState === "copied" ? "Copied ✓" : copyState === "failed" ? "Copy failed — retry" : "Copy code"}
        </button>
        <span className="response-sr-only" role="status">{copyState === "copied" ? "Code copied" : copyState === "failed" ? "Unable to copy code" : ""}</span>
      </div>
      <pre ref={block} tabIndex={0} aria-label="Code block">{children}</pre>
    </div>
  );
}

const components: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  table: ({ children }) => <div className="response-table-scroll" role="region" aria-label="Response table" tabIndex={0}><table>{children}</table></div>,
  a: ({ href, children }) => href ? <a href={href} target={href.startsWith("#") ? undefined : "_blank"} rel="noopener noreferrer">{children}</a> : <span>{children}</span>,
  // Model-authored image URLs remain explicit links; artifacts use the protected artifact UI.
  img: ({ src, alt }) => typeof src === "string" && src ? <a href={src} target="_blank" rel="noopener noreferrer">{alt || "View image"}</a> : <span>{alt}</span>,
};

/**
 * Progressive streaming render: while a document is mid-generation, an open
 * code fence would otherwise dump the entire remaining tail as raw text until
 * the fence closes. Closing unclosed fences at DISPLAY time keeps long
 * documents rendering as real Markdown live, byte-for-byte identical once the
 * stream completes (final render never uses this).
 */
function closeStreamingFences(text: string): string {
  const fenceMatches = text.match(/^(```|~~~)/gm);
  if (!fenceMatches || fenceMatches.length % 2 === 0) return text;
  return `${text}\n\`\`\``;
}

/** CommonMark parses unfinished fences without dropping the final streamed line. */
export const ResponseMarkdown = memo(function ResponseMarkdown({ text, streaming }: { text: string; streaming?: boolean }) {
  const display = streaming ? closeStreamingFences(text) : text;
  return <div className="response-markdown" data-streaming={streaming ? "true" : undefined}><Markdown remarkPlugins={[remarkGfm]} skipHtml urlTransform={responseUrlTransform} components={components}>{display}</Markdown></div>;
});
