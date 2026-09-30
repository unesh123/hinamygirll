import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

let mermaidInitialized = false;

function ensureMermaidInit() {
  if (mermaidInitialized) return;
  try {
    mermaid.initialize({
      startOnLoad: false,
      theme: "base",
      securityLevel: "loose",
      fontFamily: "Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      fontSize: 14,
      themeVariables: {
        darkMode: true,
        background: "transparent",
        primaryColor: "#0f172a",
        primaryTextColor: "#ffffff",
        primaryBorderColor: "#38bdf8",
        lineColor: "#60a5fa",
        secondaryColor: "#1e1b4b",
        secondaryTextColor: "#ffffff",
        secondaryBorderColor: "#a855f7",
        tertiaryColor: "#090d16",
        tertiaryTextColor: "#ffffff",
        tertiaryBorderColor: "#06b6d4",
        noteBkgColor: "#1e293b",
        noteTextColor: "#f8fafc",
        noteBorderColor: "#38bdf8",
        actorBkg: "#0f172a",
        actorBorder: "#ec4899",
        actorTextColor: "#ffffff",
        actorLineColor: "#ec4899",
        signalColor: "#38bdf8",
        signalTextColor: "#ffffff",
        labelBoxBkgColor: "#090d16",
        labelBoxBorderColor: "#38bdf8",
        labelTextColor: "#ffffff",
        loopTextColor: "#ffffff",
        nodeBorder: "#38bdf8",
        mainBkg: "#0b1329",
        nodeTextColor: "#ffffff",
        textColor: "#ffffff",
        edgeLabelBackground: "#090d16",
        clusterBkg: "#060913",
        clusterBorder: "#3b82f6",
        titleColor: "#ffffff",
      },
      flowchart: {
        htmlLabels: true,
        curve: "basis",
        padding: 20,
        nodeSpacing: 50,
        rankSpacing: 50,
        useMaxWidth: true,
      },
    });
    mermaidInitialized = true;
  } catch (err) {
    console.warn("[Mermaid] Initialization warning:", err);
  }
}

const INJECTED_SVG_STYLES = `
  <style>
    /* High contrast glowing node styling */
    .node rect, .node circle, .node ellipse, .node polygon, .node path {
      fill: #0b1528 !important;
      stroke: #38bdf8 !important;
      stroke-width: 2px !important;
      filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5)) !important;
      rx: 8px !important;
      ry: 8px !important;
    }
    /* ALL text: nodes, labels, foreignObjects, spans, divs */
    text, .label, .label text, .nodeLabel, span.nodeLabel, p, div, .actor, .actor text, tspan {
      fill: #ffffff !important;
      color: #ffffff !important;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
      font-weight: 600 !important;
      font-size: 14px !important;
      line-height: 1.4 !important;
      text-shadow: 0 1px 3px rgba(0,0,0,0.9) !important;
    }
    /* Flow lines and arrows */
    .flowchart-link, .edgePath path, path.path {
      stroke: #60a5fa !important;
      stroke-width: 2px !important;
      opacity: 0.95 !important;
    }
    .marker, #statediagram-barbEnd {
      fill: #60a5fa !important;
      stroke: #60a5fa !important;
    }
    /* Edge condition labels */
    .edgeLabel {
      background-color: #030712 !important;
      fill: #e0f2fe !important;
      color: #e0f2fe !important;
      font-size: 12px !important;
      font-weight: 600 !important;
      padding: 3px 8px !important;
      border-radius: 4px !important;
    }
    .edgeLabel rect {
      fill: #030712 !important;
      stroke: #1e293b !important;
      opacity: 0.95 !important;
      rx: 4px !important;
    }
    /* Subgraphs and clusters */
    .cluster rect {
      fill: #060b18 !important;
      stroke: #6366f1 !important;
      stroke-width: 1.5px !important;
      stroke-dasharray: 4 4 !important;
      rx: 10px !important;
    }
    .cluster-label text, .cluster-label span {
      fill: #c7d2fe !important;
      color: #c7d2fe !important;
      font-size: 14px !important;
      font-weight: 700 !important;
      letter-spacing: 0.05em !important;
      text-transform: uppercase !important;
    }
  </style>
`;

interface MermaidDiagramProps {
  code: string;
}

