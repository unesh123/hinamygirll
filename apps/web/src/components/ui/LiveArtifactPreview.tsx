import React, { memo, useState } from "react";

interface LiveArtifactPreviewProps {
  code: string;
  language: string;
}

export const LiveArtifactPreview = memo(function LiveArtifactPreview({
  code,
  language,
}: LiveArtifactPreviewProps) {
  const [viewMode, setViewMode] = useState<"preview" | "code">("preview");
  const [copied, setCopied] = useState(false);

  const isSvg = language === "svg" || code.trim().startsWith("<svg");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div className="hinaa-live-artifact my-4 overflow-hidden rounded-xl border border-slate-800 bg-[#070b14] shadow-2xl">
      {/* Top Bar */}
      <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-950/70 px-4 py-2.5 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/20">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.25 9.75L16.5 12l-2.25 2.25m-4.5 0L7.5 12l2.25-2.25M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z" />
            </svg>
          </div>
          <span className="text-xs font-semibold tracking-wide text-slate-200">
            Interactive Artifact
          </span>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-mono uppercase text-pink-400 ring-1 ring-pink-500/20">
            {language}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Toggle */}
          <div className="flex rounded-lg bg-slate-900 p-0.5 ring-1 ring-slate-800">
            <button
              type="button"
              onClick={() => setViewMode("preview")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                viewMode === "preview"
                  ? "bg-cyan-600/20 text-cyan-300 ring-1 ring-cyan-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Preview
            </button>
            <button
              type="button"
              onClick={() => setViewMode("code")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                viewMode === "code"
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Code
            </button>
          </div>

          <button
            type="button"
            onClick={() => void handleCopy()}
            className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300 ring-1 ring-slate-800 transition hover:bg-slate-800 hover:text-slate-100"
          >
            {copied ? (
              <>
                <svg className="h-3.5 w-3.5 text-emerald-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <span>Copied</span>
              </>
            ) : (
              <>
                <svg className="h-3.5 w-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                </svg>
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="relative min-h-[160px] bg-slate-950/40 p-4">
        {viewMode === "preview" ? (
          isSvg ? (
            <div
              className="flex items-center justify-center py-4 [&>svg]:max-w-full [&>svg]:h-auto"
              dangerouslySetInnerHTML={{ __html: code }}
            />
          ) : (
            <iframe
              title="Artifact Sandbox"
              sandbox="allow-scripts"
              srcDoc={`<!DOCTYPE html><html><head><meta charset="utf-8"><script src="https://cdn.tailwindcss.com"></script><style>body { margin: 0; padding: 16px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; }</style></head><body>${code}</body></html>`}
              className="h-[360px] w-full rounded-lg border border-slate-800 bg-[#0f172a]"
            />
          )
        ) : (
          <pre className="overflow-x-auto rounded-lg bg-slate-950/80 p-4 font-mono text-xs leading-relaxed text-slate-300">
            <code>{code}</code>
          </pre>
        )}
      </div>
    </div>
  );
});
