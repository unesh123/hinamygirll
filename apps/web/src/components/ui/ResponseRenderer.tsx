import { memo, useState } from "react";
import { type ResponseBlock, parseResponseBlocks } from "./ResponseBlock";
import { ResponseMarkdown } from "./ResponseMarkdown";

export interface ResponseRendererProps {
  content: string | ResponseBlock[];
  className?: string;
  onActionClick?: (actionId: string) => void;
}

export const ResponseRenderer = memo(function ResponseRenderer({
  content,
  className = "response-renderer",
  onActionClick,
}: ResponseRendererProps) {
  const blocks = parseResponseBlocks(content);

  if (blocks.length === 0) {
    return null;
  }

  return (
    <div className={className} data-testid="response-renderer">
      {blocks.map((block, idx) => {
        const key = block.id ?? `block-${block.kind}-${idx}`;

        switch (block.kind) {
          case "text":
            return <ResponseMarkdown key={key} text={block.content} />;

          case "code":
            return (
              <div key={key} className="response-block-code my-3">
                {block.filename && (
                  <div className="text-xs text-sakura-text-muted px-3 py-1 bg-sakura-card-bg/60 border border-b-0 border-sakura-border/40 rounded-t-md font-mono">
                    {block.filename}
                  </div>
                )}
                <ResponseMarkdown text={`\`\`\`${block.language}\n${block.code}\n\`\`\``} />
              </div>
            );

          case "terminal":
            return (
              <div
                key={key}
                className="response-block-terminal my-3 rounded-md overflow-hidden border border-sakura-border/50 bg-black/80 font-mono text-xs text-green-400"
              >
                <div className="bg-white/10 px-3 py-1 text-[11px] text-white/70 flex items-center justify-between">
                  <span>Terminal</span>
                  {block.exitCode !== undefined && (
                    <span className={block.exitCode === 0 ? "text-green-400" : "text-red-400"}>
                      exit {block.exitCode}
                    </span>
                  )}
                </div>
                <div className="p-3">
                  <div className="text-white/90 mb-1">$ {block.command}</div>
                  <pre className="text-white/70 whitespace-pre-wrap">{block.output}</pre>
                </div>
              </div>
            );

          case "diff":
            return (
              <div
                key={key}
                className="response-block-diff my-3 border border-sakura-border/40 rounded-md overflow-hidden bg-black/60 font-mono text-xs"
              >
                {block.filepath && (
                  <div className="bg-white/10 px-3 py-1 text-white/80 font-semibold">{block.filepath}</div>
                )}
                <pre className="p-3 text-sakura-text whitespace-pre-wrap">{block.after}</pre>
              </div>
            );

          case "warning":
            return (
              <div
                key={key}
                role="alert"
                className="response-block-warning my-3 p-3 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-200 text-sm"
              >
                {block.title && <div className="font-semibold mb-1">{block.title}</div>}
                <div>{block.message}</div>
              </div>
            );

          case "error":
            return (
              <div
                key={key}
                role="alert"
                className="response-block-error my-3 p-3 rounded-md bg-red-500/10 border border-red-500/30 text-red-200 text-sm"
              >
                {block.code && <div className="font-mono text-xs text-red-400 mb-1">[{block.code}]</div>}
                <div>{block.message}</div>
              </div>
            );

          case "callout": {
            const themeMap: Record<string, { bg: string; border: string; text: string; label: string }> = {
              note: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-200", label: "Note" },
              tip: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-200", label: "Tip" },
              important: { bg: "bg-purple-500/10", border: "border-purple-500/30", text: "text-purple-200", label: "Important" },
              warning: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-200", label: "Warning" },
              caution: { bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-200", label: "Caution" },
            };
            const theme = themeMap[block.calloutType] ?? themeMap.note;
            return (
              <aside
                key={key}
                role="note"
                aria-label={block.title || theme.label}
                className={`response-block-callout my-3 p-3.5 rounded-lg ${theme.bg} border ${theme.border} ${theme.text} text-sm`}
              >
                <div className="font-semibold text-xs uppercase tracking-wide opacity-90 mb-1">
                  {block.title || theme.label}
                </div>
                <div className="leading-relaxed whitespace-pre-wrap">{block.message}</div>
              </aside>
            );
          }

          case "quote":
            return (
              <blockquote
                key={key}
                className="response-block-quote my-3 pl-4 border-l-2 border-sakura-primary/60 text-sakura-text/90 italic text-sm"
              >
                <p>{block.quote}</p>
                {(block.author || block.source) && (
                  <cite className="block text-xs not-italic text-sakura-text-muted mt-1">
                    — {block.author}
                    {block.source && ` (${block.source})`}
                  </cite>
                )}
              </blockquote>
            );

          case "collapsible":
            return (
              <details
                key={key}
                open={block.defaultOpen}
                className="response-block-collapsible my-3 p-2.5 rounded-md border border-sakura-border/40 bg-sakura-card-bg/30 text-sm"
              >
                <summary className="cursor-pointer font-medium text-sakura-text hover:text-sakura-primary focus:outline-none focus:ring-1 focus:ring-sakura-primary select-none">
                  {block.title}
                </summary>
                <div className="mt-2.5 pt-2 border-t border-sakura-border/20 text-sakura-text/90">
                  <ResponseMarkdown text={block.content} />
                </div>
              </details>
            );

          case "steps":
            return (
              <ol key={key} className="response-block-steps my-3 space-y-2 text-sm">
                {block.steps.map((step, sIdx) => {
                  const statusColors: Record<string, string> = {
                    completed: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
                    running: "bg-blue-500/20 text-blue-300 border-blue-500/40 animate-pulse",
                    failed: "bg-red-500/20 text-red-300 border-red-500/40",
                    pending: "bg-white/10 text-sakura-text-muted border-white/20",
                  };
                  const badgeClass = statusColors[step.status ?? "pending"];
                  return (
                    <li
                      key={`step-${sIdx}`}
                      className="flex items-start gap-3 p-2 rounded border border-sakura-border/20 bg-sakura-card-bg/20"
                    >
                      <span className={`px-1.5 py-0.5 rounded text-[11px] font-mono border ${badgeClass}`}>
                        {sIdx + 1}
                      </span>
                      <div className="flex-1">
                        <div className="font-medium text-sakura-text">{step.title}</div>
                        {step.description && (
                          <div className="text-xs text-sakura-text-muted mt-0.5">{step.description}</div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
            );

          case "action_card":
            return (
              <div
                key={key}
                className="response-block-action-card my-3 p-4 rounded-lg border border-sakura-border/50 bg-sakura-card-bg/50 text-sm shadow-sm"
              >
                <h4 className="font-semibold text-sakura-text mb-1">{block.title}</h4>
                {block.description && (
                  <p className="text-xs text-sakura-text-muted mb-3">{block.description}</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {block.actions.map((act) => (
                    <button
                      key={act.actionId}
                      type="button"
                      onClick={() => {
                        if (act.url) {
                          window.open(act.url, "_blank", "noopener,noreferrer");
                        } else {
                          onActionClick?.(act.actionId);
                        }
                      }}
                      className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                        act.primary
                          ? "bg-sakura-primary text-black hover:bg-sakura-primary/90"
                          : "bg-white/10 text-sakura-text hover:bg-white/20 border border-sakura-border/30"
                      }`}
                    >
                      {act.label}
                    </button>
                  ))}
                </div>
              </div>
            );

          case "status":
            return (
              <div key={key} className="response-block-status inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium border border-sakura-border/40 bg-sakura-card-bg/40 my-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    block.status === "completed"
                      ? "bg-emerald-400"
                      : block.status === "running"
                      ? "bg-blue-400 animate-ping"
                      : block.status === "failed"
                      ? "bg-red-400"
                      : "bg-amber-400"
                  }`}
                />
                <span className="text-sakura-text">{block.label}</span>
                {block.details && <span className="text-sakura-text-muted">({block.details})</span>}
              </div>
            );

          case "progress":
            return (
              <div key={key} className="response-block-progress my-3 p-3 rounded-md bg-sakura-card-bg/40 border border-sakura-border/40 text-sm">
                <div className="flex justify-between mb-1.5 text-xs text-sakura-text-muted">
                  <span>{block.message}</span>
                  <span>{Math.round(block.percentage)}%</span>
                </div>
                <div className="w-full bg-white/10 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-sakura-primary h-full transition-all duration-300"
                    style={{ width: `${Math.min(100, Math.max(0, block.percentage))}%` }}
                  />
                </div>
              </div>
            );

          case "image":
            return (
              <div key={key} className="response-block-image my-3">
                <a href={block.url} target="_blank" rel="noopener noreferrer" className="text-sakura-primary underline text-sm">
                  {block.alt || "View image"}
                </a>
                {block.caption && <p className="text-xs text-sakura-text-muted mt-1">{block.caption}</p>}
              </div>
            );

          case "video":
            return (
              <div key={key} className="response-block-video my-3 rounded-lg overflow-hidden border border-sakura-border/40">
                <video src={block.url} poster={block.poster} controls className="w-full max-h-96" />
                {block.title && <div className="p-2 text-xs text-sakura-text-muted bg-black/40">{block.title}</div>}
              </div>
            );

          case "audio":
            return (
              <div key={key} className="response-block-audio my-3 p-3 rounded-lg border border-sakura-border/40 bg-sakura-card-bg/40">
                {block.title && <div className="text-xs text-sakura-text font-medium mb-1.5">{block.title}</div>}
                <audio src={block.url} controls className="w-full h-8" />
              </div>
            );

          default:
            return <ResponseMarkdown key={key} text={JSON.stringify(block)} />;
        }
      })}
    </div>
  );
});
