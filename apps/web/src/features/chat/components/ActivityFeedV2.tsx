import { useMemo } from "react";
import { Globe, Wrench, FileSearch, Brain, Hammer, CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { ActivityStep } from "./AgentActivityCard";

export type ActivityLaneId = "reasoning" | "research" | "files" | "media" | "system";

export interface ActivityLane {
  id: ActivityLaneId;
  label: string;
  icon: "brain" | "globe" | "file" | "hammer" | "wrench";
  steps: ActivityStep[];
}

export interface ActivityFeedV2Props {
  steps: ActivityStep[];
  /** Render lanes side by side; falls back to stacked on narrow widths. */
  orientation?: "auto" | "stacked";
}

const LANE_ORDER: ActivityLaneId[] = ["reasoning", "research", "files", "media", "system"];

const LANE_META: Record<ActivityLaneId, { label: string; icon: ActivityLane["icon"]; patterns: RegExp[] }> = {
  reasoning: {
    label: "Reasoning",
    icon: "brain",
    patterns: [/plan/i, /think/i, /intent/i, /reason/i, /decide/i, /summariz?e/i],
  },
  research: {
    label: "Research",
    icon: "globe",
    patterns: [/search/i, /web/i, /browse/i, /fetch/i, /crawl/i, /scrape/i],
  },
  files: {
    label: "Files",
    icon: "file",
    patterns: [/file/i, /edit/i, /read/i, /write/i, /document/i, /pdf/i, /repo/i, /test/i],
  },
  media: {
    label: "Media",
    icon: "hammer",
    patterns: [/image/i, /video/i, /render/i, /audio/i, /voice/i, /avatar/i, /comfy/i, /ffmpeg/i],
  },
  system: {
    label: "System",
    icon: "wrench",
    patterns: [/.*/], // fallback lane
  },
};

const LANE_ICONS = {
  brain: Brain,
  globe: Globe,
  file: FileSearch,
  hammer: Hammer,
  wrench: Wrench,
} as const;

const STEP_STATUS_ICON = {
  completed: CheckCircle2,
  failed: XCircle,
} as const;

function laneFor(step: ActivityStep): ActivityLaneId {
  const hay = `${step.toolName ?? ""} ${step.title} ${step.message ?? ""}`;
  for (const id of LANE_ORDER) {
    if (id === "system") continue;
    if (LANE_META[id].patterns.some((re) => re.test(hay))) return id;
  }
  return "system";
}

/**
 * Activity Feed v2 — groups execution steps into parallel tool lanes so the
 * user can see reasoning, research, file work and media work happening
 * side-by-side instead of one flat list. Steps are never reordered, only
 * bucketed; within a lane the original order is preserved.
 */
export function ActivityFeedV2({ steps, orientation = "auto" }: ActivityFeedV2Props) {
  const lanes = useMemo<ActivityLane[]>(() => {
    const buckets = new Map<ActivityLaneId, ActivityStep[]>();
    for (const step of steps) {
      const id = laneFor(step);
      const list = buckets.get(id) ?? [];
      list.push(step);
      buckets.set(id, list);
    }
    return LANE_ORDER.filter((id) => buckets.has(id)).map((id) => ({
      id,
      label: LANE_META[id].label,
      icon: LANE_META[id].icon,
      steps: buckets.get(id)!,
    }));
  }, [steps]);

  if (lanes.length === 0) return null;

  return (
    <div
      data-testid="activity-feed-v2"
      className={
        orientation === "stacked"
          ? "grid grid-cols-1 gap-3"
          : "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
      }
    >
      {lanes.map((lane) => {
        const Icon = LANE_ICONS[lane.icon];
        return (
          <section
            key={lane.id}
            data-testid={`activity-lane-${lane.id}`}
            className="rounded-xl border border-glass-border bg-frost/60 p-2 min-w-0"
          >
            <header className="flex items-center gap-1.5 mb-1.5">
              <Icon size={12} className="text-accent" />
              <span className="text-[10px] font-bold uppercase tracking-wide text-text-muted">
                {lane.label}
              </span>
              <span className="ml-auto text-[10px] text-text-muted">
                {lane.steps.length}
              </span>
            </header>
            <ul className="space-y-1">
              {lane.steps.map((step) => {
                const StatusIcon =
                  step.status in STEP_STATUS_ICON
                    ? STEP_STATUS_ICON[step.status as keyof typeof STEP_STATUS_ICON]
                    : Loader2;
                return (
                  <li
                    key={step.id}
                    data-testid={`activity-step-${step.id}`}
                    className="flex items-start gap-1.5 text-[11px] leading-snug text-text-primary min-w-0"
                  >
                    <StatusIcon
                      size={12}
                      className={
                        step.status === "completed"
                          ? "text-emerald-500 shrink-0"
                          : step.status === "failed"
                            ? "text-red-500 shrink-0"
                            : "text-accent shrink-0 animate-spin"
                      }
                    />
                    <span className="min-w-0 break-words">
                      <span className="font-semibold">{step.title}</span>
                      {step.message && (
                        <span className="text-text-muted"> — {step.message}</span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
