import { useMemo } from "react";
import { Command, FileCode2 } from "lucide-react";
import type { HinaIntent } from "../../actions/types";
import type { TurnArtifact } from "../contracts/agentEvents";

export interface SlashCommandItem {
  id: string;
  trigger: string;
  label: string;
  description: string;
  intent: HinaIntent;
}

/** Real slash commands grounded strictly in implemented action engine intents. */
export const REAL_SLASH_COMMANDS: SlashCommandItem[] = [
  { id: "split", trigger: "/split", label: "Split bill", description: "Split an expense across people", intent: "split" },
  { id: "timer", trigger: "/timer", label: "Start timer", description: "Launch a timed focus countdown", intent: "timer.start" },
  { id: "reminder", trigger: "/remind", label: "Create reminder", description: "Schedule a reminder at a local time", intent: "reminder.create" },
  { id: "checklist", trigger: "/checklist", label: "Checklist", description: "Build an interactive checklist", intent: "checklist.create" },
  { id: "timezone", trigger: "/tz", label: "Timezone convert", description: "Convert times across timezones", intent: "timezone.convert" },
  { id: "image", trigger: "/image", label: "Generate image", description: "Create artwork via configured image tool", intent: "image.job" },
  { id: "doc", trigger: "/doc", label: "Draft document", description: "Create a structured report or PDF", intent: "pdf.doc" },
  { id: "plan", trigger: "/plan", label: "Run step plan", description: "Plan and execute a multi-step task", intent: "plan.run" },
  { id: "browser", trigger: "/browse", label: "Browser task", description: "Open or inspect a page with the browser agent", intent: "browser.agent" },
];

export interface SlashCommandPaletteProps {
  query: string;
  mode: "slash" | "mention" | null;
  artifacts?: TurnArtifact[];
  onSelect: (insertion: string) => void;
}

export function SlashCommandPalette({
  query,
  mode,
  artifacts = [],
  onSelect,
}: SlashCommandPaletteProps) {
  const items = useMemo(() => {
    const clean = query.trim().toLowerCase();
    if (mode === "slash") {
      return REAL_SLASH_COMMANDS.filter(
        (c) =>
          !clean ||
          c.trigger.toLowerCase().includes(clean) ||
          c.label.toLowerCase().includes(clean),
      ).map((c) => ({
        id: c.id,
        primary: c.trigger,
        secondary: `${c.label} — ${c.description}`,
        insert: `${c.trigger} `,
      }));
    }
    if (mode === "mention") {
      return artifacts
        .filter((a) => !clean || a.label.toLowerCase().includes(clean))
        .map((a) => ({
          id: a.id,
          primary: `@${a.label}`,
          secondary: a.path || a.kind,
          insert: `@${a.label} `,
        }));
    }
    return [];
  }, [artifacts, mode, query]);

  if (!mode || items.length === 0) return null;

  return (
    <div
      data-testid="chat-slash-palette"
      role="listbox"
      aria-label={mode === "slash" ? "Slash commands" : "Turn files and artifacts"}
      className="mb-2 max-h-48 overflow-y-auto rounded-xl border p-1.5"
      style={{
        background: "var(--bg-elevated)",
        borderColor: "var(--border-strong)",
        boxShadow: "var(--shadow-float)",
      }}
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="option"
          aria-selected="false"
          onClick={() => onSelect(item.insert)}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left text-xs hover:opacity-90 cursor-pointer"
          style={{ color: "var(--text-primary)" }}
        >
          {mode === "slash" ? (
            <Command size={13} style={{ color: "var(--accent-primary)" }} className="shrink-0" />
          ) : (
            <FileCode2 size={13} style={{ color: "var(--accent-secondary)" }} className="shrink-0" />
          )}
          <span className="font-semibold" style={{ fontFamily: "var(--font-mono)" }}>
            {item.primary}
          </span>
          <span className="truncate text-[11px]" style={{ color: "var(--text-muted)" }}>
            {item.secondary}
          </span>
        </button>
      ))}
    </div>
  );
}
