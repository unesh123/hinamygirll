import React, { useState } from "react";
import { ExternalLink, Globe } from "lucide-react";

export interface CitationSource {
  id: string; // e.g. "1", "2"
  title: string;
  publisher?: string;
  url?: string;
  date?: string;
  snippet?: string;
}

export interface CitationPopoverProps {
  source: CitationSource;
  children: React.ReactNode;
}

export const CitationPopover: React.FC<CitationPopoverProps> = ({ source, children }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <span
      className="citation-wrapper"
      style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <span
        style={{
          cursor: "pointer",
          color: "var(--accent-primary, #dc5f8b)",
          fontWeight: 600,
          padding: "0 2px",
        }}
      >
        {children}
      </span>

      {isOpen && (
        <div
          className="citation-popover"
          style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: "50%",
            transform: "translateX(-50%)",
            width: 260,
            padding: 10,
            background: "var(--surface-overlay, #ffffff)",
            borderRadius: "var(--radius-md, 12px)",
            boxShadow: "var(--shadow-dropdown, 0 10px 25px -5px rgba(0,0,0,0.1))",
            border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
            zIndex: 60,
            pointerEvents: "auto",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <Globe size={12} style={{ color: "var(--accent-primary)" }} />
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: "var(--text-tertiary)",
                textTransform: "uppercase",
                letterSpacing: "0.03em",
              }}
            >
              {source.publisher || "Source"} {source.date ? `· ${source.date}` : ""}
            </span>
          </div>

          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--text-primary)",
              marginBottom: 4,
              lineHeight: 1.3,
            }}
          >
            {source.title}
          </div>

          {source.snippet && (
            <div
              style={{
                fontSize: 11,
                color: "var(--text-secondary)",
                lineHeight: 1.35,
                marginBottom: 6,
                maxHeight: 60,
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {source.snippet}
            </div>
          )}

          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                fontWeight: 600,
                color: "var(--accent-primary)",
                textDecoration: "none",
              }}
            >
              <span>Visit Source</span>
              <ExternalLink size={10} />
            </a>
          )}
        </div>
      )}
    </span>
  );
};
