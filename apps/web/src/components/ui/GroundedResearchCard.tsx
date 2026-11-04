import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, HelpCircle, Sparkles, ExternalLink, Globe, ChevronDown, ChevronUp } from "lucide-react";

export type GroundingVerificationStatus =
  | "VERIFIED_FACT"
  | "INFERENCE"
  | "SOURCES_DISAGREE"
  | "NOT_ENOUGH_EVIDENCE";

export interface ResearchSourceItem {
  source_id: string;
  title: string;
  url: string;
  publisher?: string;
  publication_date?: string;
  event_date?: string;
  excerpt: string;
}

export interface GroundedResearchCardProps {
  status: GroundingVerificationStatus;
  sources: ResearchSourceItem[];
  abstentionReason?: string;
  onSelectSource?: (source: ResearchSourceItem) => void;
}

export function GroundedResearchCard({
  status,
  sources,
  abstentionReason,
  onSelectSource,
}: GroundedResearchCardProps) {
  const [expanded, setExpanded] = useState(false);

  const statusConfig = {
    VERIFIED_FACT: {
      label: "Verified from Sources",
      icon: <CheckCircle2 size={13} className="text-emerald-500" />,
      badgeClass: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
    },
    INFERENCE: {
      label: "Model Inference",
      icon: <Sparkles size={13} className="text-indigo-500" />,
      badgeClass: "bg-indigo-500/10 text-indigo-600 border-indigo-500/20",
    },
    SOURCES_DISAGREE: {
      label: "Sources Disagree",
      icon: <AlertTriangle size={13} className="text-amber-500" />,
      badgeClass: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    },
    NOT_ENOUGH_EVIDENCE: {
      label: "Not Enough Evidence (Abstained)",
      icon: <HelpCircle size={13} className="text-slate-500" />,
      badgeClass: "bg-slate-500/10 text-slate-600 border-slate-500/20",
    },
  }[status];

  return (
    <div
      className="my-2 p-3 bg-frost/90 backdrop-blur-sm border border-glass-border rounded-xl shadow-xs text-xs font-sans min-w-0"
      role="region"
      aria-label="Research Grounding and Sources"
    >
      {/* ── Top Bar: Grounding Status & Toggle ── */}
      <div className="flex items-center justify-between gap-2 min-w-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-semibold tracking-wide ${statusConfig.badgeClass}`}
          >
            {statusConfig.icon}
            {statusConfig.label}
          </span>
          {sources.length > 0 && (
            <span className="text-text-muted text-[11px]">
              ({sources.length} {sources.length === 1 ? "source" : "sources"})
            </span>
          )}
        </div>

        {sources.length > 0 && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 px-2 py-0.5 rounded-md hover:bg-black/5 text-text-secondary text-[11px] font-medium transition-colors cursor-pointer"
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse sources" : "Expand sources"}
          >
            <span>{expanded ? "Hide sources" : "View sources"}</span>
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
        )}
      </div>

      {/* ── Abstention Details ── */}
      {status === "NOT_ENOUGH_EVIDENCE" && abstentionReason && (
        <p className="mt-2 text-[11px] text-text-muted italic">
          {abstentionReason}
        </p>
      )}

      {/* ── Expandable Source Cards ── */}
      {expanded && sources.length > 0 && (
        <div className="mt-3 flex flex-col gap-2 pt-2 border-t border-glass-border">
          {sources.map((src, idx) => {
            const domain = src.url ? new URL(src.url).hostname : "source";
            return (
              <div
                key={src.source_id || idx}
                className="p-2.5 rounded-lg bg-surface/50 border border-glass-border/70 hover:border-brand-300/40 transition-all text-[11px] flex flex-col gap-1 min-w-0"
              >
                <div className="flex items-center justify-between gap-2 min-w-0">
                  <div className="flex items-center gap-1.5 font-semibold text-text-primary min-w-0 truncate">
                    <span className="w-4 h-4 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[10px] flex-shrink-0 font-bold">
                      {idx + 1}
                    </span>
                    <Globe size={11} className="text-text-muted flex-shrink-0" />
                    <span className="truncate">{src.title}</span>
                  </div>

                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[10px] text-accent hover:underline flex-shrink-0 ml-2"
                    aria-label={`Open external link for ${src.title}`}
                  >
                    <span>{domain}</span>
                    <ExternalLink size={10} />
                  </a>
                </div>

                {src.excerpt && (
                  <p className="text-text-secondary text-[10px] leading-relaxed line-clamp-2 mt-0.5 break-words">
                    &ldquo;{src.excerpt}&rdquo;
                  </p>
                )}

                <div className="flex items-center gap-2 text-[9px] text-text-muted mt-0.5">
                  {src.publisher && <span>Pub: {src.publisher}</span>}
                  {src.publication_date && <span>Date: {src.publication_date}</span>}
                  {src.event_date && (
                    <span className="text-amber-600 font-medium">
                      Event: {src.event_date}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
