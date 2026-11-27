import { Panel, StatTile } from "../../design-system/hud";
import { PageFrame, ResourceState } from "../ui";
import { useApiJson } from "../useApi";

export interface SocietyEventItem {
  kind?: string;
  goal?: string;
  topic?: string;
  name?: string;
  verified?: boolean;
  rounds?: number;
  reviewer_caught?: number;
  failures?: string[];
  ts?: number;
}

export interface SocietyMetricsResponse {
  status: string;
  total_circles: number;
  first_pass_verified: number;
  first_pass_rate_pct: number | null;
  reviewer_catches: number;
  verifier_failures: number;
  lessons_stored: number;
  lessons_applied: number;
  skills_synthesized: number;
  marathons_completed: number;
  marathons_paused: number;
  recent_events: SocietyEventItem[];
}

export default function AgentHealthPage() {
  const state = useApiJson<SocietyMetricsResponse>("/api/v1/society/metrics");
  const m = state.data;

  return (
    <PageFrame
      title="Agent Health"
      subtitle="Verified first-pass rates, reviewer catches, compounding lessons, synthesized skills, and marathon checkpoints."
    >
      <ResourceState status={state.status} error={state.error} noun="agent health metrics" onRetry={state.reload}>
        {m && (
          <>
            <div className="shell-stats">
              <StatTile
                label="First-pass rate"
                value={m.first_pass_rate_pct !== null ? `${m.first_pass_rate_pct}%` : "—"}
              />
              <StatTile label="Society circles" value={m.total_circles} />
              <StatTile label="Reviewer catches" value={m.reviewer_catches} />
              <StatTile label="Lessons stored" value={m.lessons_stored} />
              <StatTile label="Skills synthesized" value={m.skills_synthesized} />
              <StatTile label="Marathons done" value={m.marathons_completed} />
            </div>

            <Panel title="Recent Society & Memory Events" aria-label="Recent Society Events">
              {m.recent_events.length === 0 ? (
                <p className="shell-state" data-kind="empty">
                  No agent society runs recorded yet.
                </p>
              ) : (
                <ul className="shell-list">
                  {[...m.recent_events].reverse().map((evt, i) => (
                    <li key={`${evt.ts ?? i}-${i}`} className="shell-card">
                      <div className="shell-card__row">
                        <strong>{evt.kind || "event"}</strong>
                        {typeof evt.verified === "boolean" && (
                          <span className="shell-card__meta">
                            {evt.verified ? "VERIFIED" : "FAILED"} · {evt.rounds ?? 1} round(s)
                          </span>
                        )}
                      </div>
                      <span className="shell-card__meta">
                        {evt.goal || evt.topic || evt.name || "Recorded milestone"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </>
        )}
      </ResourceState>
    </PageFrame>
  );
}
