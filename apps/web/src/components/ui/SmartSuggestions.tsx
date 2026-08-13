import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Image,
  Code,
  FileText,
  Brain,
  Sparkles,
  Lightbulb,
  Mic,
  Wrench,
  type LucideIcon,
} from "lucide-react";

export type SuggestionTransform = (input: string) => string;

export interface Suggestion {
  id: string;
  icon: LucideIcon;
  label: string;
  description: string;
  color: string;
  prefix?: string;
  transform?: SuggestionTransform;
}

const BASE_SUGGESTIONS: Suggestion[] = [
  { id: "search-web", icon: Search, label: "Search the live web", description: "Fast attributable web results", color: "#7dd3fc", prefix: "Search the web for: " },
  { id: "research-sources", icon: Brain, label: "Research with sources", description: "Multi-source cited answer", color: "#d8b4fe", prefix: "Research the web with sources: " },
  { id: "generate-image", icon: Sparkles, label: "Generate a local image", description: "Use your private ComfyUI workflow", color: "#f9a8d4", prefix: "Generate an image of: " },
  { id: "plan-task", icon: Wrench, label: "Create a task plan", description: "Turn a goal into visible local steps", color: "#fdba74", prefix: "Plan this task: " },
  { id: "summarize-document", icon: FileText, label: "Summarize a document", description: "Use text or an uploaded local file", color: "#a7f3d0", prefix: "Summarize this clearly: " },
  { id: "write-code", icon: Code, label: "Build or explain code", description: "Architecture, examples, tests, and limits", color: "#93c5fd", prefix: "Explain and implement: " },
  { id: "explain-concept", icon: Lightbulb, label: "Explain clearly", description: "A concise answer with practical examples", color: "#fde68a", prefix: "Explain: " },
  { id: "voice-chat", icon: Mic, label: "Start live voice", description: "Open HINAA’s microphone conversation", color: "#86efac", prefix: "" },
];

function containsAny(input: string, words: string[]) {
  return words.some((word) => input.includes(word));
}

/**
 * Produce useful completions from what the user is already writing. The
 * transforms deliberately use HINAA's existing deterministic command phrases
 * so a visible suggestion maps to a real approved tool path rather than a
 * decorative prompt.
 */
export function rankSmartSuggestions(input: string, maxSuggestions = 5): Suggestion[] {
  const clean = input.replace(/\s+/g, " ").trim();
  const lower = clean.toLowerCase();
  if (!clean) return [];

  const contextual: Suggestion[] = [];
  if (containsAny(lower, ["research", "compare", "latest", "current", "source", "citation", "investigate", "documentation"])) {
    contextual.push(
      {
        id: "context-deep-research",
        icon: Brain,
        label: "Research this deeply with sources",
        description: "Uses deeper cross-referencing; approval will show the effort level",
        color: "#d8b4fe",
        transform: (value) => `Deep research the web with sources: ${value.trim()}`,
      },
      {
        id: "context-compare-research",
        icon: Search,
        label: "Make a sourced comparison",
        description: "Compare choices, trade-offs, and a recommendation",
        color: "#7dd3fc",
        transform: (value) => `Research the web with sources and compare: ${value.trim()}`,
      },
    );
  }
  if (containsAny(lower, ["image", "art", "portrait", "anime", "illustration", "render", "variation"])) {
    contextual.push({
      id: "context-image-variations",
      icon: Image,
      label: "Generate four local variations",
      description: "Creates independent ComfyUI result slots",
      color: "#f9a8d4",
      transform: (value) => `Generate four fast image variations of: ${value.trim()}`,
    });
  }
  if (containsAny(lower, ["pdf", "document", "docx", "pptx", "file", "summarize", "report"])) {
    contextual.push({
      id: "context-document-artifact",
      icon: FileText,
      label: "Turn this into a project artifact",
      description: "Keep the output organized in a local project",
      color: "#a7f3d0",
      transform: (value) => `Plan this task and save the document results to my local project: ${value.trim()}`,
    });
  }
  if (containsAny(lower, ["code", "bug", "error", "react", "python", "api", "build", "implement"])) {
    contextual.push({
      id: "context-code-explain",
      icon: Code,
      label: "Explain with architecture and tests",
      description: "Ask for implementation detail, limits, and verification",
      color: "#93c5fd",
      transform: (value) => `Explain in detail with architecture, examples, limitations, and tests: ${value.trim()}`,
    });
  }

  const directMatches = BASE_SUGGESTIONS
    .map((suggestion) => {
      const haystack = `${suggestion.label} ${suggestion.description}`.toLowerCase();
      const words = lower.split(/\s+/).filter(Boolean);
      const score = words.reduce((total, word) => total + (haystack.includes(word) ? 1 : 0), 0);
      return { suggestion, score };
    })
    .filter(({ score }) => score > 0)
    .sort((left, right) => right.score - left.score)
    .map(({ suggestion }) => suggestion);

  const unique = new Map<string, Suggestion>();
  for (const suggestion of [...contextual, ...directMatches]) unique.set(suggestion.id, suggestion);
  return [...unique.values()].slice(0, maxSuggestions);
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
  maxSuggestions = 5,
}: SmartSuggestionsProps) {
  const ranked = useMemo(
    () => rankSmartSuggestions(input, maxSuggestions),
    [input, maxSuggestions],
  );

  return (
    <AnimatePresence>
      {visible && ranked.length > 0 && (
        <motion.div
          className="smart-suggestions"
          role="listbox"
          aria-label="Suggested next actions"
          initial={{ opacity: 0, y: 6, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 5, scale: 0.98 }}
          transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
        >
          <div className="smart-suggestions__heading">Suggested next step</div>
          {ranked.map((suggestion, index) => {
            const Icon = suggestion.icon;
            return (
              <motion.button
                key={suggestion.id}
                type="button"
                role="option"
                aria-label={`${suggestion.label}: ${suggestion.description}`}
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.025, duration: 0.16 }}
                onClick={() => onSelect(suggestion)}
                className="smart-suggestions__option"
              >
                <span className="smart-suggestions__icon" style={{ color: suggestion.color, background: `${suggestion.color}18` }}>
                  <Icon size={14} aria-hidden="true" />
                </span>
                <span className="smart-suggestions__copy">
                  <strong>{suggestion.label}</strong>
                  <small>{suggestion.description}</small>
                </span>
                <span className="smart-suggestions__apply" aria-hidden="true">Apply</span>
              </motion.button>
            );
          })}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default SmartSuggestions;
