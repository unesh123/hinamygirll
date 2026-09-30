import React, { memo, useEffect, useRef, useState, type ReactNode } from "react";
import Markdown, { type Components, defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { MermaidDiagram } from "./MermaidDiagram";
import { LiveArtifactPreview } from "./LiveArtifactPreview";
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

  let detectedLang = "Code";
  if (React.isValidElement(children)) {
    const childClass = (children.props as any)?.className || "";
    const match = /language-(\w+)/.exec(childClass);
    if (match) detectedLang = match[1].toUpperCase();
  }

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
        <span className="font-mono text-[11px] font-semibold tracking-wider text-pink-400">{detectedLang}</span>
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
  pre: ({ children }) => {
    if (React.isValidElement(children)) {
      const childProps = children.props as any;
      const childClass = childProps?.className || "";
      if (
        childClass.includes("language-mermaid") ||
        childClass.includes("language-html") ||
        childClass.includes("language-svg")
      ) {
        return <>{children}</>;
      }
    }
    return <CodeBlock>{children}</CodeBlock>;
  },
  code: ({ className, children, ...props }) => {
    const match = /language-(\w+)/.exec(className || "");
    const lang = match ? match[1].toLowerCase() : "";
    const raw = String(children).replace(/\n$/, "");

    if (lang === "mermaid") {
      return <MermaidDiagram code={raw} />;
    }
    if (lang === "html" || lang === "svg") {
      return <LiveArtifactPreview code={raw} language={lang} />;
    }
    return <code className={className} {...props}>{children}</code>;
  },
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
