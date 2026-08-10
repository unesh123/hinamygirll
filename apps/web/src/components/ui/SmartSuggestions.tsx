/**
 * SmartSuggestions — animated type-ahead chips that appear as user types
 * Predicts intent with 5-10+ contextual suggestions using pattern matching
 */

import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, Image, Globe, Code, Music, Mail, Calendar,
  FileText, Brain, Sparkles, Lightbulb, Mic, Wrench,
} from "lucide-react";
import type { IconComponent } from "../../shared/iconType";

export interface Suggestion {
  id: string;
  icon: IconComponent;
  label: string;
  description: string;
  color: string;
  prefix?: string;
}

/* ─── Suggestion database ──────────────────────────────── */
const ALL_SUGGESTIONS: Suggestion[] = [
  { id: "search-web", icon: Search, label: "Search the web", description: "Real-time search with sources", color: "#0891b2", prefix: "Search for: " },
  { id: "find-images", icon: Image, label: "Find images", description: "Search for photos and pictures", color: "#7c3aed", prefix: "Find images of: " },
  { id: "generate-image", icon: Sparkles, label: "Generate image", description: "Create AI-generated artwork", color: "#d97706", prefix: "Generate an image of: " },
  { id: "browse-web", icon: Globe, label: "Browse website", description: "Open and read a webpage", color: "#059669", prefix: "Open: " },
  { id: "write-code", icon: Code, label: "Write code", description: "Generate or explain code", color: "#dc2626", prefix: "Write code for: " },
  { id: "explain-concept", icon: Lightbulb, label: "Explain concept", description: "Learn about any topic", color: "#f59e0b", prefix: "Explain: " },
  { id: "play-music", icon: Music, label: "Play music", description: "Find and play songs on YouTube", color: "#ef4444", prefix: "Play: " },
  { id: "check-email", icon: Mail, label: "Check email", description: "Find and read emails", color: "#3b82f6", prefix: "Show emails" },
  { id: "show-calendar", icon: Calendar, label: "Show calendar", description: "Check your schedule", color: "#8b5cf6", prefix: "Show calendar" },
  { id: "search-files", icon: FileText, label: "Search files", description: "Find documents and files", color: "#64748b", prefix: "Find files: " },
  { id: "remember-this", icon: Brain, label: "Remember this", description: "Save to memory", color: "#ec4899", prefix: "Remember: " },
  { id: "summarize", icon: Sparkles, label: "Summarize", description: "Condense text or pages", color: "#14b8a6", prefix: "Summarize: " },
  { id: "translate", icon: Globe, label: "Translate", description: "Translate between languages", color: "#06b6d4", prefix: "Translate: " },
  { id: "voice-chat", icon: Mic, label: "Start voice chat", description: "Talk naturally with HINAA", color: "#10b981", prefix: "" },
  { id: "automate", icon: Wrench, label: "Automate task", description: "Chain multiple actions", color: "#f97316", prefix: "Automate: " },
];

/* ─── Pattern matcher ──────────────────────────────────── */
function scoreSuggestion(suggestion: Suggestion, input: string): number {
  const lower = input.toLowerCase().trim();
  if (!lower) return 0;

  let score = 0;
  const label = suggestion.label.toLowerCase();
  const desc = suggestion.description.toLowerCase();

  // Exact match
  if (label === lower) score += 100;
  // Starts with
  if (label.startsWith(lower)) score += 80;
  // Contains
  if (label.includes(lower)) score += 60;
  if (desc.includes(lower)) score += 40;

  // Word-level matching
  const words = lower.split(/\s+/);
  for (const word of words) {
    if (label.includes(word)) score += 30;
    if (desc.includes(word)) score += 20;
  }

  // Category matching
  const categories: Record<string, string[]> = {
    search: ["search-web", "find-images", "search-files"],
    image: ["find-images", "generate-image"],
    code: ["write-code", "explain-concept"],
    music: ["play-music"],
    email: ["check-email"],
    calendar: ["show-calendar"],
    memory: ["remember-this"],
    voice: ["voice-chat"],
    browser: ["browse-web"],
    summarize: ["summarize"],
    translate: ["translate"],
    automate: ["automate"],
  };

  for (const [cat, ids] of Object.entries(categories)) {
    if (lower.includes(cat) && ids.includes(suggestion.id)) score += 25;
  }

  return score;
}

interface SmartSuggestionsProps {
  input: string;
  onSelect: (suggestion: Suggestion) => void;
  visible: boolean;
  maxSuggestions?: number;
}

export function SmartSuggestions({
  input,
  onSelect,
  visible,
  maxSuggestions = 10,
}: SmartSuggestionsProps) {
  const ranked = useMemo(() => {
    if (!input.trim()) return [];
    return ALL_SUGGESTIONS
      .map((s) => ({ suggestion: s, score: scoreSuggestion(s, input) }))
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, maxSuggestions)
      .map((s) => s.suggestion);
  }, [input, maxSuggestions]);

  return (
    <AnimatePresence>
      {visible && ranked.length > 0 && (
        <motion.div
          className="smart-suggestions"
          initial={{ opacity: 0, y: 6, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 6, scale: 0.97 }}
          transition={{ duration: 0.22, ease: [0.22, 0.61, 0.36, 1] }}
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: 0,
            right: 0,
            background: "rgba(255,255,255,0.9)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            borderRadius: 16,
            border: "1px solid rgba(255,255,255,0.85)",
            boxShadow: "0 8px 40px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.04)",
            padding: 6,
            zIndex: 200,
            maxHeight: 340,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          {ranked.map((suggestion, i) => {
            const Icon = suggestion.icon;
            return (
              <motion.button
                key={suggestion.id}
                type="button"
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03, duration: 0.2 }}
                onClick={() => onSelect(suggestion)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "9px 12px",
                  border: "none",
                  background: "transparent",
                  borderRadius: 10,
                  cursor: "pointer",
                  width: "100%",
                  textAlign: "left",
                  fontFamily: "inherit",
                  transition: "background 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "rgba(167,243,208,0.2)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = "transparent";
                }}
              >
                <span
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 8,
                    background: `${suggestion.color}18`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Icon size={14} color={suggestion.color} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#1a1f2e" }}>
                    {suggestion.label}
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "#94a3b8", marginTop: 1 }}>
                    {suggestion.description}
                  </div>
                </div>
                {suggestion.prefix && (
                  <span style={{ fontSize: "0.65rem", color: "#94a3b8", flexShrink: 0 }}>
                    ↵
                  </span>
                )}
              </motion.button>
            );
          })}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default SmartSuggestions;
