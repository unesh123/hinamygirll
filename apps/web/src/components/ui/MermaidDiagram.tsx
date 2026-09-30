import React, { memo, useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

let mermaidInitialized = false;

function ensureMermaidInit() {
  if (mermaidInitialized) return;
  try {
    mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      securityLevel: "loose",
      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      themeVariables: {
        darkMode: true,
        background: "#090d16",
        mainBkg: "#0f172a",
        primaryColor: "#be185d",
        primaryTextColor: "#f8fafc",
        primaryBorderColor: "#ec4899",
        lineColor: "#38bdf8",
        secondaryColor: "#1e293b",
        secondaryTextColor: "#cbd5e1",
        secondaryBorderColor: "#334155",
        tertiaryColor: "#090d16",
        tertiaryTextColor: "#94a3b8",
        noteBkgColor: "#1e293b",
        noteTextColor: "#f1f5f9",
        noteBorderColor: "#38bdf8",
        actorBkg: "#0f172a",
        actorBorder: "#ec4899",
        actorTextColor: "#f8fafc",
        signalColor: "#38bdf8",
        signalTextColor: "#f8fafc",
      },
    });
    mermaidInitialized = true;
  } catch (err) {
    console.warn("[Mermaid] Initialization warning:", err);
  }
}

interface MermaidDiagramProps {
  code: string;
}

export const MermaidDiagram = memo(function MermaidDiagram({ code }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [renderError, setRenderError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"diagram" | "code">("diagram");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    ensureMermaidInit();
    const cleanCode = code.trim();
    if (!cleanCode) return;

    let isMounted = true;
    const renderId = `mermaid-arch-${Math.random().toString(36).substring(2, 9)}`;

    async function renderChart() {
      try {
        const { svg } = await mermaid.render(renderId, cleanCode);
        if (isMounted) {
          setSvgContent(svg);
          setRenderError(null);
        }
      } catch (err) {
        if (isMounted) {
          // If mermaid fails (e.g. partial stream or unsupported syntax), fallback to code
          setRenderError(err instanceof Error ? err.message : "Diagram rendering in progress...");
        }
      }
    }

    void renderChart();

    return () => {
      isMounted = false;
      const el = document.getElementById(renderId);
      if (el) el.remove();
      const dEl = document.getElementById(`d${renderId}`);
      if (dEl) dEl.remove();
    };
  }, [code]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div className="hinaa-architecture-artifact my-4 overflow-hidden rounded-xl border border-slate-800 bg-[#070b14] shadow-2xl">
      {/* Top Header & Mode Switcher */}
      <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-950/70 px-4 py-2.5 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-pink-500/10 text-pink-400 ring-1 ring-pink-500/20">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.14 2.14a1.5 1.5 0 002.12 0l3.74-3.74" />
            </svg>
          </div>
          <span className="text-xs font-semibold tracking-wide text-slate-200">
            Architecture Blueprint
          </span>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-cyan-400 ring-1 ring-cyan-500/20">
            Mermaid 2.0
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* View Mode Toggle */}
          <div className="flex rounded-lg bg-slate-900 p-0.5 ring-1 ring-slate-800">
            <button
              type="button"
              onClick={() => setViewMode("diagram")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                viewMode === "diagram"
                  ? "bg-pink-600/20 text-pink-300 ring-1 ring-pink-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Visual
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
              Source
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

      {/* Main Content Area */}
      <div className="relative min-h-[140px] p-4">
        {viewMode === "diagram" && (
          <div className="flex w-full items-center justify-center overflow-x-auto py-2">
            {svgContent ? (
              <div
                ref={containerRef}
                className="mermaid-svg-container max-w-full [&>svg]:mx-auto [&>svg]:h-auto [&>svg]:max-w-full"
                dangerouslySetInnerHTML={{ __html: svgContent }}
              />
            ) : renderError ? (
              <div className="flex flex-col items-center justify-center gap-2 py-6 text-center text-slate-400">
                <span className="text-xs text-amber-400/90 font-mono">
                  {renderError.includes("progress") ? "Rendering dynamic blueprint..." : "Blueprint syntax in progress"}
                </span>
                <pre className="max-h-48 overflow-auto rounded bg-slate-900/60 p-3 font-mono text-[11px] text-slate-300">
                  {code}
                </pre>
              </div>
            ) : (
              <div className="flex items-center gap-2 py-8 text-xs text-slate-400">
                <div className="h-3 w-3 animate-spin rounded-full border border-pink-500 border-t-transparent" />
                <span>Compiling architectural layout...</span>
              </div>
            )}
          </div>
        )}

        {viewMode === "code" && (
          <pre className="overflow-x-auto rounded-lg bg-slate-950/80 p-4 font-mono text-xs leading-relaxed text-slate-300">
            <code>{code}</code>
          </pre>
        )}
      </div>
    </div>
  );
});