export const MermaidDiagram = memo(function MermaidDiagram({ code }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [renderError, setRenderError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"diagram" | "code">("diagram");
  const [copied, setCopied] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Fullscreen Pan & Zoom state
  const [modalZoom, setModalZoom] = useState(1.2);
  const [modalPan, setModalPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  const handleExportSvg = () => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "architecture-blueprint.svg";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 4000);
  };

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
          // Inject scoped styles into the SVG header for maximum contrast
          const enhancedSvg = svg.replace(/<svg\b([^>]*)>/, `<svg$1>${INJECTED_SVG_STYLES}`);
          setSvgContent(enhancedSvg);
          setRenderError(null);
        }
      } catch (err) {
        if (isMounted) {
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

  // Keyboard shortcut to close fullscreen modal
  useEffect(() => {
    if (!isFullscreen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsFullscreen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isFullscreen]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  // Pan handlers for fullscreen modal
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - modalPan.x, y: e.clientY - modalPan.y };
  }, [modalPan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setModalPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  return (
    <>
      <div className="hinaa-architecture-artifact my-4 overflow-hidden rounded-xl border border-slate-800 bg-[#070b14] shadow-2xl">
        {/* Top Header & Mode Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 bg-slate-950/70 px-4 py-2.5 backdrop-blur-md">
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

          <div className="flex flex-wrap items-center gap-2">
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

            {/* Zoom & Canvas Controls */}
            {viewMode === "diagram" && svgContent && (
              <div className="flex items-center rounded-lg bg-slate-900 p-0.5 ring-1 ring-slate-800 text-[11px] font-mono text-slate-300">
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.max(0.4, Math.round((z - 0.2) * 10) / 10))}
                  title="Zoom out"
                  className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition"
                >
                  -
                </button>
                <button
                  type="button"
                  onClick={() => setZoom(1)}
                  title="Reset zoom"
                  className="px-2 py-0.5 rounded hover:bg-slate-800 text-[10px]"
                >
                  {Math.round(zoom * 100)}%
                </button>
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.min(2.5, Math.round((z + 0.2) * 10) / 10))}
                  title="Zoom in"
                  className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition"
                >
                  +
                </button>
              </div>
            )}

            {/* Expand / Fullscreen Button */}
            {svgContent && (
              <button
                type="button"
                onClick={() => {
                  setModalZoom(1.2);
                  setModalPan({ x: 0, y: 0 });
                  setIsFullscreen(true);
                }}
                title="Expand to Fullscreen Explorer"
                className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-medium text-cyan-300 ring-1 ring-cyan-500/30 transition hover:bg-cyan-950/40 hover:text-cyan-200 hover:ring-cyan-500/50"
              >
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
                </svg>
                <span>Expand</span>
              </button>
            )}

            {/* Export SVG Button */}
            {svgContent && (
              <button
                type="button"
                onClick={handleExportSvg}
                title="Download vector SVG blueprint"
                className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300 ring-1 ring-slate-800 transition hover:bg-slate-800 hover:text-slate-100"
              >
                <svg className="h-3.5 w-3.5 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                <span>SVG</span>
              </button>
            )}

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
        <div className="relative min-h-[140px] p-4 bg-[#050811]">
          {viewMode === "diagram" && (
            <div className="flex w-full items-center justify-center overflow-x-auto py-2">
              {svgContent ? (
                <div
                  ref={containerRef}
                  style={{ transform: `scale(${zoom})`, transformOrigin: "top center", transition: "transform 0.15s ease" }}
                  className="mermaid-svg-container w-full max-w-full [&>svg]:mx-auto [&>svg]:h-auto [&>svg]:w-full [&>svg]:max-w-4xl"
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

      {/* Fullscreen Interactive Architecture Explorer Modal */}
      {isFullscreen && svgContent && (
        <div
          className="fixed inset-0 z-50 flex flex-col bg-slate-950/95 backdrop-blur-2xl text-slate-100 select-none animate-in fade-in duration-200"
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          {/* Modal Top Control Bar */}
          <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/80 px-6 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/30">
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.14 2.14a1.5 1.5 0 002.12 0l3.74-3.74" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-100">Architecture Explorer (Interactive Canvas)</h3>
                <p className="text-[11px] text-slate-400">Click & drag to pan • Scroll or use buttons to zoom • Press ESC to exit</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Zoom Controls */}
              <div className="flex items-center rounded-lg bg-slate-800/80 p-1 ring-1 ring-slate-700 text-xs font-mono">
                <button
                  type="button"
                  onClick={() => setModalZoom((z) => Math.max(0.3, Math.round((z - 0.2) * 10) / 10))}
                  title="Zoom Out"
                  className="px-2.5 py-1 rounded hover:bg-slate-700 text-slate-300 hover:text-white"
                >
                  -
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setModalZoom(1);
                    setModalPan({ x: 0, y: 0 });
                  }}
                  title="Reset Zoom & Pan"
                  className="px-3 py-1 rounded hover:bg-slate-700 text-slate-200"
                >
                  {Math.round(modalZoom * 100)}%
                </button>
                <button
                  type="button"
                  onClick={() => setModalZoom((z) => Math.min(3.5, Math.round((z + 0.2) * 10) / 10))}
                  title="Zoom In"
                  className="px-2.5 py-1 rounded hover:bg-slate-700 text-slate-300 hover:text-white"
                >
                  +
                </button>
              </div>

              {/* Export SVG */}
              <button
                type="button"
                onClick={handleExportSvg}
                className="flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 transition ring-1 ring-slate-700"
              >
                <svg className="h-3.5 w-3.5 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                <span>Export SVG</span>
              </button>

              {/* Close Button */}
              <button
                type="button"
                onClick={() => setIsFullscreen(false)}
                className="flex items-center justify-center h-8 w-8 rounded-lg bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition ring-1 ring-slate-700"
                title="Close (ESC)"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Interactive Infinite Canvas */}
          <div
            className={`flex-1 overflow-hidden relative cursor-grab ${isDragging ? "cursor-grabbing" : ""}`}
            onMouseDown={handleMouseDown}
          >
            <div
              style={{
                transform: `translate(${modalPan.x}px, ${modalPan.y}px) scale(${modalZoom})`,
                transformOrigin: "center center",
                transition: isDragging ? "none" : "transform 0.1s ease-out",
              }}
              className="w-full h-full flex items-center justify-center p-8 [&>svg]:max-w-none [&>svg]:h-auto select-none"
              dangerouslySetInnerHTML={{ __html: svgContent }}
            />
          </div>
        </div>
      )}
    </>
  );
});
